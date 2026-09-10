"""Comprueba que el proyecto está configurado antes de dejar trabajar en él.

Propósito
    Un arnés sin configurar es peor que no tener arnés: el reviewer aprueba
    contra `docs/architecture.md`, así que si ese archivo sigue lleno de
    placeholders no hay criterio de calidad y cualquier código que pase los
    tests se considera bueno. Este validador bloquea la sesión hasta que lo
    imprescindible esté puesto.

Qué bloquea (`[FAIL]`)
    - `feature_list.json` todavía con el placeholder de `project`.
    - `docs/architecture.md` sin rellenar (placeholders `<...>` o la nota de
      plantilla intacta) **si ya hay alguna feature fuera de `draft`**.
    - `README.md` con placeholders sin sustituir.

Por qué la arquitectura solo bloquea a veces
    El borrador de `docs/architecture.md` lo escribe el agente `analyst` y lo
    apruebas tú borrando su nota de plantilla. Mientras todas las features
    están en `draft` nadie está programando, así que el borrador sin aprobar es
    un `[WARN]`: si fuera `[FAIL]`, toda la fase de análisis correría en rojo y
    el rojo dejaría de significar algo. En cuanto una feature sale de `draft`
    vuelve a ser bloqueante, que es cuando importa: el reviewer necesita
    criterio justo cuando hay código que juzgar.

Qué solo avisa (`[WARN]`)
    - `docs/architecture.md` en borrador mientras todo esté en `draft`.
    - `description` sin rellenar.
    - `feature_list.json` sin features.
    - `src/` sin módulos todavía.

Caso especial
    Si NADA está configurado, el repositorio es la plantilla recién copiada:
    en vez de escupir todos los fallos, dice qué ejecutar (`bootstrap.ps1`).

Quién lo ejecuta
    `init.ps1` e `init.sh` (sección 3). Ambos usan este mismo módulo para que
    las reglas no se desincronicen entre Windows y POSIX.

Uso
    python scripts/validate_project_setup.py [raiz_del_repo]

Exit codes
    0  configurado (los [WARN] no bloquean)
    1  falta configuración imprescindible
"""
from __future__ import annotations

import json
import os
import re
import sys

PROJECT_PLACEHOLDER = "<TU_PROYECTO>"
DESCRIPTION_PLACEHOLDER = "<DESCRIPCION_PROYECTO>"
TEMPLATE_MARKER = "Este archivo es una plantilla"

# Un placeholder es un token entre ángulos sin espacios raros: <modulo_1>,
# <TU_PROYECTO>, <capa>. No cuenta el HTML de los comentarios ni las flechas.
PLACEHOLDER_RE = re.compile(r"<[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_ .-]{0,40}>")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def find_placeholders(text: str) -> list[str]:
    """Placeholders del documento, ignorando los comentarios HTML de ayuda."""
    return sorted(set(PLACEHOLDER_RE.findall(HTML_COMMENT_RE.sub("", text))))


def check(root: str) -> tuple[list[str], list[str], bool]:
    """Devuelve (fallos, avisos, es_plantilla_sin_instanciar)."""
    fails: list[str] = []
    warns: list[str] = []

    def path(*parts: str) -> str:
        return os.path.join(root, *parts)

    # --- feature_list.json --------------------------------------------------
    project_unset = False
    features_empty = False
    try:
        data = json.loads(_read(path("feature_list.json")))
    except (OSError, json.JSONDecodeError) as exc:
        fails.append(f"No se pudo leer feature_list.json: {exc}")
        data = {}

    project = str(data.get("project", "")).strip()
    if not project or project == PROJECT_PLACEHOLDER:
        project_unset = True
        fails.append(
            'feature_list.json: "project" sigue sin rellenar '
            f'(vale "{project or ""}")'
        )
    else:
        description = str(data.get("description", "")).strip()
        if not description or description.startswith("<"):
            warns.append('feature_list.json: "description" sin rellenar')

    features = data.get("features")
    if isinstance(features, list) and not features:
        features_empty = True
        warns.append("feature_list.json: no hay ninguna feature definida todavía")

    # --- docs/architecture.md ----------------------------------------------
    architecture_unset = False
    try:
        architecture = _read(path("docs", "architecture.md"))
    except OSError as exc:
        fails.append(f"No se pudo leer docs/architecture.md: {exc}")
        architecture = ""

    architecture_issues: list[str] = []
    if architecture:
        placeholders = find_placeholders(architecture)
        if TEMPLATE_MARKER in architecture:
            architecture_unset = True
            architecture_issues.append(
                "docs/architecture.md sigue siendo la plantilla sin rellenar. "
                "Léela y apruébala: python scripts/aprobar.py arquitectura"
            )
        if placeholders:
            architecture_unset = True
            shown = ", ".join(placeholders[:6])
            extra = f" (y {len(placeholders) - 6} más)" if len(placeholders) > 6 else ""
            architecture_issues.append(
                f"docs/architecture.md tiene placeholders sin rellenar: {shown}{extra}"
            )

    # La arquitectura sin aprobar solo bloquea cuando ya hay trabajo real: si
    # todo sigue en `draft` estamos en fase de análisis y el rojo sobraría.
    hay_trabajo = any(
        isinstance(f, dict) and f.get("status") not in (None, "draft")
        for f in (features if isinstance(features, list) else [])
    )
    if architecture_issues:
        if hay_trabajo:
            fails.extend(architecture_issues)
        else:
            warns.extend(architecture_issues)
            warns.append(
                "docs/architecture.md es un borrador sin aprobar; todavía no bloquea "
                "porque no hay ninguna feature fuera de draft"
            )

    # --- README.md ----------------------------------------------------------
    try:
        readme = _read(path("README.md"))
    except OSError as exc:
        fails.append(f"No se pudo leer README.md: {exc}")
        readme = ""

    for placeholder in (PROJECT_PLACEHOLDER, DESCRIPTION_PLACEHOLDER):
        if placeholder in readme:
            fails.append(f"README.md todavía contiene {placeholder}")

    # --- src/ ---------------------------------------------------------------
    src_dir = path("src")
    modules: list[str] = []
    if os.path.isdir(src_dir):
        modules = [f for f in os.listdir(src_dir) if f.endswith(".py") and f != "__init__.py"]
    if not modules:
        warns.append("src/ no tiene módulos todavía")

    pristine = project_unset and architecture_unset and features_empty and not modules
    return fails, warns, pristine


def main(argv: list[str]) -> int:
    root = argv[1] if len(argv) > 1 else "."
    fails, warns, pristine = check(root)

    if pristine:
        print("[FAIL]  Este repositorio es la plantilla del arnés SIN INSTANCIAR.")
        print("[FAIL]  No se puede trabajar en un proyecto que todavía no existe.")
        print("")
        print("        Instáncialo y vuelve a ejecutar el verificador:")
        print("")
        print('          ./bootstrap.ps1 -Name "mi-proyecto" -Description "Qué hace."')
        print("")
        print("        Después pásale tus requisitos en lenguaje normal (/requisitos):")
        print("        el analyst los deja en specs/ y redacta docs/architecture.md,")
        print("        y tú los apruebas. Ver README.md § Arranque rápido.")
        return 1

    for warn in warns:
        print(f"[WARN]  {warn}")
    for fail in fails:
        print(f"[FAIL]  {fail}")

    if fails:
        print("[FAIL]  Configuración incompleta: resuélvela antes de trabajar.")
        return 1

    print("[OK]    Proyecto configurado")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
