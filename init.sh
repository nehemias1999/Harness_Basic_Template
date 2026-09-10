#!/usr/bin/env bash
# init.sh — Verificación e inicialización del entorno (POSIX / WSL / CI Linux)
#
# Propósito : comprobar que el repositorio está en un estado sano antes de
#             trabajar y antes de declarar cualquier feature como `done`.
# Lo ejecuta: el agente al COMENZAR una sesión, el hook `Stop` (vía
#             scripts/harness_hook.py) al cerrarla, y
#             el reviewer antes de emitir su veredicto. Si falla, la sesión no avanza.
# Equivalente: ./init.ps1 (canónico en Windows; misma salida y mismo exit code).
# Parámetros : --quiet  resume la salida de los tests (equivale a -Quiet de init.ps1).
# Uso        : ./init.sh [--quiet]
# Salida     : bloques numerados con líneas [OK] / [WARN] / [FAIL].
# Exit codes : 0 entorno listo (los [WARN] no bloquean) · 1 hay algo que resolver.

set -u

# Como init.ps1: el verificador se planta en la raíz del repositorio. Sin esto,
# ejecutarlo desde otro directorio reportaba los 8 archivos base como
# "faltantes" en vez de verificar lo que había que verificar.
cd "$(dirname "$0")" || exit 1

QUIET=0
for arg in "$@"; do
  case "$arg" in
    --quiet) QUIET=1 ;;
    *) printf "Parámetro desconocido: %s (solo --quiet)
" "$arg" >&2; exit 1 ;;
  esac
done

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
echo "── 3. Verificando configuración del proyecto ───────────"

# Bloqueante a propósito: un arnés sin configurar no tiene criterio de calidad
# (el reviewer juzga contra docs/architecture.md). Ver docs/scripts.md.
if [ -f "scripts/validate_project_setup.py" ]; then
  if ! $PY scripts/validate_project_setup.py .; then
    EXIT_CODE=1
  fi
else
  fail "Falta scripts/validate_project_setup.py — no se puede verificar la configuración"
  EXIT_CODE=1
fi

echo ""
echo "── 4. Validando feature_list.json ──────────────────────"

if [ -f "scripts/validate_feature_list.py" ]; then
  if ! $PY scripts/validate_feature_list.py feature_list.json; then
    EXIT_CODE=1
  fi
else
  fail "Falta scripts/validate_feature_list.py — no se puede validar el alcance"
  EXIT_CODE=1
fi

echo ""
echo "── 5. Validando requisitos y trazabilidad ──────────────"

# Bloqueante a propósito: la aprobación de un requisito no es un "dale" en el
# chat, es `estado: aprobado` en specs/ mas la feature en `pending`. Mismo
# módulo que usa init.ps1. Ver docs/scripts.md.
if [ -f "scripts/validate_requirements.py" ]; then
  if ! $PY scripts/validate_requirements.py .; then
    EXIT_CODE=1
  fi
else
  fail "Falta scripts/validate_requirements.py — no se puede verificar la trazabilidad"
  EXIT_CODE=1
fi

echo ""
echo "── 6. Ejecutando tests ─────────────────────────────────"

if [ ! -d "tests" ]; then
  warn "La carpeta tests/ no existe todavía"
else
  # Contar antes de ejecutar: un discover sin tests devuelve 0 y no debe
  # confundirse con "todo verde". Un repo recién instanciado avisa, no falla.
  # Se compara el exit code del conteo en vez de su salida: si Python imprime
  # algo antes de fallar, una comparación de cadenas mandaría al verificador a
  # ejecutar tests que no se pudieron ni descubrir (init.ps1 ya miraba el code).
  if TEST_COUNT=$($PY -c 'import unittest; print(unittest.TestLoader().discover("tests").countTestCases())' 2>/dev/null); then
    :
  else
    TEST_COUNT="-1"
  fi

  if [ "$TEST_COUNT" = "-1" ]; then
    fail "No se pudieron descubrir los tests (¿error de import en tests/?)"
    EXIT_CODE=1
  elif [ "$TEST_COUNT" = "0" ]; then
    warn "0 tests en tests/ — el arnés no está verificando nada todavía"
  else
    if [ "$QUIET" -eq 1 ]; then
      TEST_FLAG="-q"
    else
      TEST_FLAG="-v"
    fi
    if $PY -m unittest discover -s tests "$TEST_FLAG" 2>&1; then
      ok "Todos los tests pasan ($TEST_COUNT tests)"
    else
      fail "Hay tests rotos"
      EXIT_CODE=1
    fi
  fi
fi

echo ""
echo "── 7. Resumen ──────────────────────────────────────────"

if [ $EXIT_CODE -eq 0 ]; then
  ok "Entorno listo. Puedes empezar a trabajar."
else
  fail "Entorno NO está listo. Resuelve los errores antes de avanzar."
fi

exit $EXIT_CODE
