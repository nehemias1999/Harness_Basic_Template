# Verificación — Cómo demostrar que el trabajo funciona

> Regla de oro: **el agente no dice "funciona", lo demuestra**.
> Toda feature termina con evidencia ejecutable, no con afirmaciones.

## Niveles de verificación

### Nivel 1 — Tests unitarios (obligatorio)

Toda función pública en `src/` tiene al menos un test en `tests/` que:

1. Cubre el camino feliz.
2. Cubre al menos un camino de error si la función puede fallar.

```bash
python -m unittest discover -s tests -v
```

### Nivel 2 — Test de integración de la interfaz (obligatorio para features de UI/CLI)

Las features que añaden comandos o endpoints se verifican ejecutando el código
real contra un directorio temporal, no contra el estado del desarrollador:

```python
import os
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    env = {**os.environ, "<VAR_DE_ESTADO>": os.path.join(tmp, "state.json")}
    out = subprocess.check_output(
        [sys.executable, "-m", "src.<modulo>", "<comando>", "<arg>"],
        env=env, text=True,
    )
    assert "<fragmento esperado>" in out
```

`sys.executable` en lugar del literal `python3`: así el test usa el mismo
intérprete en Windows y en Linux.

### Nivel 3 — Smoke test manual (opcional pero recomendado)

Antes de cerrar la sesión, ejecuta un flujo end-to-end contra un archivo
temporal y bórralo después.

```powershell
# Windows / PowerShell
$env:<VAR_DE_ESTADO> = "$env:TEMP\smoke_state.json"
python -m src.<modulo> <comando> <arg>
Remove-Item $env:<VAR_DE_ESTADO>
```

```bash
# POSIX
<VAR_DE_ESTADO>="${TMPDIR:-/tmp}/smoke_state.json" python -m src.<modulo> <comando> <arg>
rm "${TMPDIR:-/tmp}/smoke_state.json"
```

## Anti-patrones (no hacer)

- ❌ "He añadido el comando, debería funcionar." → falta test ejecutable.
- ❌ Test que solo verifica que la función no lanza excepción. → tiene que
  comprobar el resultado concreto.
- ❌ `mock` del filesystem. → usa `tempfile.TemporaryDirectory()` real.
- ❌ Rutas absolutas o del usuario en los tests. → siempre temporales.
- ❌ Marcar la feature como `done` sin pasar el verificador.

## Verificación final antes de cerrar

```powershell
./init.ps1          # Windows — debe terminar con [OK] Entorno listo
```

```bash
./init.sh           # POSIX / WSL / CI — mismo resultado
```

Si el verificador está rojo, **no** marques nada como `done`. Anota el bloqueo
en `progress/current.md` y deja la feature en `blocked` en `feature_list.json`.

Ojo con un caso que el verificador distingue a propósito: **0 tests sale `[WARN]`,
no `[OK]`**. Un repo sin tests no está verde, está sin verificar. Ver
`docs/scripts.md`.
