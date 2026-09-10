"""Comprueba que el arnés no se refiera a archivos que no existen.

Propósito
    `CHECKPOINTS.md` C1 pide que toda ruta mencionada en la documentación
    exista de verdad. Hasta ahora eso era prosa: nadie lo comprobaba, y una
    referencia colgante es especialmente cara en este repositorio porque los
    documentos son el mapa con el que los agentes se orientan. Un agente que
    busca `scripts/algo.py` porque `AGENTS.md` lo menciona, y no lo encuentra,
    improvisa.

Qué mira
    Las rutas entre comillas invertidas en los documentos de referencia, y el
    campo `spec` de cada feature de `feature_list.json`.

    Solo cuentan las menciones **con carpeta** (`scripts/x.py`,
    `.claude/agents/y.md`). Un nombre suelto —`storage.py` en una tabla de
    convenciones de nombres, `history.md` en medio de una frase— es un ejemplo
    o una abreviatura, no una ruta, y perseguirlos llenaba la salida de ruido
    hasta que nadie la mirara. También se ignoran los ejemplos con
    placeholders (`progress/impl_<f>.md`) y `requirements.txt`, que es justo lo
    que no debe existir.

Quién lo ejecuta
    `/harness-check` y el CI. **No** el verificador: una referencia rota es
    deuda de documentación, no un motivo para frenar una sesión de trabajo.

Uso
    python scripts/validate_referencias.py [raiz_del_repo]

Exit codes
    0  no hay referencias colgantes
    1  hay al menos una
"""
from __future__ import annotations

import json
import os
import re
import sys

DOCUMENTOS = (
    "CLAUDE.md",
    "AGENTS.md",
    "README.md",
    "CHECKPOINTS.md",
    "docs/scripts.md",
    "docs/architecture.md",
    "docs/conventions.md",
    "docs/verification.md",
)

RUTA_RE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|py|ps1|sh|json|yml|yaml))`")

# Un nombre suelto en prosa ("...y `history.md` se mantiene append-only") o en
# una tabla de ejemplos no es una ruta.
SIN_CARPETA_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

# `requirements.txt` aparece en CHECKPOINTS.md como algo que NO debe existir.
IGNORADAS = {"requirements.txt"}


def _leer(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def check(root: str) -> list[str]:
    fallos: list[str] = []

    for documento in DOCUMENTOS:
        ruta_doc = os.path.join(root, documento)
        if not os.path.isfile(ruta_doc):
            fallos.append(f"{documento}: no existe, y es uno de los documentos de referencia")
            continue

        for mencion in sorted(set(RUTA_RE.findall(_leer(ruta_doc)))):
            if mencion in IGNORADAS or "<" in mencion:
                continue
            if SIN_CARPETA_RE.match(mencion):
                continue
            if os.path.exists(os.path.join(root, mencion)):
                continue
            fallos.append(f"{documento} menciona `{mencion}`, que no existe")

    # El puntero de cada feature a su requisito.
    try:
        datos = json.loads(_leer(os.path.join(root, "feature_list.json")))
    except (OSError, json.JSONDecodeError):
        return fallos

    for feature in datos.get("features") or []:
        if not isinstance(feature, dict):
            continue
        spec = feature.get("spec")
        if spec and not os.path.exists(os.path.join(root, spec)):
            fallos.append(f"feature {feature.get('id')} apunta a `{spec}`, que no existe")

    return fallos


def main(argv: list[str]) -> int:
    root = argv[1] if len(argv) > 1 else "."
    fallos = check(root)

    for fallo in fallos:
        print(f"[FAIL]  {fallo}")
    if fallos:
        print("[FAIL]  Hay referencias colgantes: un mapa que miente desorienta")
        print("        más que no tener mapa.")
        return 1

    print(f"[OK]    {len(DOCUMENTOS)} documentos revisados, sin referencias colgantes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
