#!/usr/bin/env bash
# init.sh — Verificación e inicialización del entorno (POSIX / WSL / CI Linux)
#
# Propósito : comprobar que el repositorio está en un estado sano antes de
#             trabajar y antes de declarar cualquier feature como `done`.
# Lo ejecuta: el agente al COMENZAR una sesión, el hook `Stop` al cerrarla, y
#             el reviewer antes de emitir su veredicto. Si falla, la sesión no avanza.
# Equivalente: ./init.ps1 (canónico en Windows; misma salida y mismo exit code).
# Parámetros : ninguno.
# Uso        : ./init.sh
# Salida     : bloques numerados con líneas [OK] / [WARN] / [FAIL].
# Exit codes : 0 entorno listo (los [WARN] no bloquean) · 1 hay algo que resolver.

set -u

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

ok()    { printf "${GREEN}[OK]${NC}    %s\n" "$1"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$1"; }
fail()  { printf "${RED}[FAIL]${NC}  %s\n" "$1"; }

EXIT_CODE=0

echo "── 1. Verificando entorno ─────────────────────────────"

# Intérprete de Python: acepta cualquiera de los nombres habituales y descarta
# los stubs que no ejecutan nada (p. ej. el alias `python3` de la Microsoft Store,
# que existe en el PATH pero solo imprime un aviso de instalación).
PY=""
PY_VERSION=""
for candidate in python3 python py; do
  command -v "$candidate" >/dev/null 2>&1 || continue
  probe=$("$candidate" -c 'import sys; print("PYOK", ".".join(map(str, sys.version_info[:3])), int(sys.version_info >= (3, 9)))' 2>/dev/null)
  case "$probe" in
    PYOK*)
      PY="$candidate"
      PY_VERSION=$(echo "$probe" | cut -d" " -f2)
      PY_OK=$(echo "$probe" | cut -d" " -f3)
      break
      ;;
  esac
done

if [ -z "$PY" ]; then
  fail "No se encontró un Python ejecutable (probé python3, python, py)"
  exit 1
fi
ok "Python -> $PY $PY_VERSION"

# Versión mínima 3.9 (dataclasses + sintaxis moderna de typing)
if [ "$PY_OK" != "1" ]; then
  fail "Se requiere Python >= 3.9 (encontrado $PY_VERSION)"
  exit 1
fi
ok "Versión de Python compatible"

echo ""
echo "── 2. Verificando archivos base del arnés ──────────────"

for f in AGENTS.md CHECKPOINTS.md feature_list.json progress/current.md \
         docs/architecture.md docs/conventions.md docs/verification.md docs/scripts.md; do
  if [ ! -f "$f" ]; then
    fail "Falta archivo base: $f"
    EXIT_CODE=1
  else
    ok "Existe $f"
  fi
done

echo ""
echo "── 3. Validando feature_list.json ──────────────────────"

if [ -f "scripts/validate_feature_list.py" ]; then
  if ! $PY scripts/validate_feature_list.py feature_list.json; then
    EXIT_CODE=1
  fi
else
  fail "Falta scripts/validate_feature_list.py — no se puede validar el alcance"
  EXIT_CODE=1
fi

echo ""
echo "── 4. Ejecutando tests ─────────────────────────────────"

if [ ! -d "tests" ]; then
  warn "La carpeta tests/ no existe todavía"
else
  # Contar antes de ejecutar: un discover sin tests devuelve 0 y no debe
  # confundirse con "todo verde". Un repo recién instanciado avisa, no falla.
  TEST_COUNT=$($PY -c 'import unittest; print(unittest.TestLoader().discover("tests").countTestCases())' 2>/dev/null || echo "-1")

  if [ "$TEST_COUNT" = "-1" ]; then
    fail "No se pudieron descubrir los tests (¿error de import en tests/?)"
    EXIT_CODE=1
  elif [ "$TEST_COUNT" = "0" ]; then
    warn "0 tests en tests/ — el arnés no está verificando nada todavía"
  else
    if $PY -m unittest discover -s tests -v 2>&1; then
      ok "Todos los tests pasan ($TEST_COUNT tests)"
    else
      fail "Hay tests rotos"
      EXIT_CODE=1
    fi
  fi
fi

echo ""
echo "── 5. Resumen ──────────────────────────────────────────"

if [ $EXIT_CODE -eq 0 ]; then
  ok "Entorno listo. Puedes empezar a trabajar."
else
  fail "Entorno NO está listo. Resuelve los errores antes de avanzar."
fi

exit $EXIT_CODE
