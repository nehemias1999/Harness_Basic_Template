#!/usr/bin/env bash
# bootstrap.sh — Instancia un proyecto nuevo (POSIX / WSL / macOS / Linux)
#
# Propósito  : rellenar los placeholders de la plantilla y dejar el repositorio
#              en estado "proyecto recién empezado".
# Lo ejecuta : un humano, UNA vez, justo después de copiar o clonar la plantilla.
#              No está en la lista de permisos del agente: instanciar un
#              proyecto vacía el alcance y borra los requisitos, y esa decisión
#              es tuya.
# Equivalente: ./bootstrap.ps1 (canónico en Windows).
#
# Los dos son wrappers de scripts/instanciar.py, que es donde vive la lógica.
# Duplicarla en PowerShell y en bash garantizaba que un día dijeran cosas
# distintas — el mismo motivo por el que los validadores son módulos Python.
#
# Uso        : ./bootstrap.sh --name "mi-proyecto" [--description "Qué hace."]
#                             [--force] [--reset-git] [--no-git] [--dry-run]
# Exit codes : 0 instanciado · 1 falta algo, o ya era un proyecto instanciado.

set -u

cd "$(dirname "$0")" || exit 1

PY=""
for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if [ "$($candidate -c 'print("PYOK")' 2>/dev/null)" = "PYOK" ]; then
      PY="$candidate"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  printf "[FAIL]  No se encontró un Python ejecutable: el arnés lo necesita (ver docs/scripts.md)\n" >&2
  exit 1
fi

exec "$PY" scripts/instanciar.py "$@"
