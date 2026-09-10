"""Los hooks del arnés, en un solo módulo y en las dos plataformas.

Propósito
    Claude Code ejecuta estos hooks; no los ejecuta el agente, así que no los
    puede omitir. Pero para que un hook **bloquee** hay que salir con exit 2 y
    escribir el motivo por stderr: con exit 1 Claude Code muestra el error y
    sigue como si nada. Los hooks del arnés salían con 1, así que en la
    práctica no bloqueaban nada — la sesión cerraba con el verificador en rojo.

    Este módulo existe además para que los hooks funcionen igual en Windows y
    en POSIX. Antes eran PowerShell puro y en WSL o Linux fallaban en cada
    edición.

Eventos
    stop        Antes de cerrar el turno: corre el verificador entero. Si está
                en rojo, bloquea (exit 2) y le dice al agente qué falta.
    post-edit   Tras cada Edit/Write: corre los tests. Si están rotos, bloquea.

Uso
    python scripts/harness_hook.py stop
    python scripts/harness_hook.py post-edit [--tests-dir tests]

    Los invoca `.claude/settings.json`. A mano sirven para probarlos.

Exit codes
    0  todo en orden (o no hay nada que verificar todavía)
    2  bloquea: el motivo va por stderr, que es el canal que Claude Code le
       devuelve al modelo

Nota sobre el bucle
    Claude Code vuelve a llamar al hook `stop` después de que el agente
    reacciona. Si el hook bloqueara siempre, la sesión no cerraría nunca: por
    eso se respeta `stop_hook_active` del JSON de entrada, que avisa de que ya
    venimos de un bloqueo. `stop` tampoco se dispara si interrumpes con Ctrl+C.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BLOQUEA = 2
PASA = 0


def _bloquear(mensaje: str) -> int:
    """El motivo va por stderr: es lo que Claude Code le devuelve al modelo."""
    print(mensaje, file=sys.stderr)
    return BLOQUEA


def _entrada_del_hook() -> dict:
    """El JSON que Claude Code pasa por stdin. Vacío si se ejecuta a mano."""
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        crudo = sys.stdin.read()
    except (OSError, ValueError):
        return {}
    if not crudo.strip():
        return {}
    try:
        datos = json.loads(crudo)
    except json.JSONDecodeError:
        return {}
    return datos if isinstance(datos, dict) else {}


def comando_del_verificador() -> list[str]:
    """El verificador de esta plataforma. Son el mismo, en dos dialectos."""
    if os.name == "nt":
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "./init.ps1",
            "-Quiet",
        ]
    return ["./init.sh", "--quiet"]


def evento_stop() -> int:
    entrada = _entrada_del_hook()
    if entrada.get("stop_hook_active"):
        # Ya venimos de un bloqueo: insistir dejaría la sesión sin poder cerrar.
        return PASA

    try:
        resultado = subprocess.run(
            comando_del_verificador(),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return _bloquear(f"[harness] no se pudo ejecutar el verificador: {exc}")

    if resultado.returncode == 0:
        return PASA

    lineas = [
        linea
        for linea in (resultado.stdout or "").splitlines()
        if linea.startswith("[FAIL]")
    ]
    detalle = "\n".join(lineas) or (resultado.stderr or "").strip()
    return _bloquear(
        "[harness] el verificador está en rojo y la sesión no se cierra así.\n"
        f"{detalle}\n"
        "Resuélvelo y vuelve a intentarlo, o deja constancia del bloqueo en "
        "progress/current.md."
    )


def _contar_tests(tests_dir: str) -> int | None:
    """Cuántos tests hay. None si no se pudieron descubrir."""
    try:
        suite = unittest.TestLoader().discover(tests_dir)
    except Exception:  # noqa: BLE001 — cualquier error de import cuenta igual
        return None
    return suite.countTestCases()


def evento_post_edit(tests_dir: str) -> int:
    ruta = os.path.join(REPO_ROOT, tests_dir)
    if not os.path.isdir(ruta):
        print(f"[harness] no existe {tests_dir}/ — nada que ejecutar")
        return PASA

    total = _contar_tests(ruta)
    if total is None:
        return _bloquear(
            f"[harness] no se pudieron descubrir los tests de {tests_dir}/: "
            f"hay un error de import. Arréglalo antes de seguir editando."
        )
    if total == 0:
        print(f"[harness] 0 tests en {tests_dir}/ — todavía no se verifica nada")
        return PASA

    resultado = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", tests_dir, "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if resultado.returncode == 0:
        print(f"[harness] {total} tests en verde")
        return PASA

    salida = ((resultado.stdout or "") + (resultado.stderr or "")).strip()
    return _bloquear(
        f"[harness] tests ROTOS tras tu edición — arréglalos antes de seguir.\n{salida}"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Hooks del arnés.")
    parser.add_argument("evento", choices=("stop", "post-edit"))
    parser.add_argument(
        "--tests-dir",
        default="tests",
        help="Carpeta de tests para post-edit (por defecto: tests)",
    )
    args = parser.parse_args(argv[1:])

    if args.evento == "stop":
        return evento_stop()
    return evento_post_edit(args.tests_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
