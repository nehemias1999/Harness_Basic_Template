"""Valida feature_list.json contra las reglas del arnés.

Propósito
    Comprobar que el alcance del proyecto está en un estado coherente antes de
    dejar avanzar una sesión: estados válidos, como mucho una feature
    `in_progress`, ids únicos y campos obligatorios presentes.

Quién lo ejecuta
    `init.ps1` e `init.sh` (sección 3). Ambos llaman a este mismo módulo para
    que la lógica de validación no se duplique ni se desincronice entre
    Windows y POSIX. También puedes ejecutarlo a mano.

Uso
    python scripts/validate_feature_list.py [ruta]     # por defecto feature_list.json

Salida
    Una línea por comprobación con prefijo [OK] / [FAIL].

Exit codes
    0  el archivo es válido
    1  el archivo es inválido (o no se pudo leer)
"""
from __future__ import annotations

import json
import sys

VALID_STATUS = {"pending", "in_progress", "done", "blocked"}
REQUIRED_FEATURE_KEYS = ("id", "name", "title", "description", "acceptance", "status")


def validate(path: str) -> list[str]:
    """Devuelve la lista de errores encontrados. Vacía significa válido."""
    errors: list[str] = []

    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return [f"No existe {path}"]
    except json.JSONDecodeError as exc:
        return [f"{path} no es JSON válido: {exc}"]

    if not isinstance(data, dict):
        return [f"{path} debe contener un objeto en la raíz"]

    for key in ("project", "rules", "features"):
        if key not in data:
            errors.append(f"Falta la clave obligatoria \"{key}\"")

    features = data.get("features")
    if features is None:
        return errors
    if not isinstance(features, list):
        return errors + ["\"features\" debe ser un array"]

    allowed = set(data.get("rules", {}).get("valid_status") or VALID_STATUS)
    seen_ids: set[object] = set()

    for index, feature in enumerate(features):
        label = f"feature #{index}"
        if not isinstance(feature, dict):
            errors.append(f"{label} no es un objeto")
            continue

        label = f"feature {feature.get('id', f'#{index}')}"
        for key in REQUIRED_FEATURE_KEYS:
            if key not in feature:
                errors.append(f"{label}: falta el campo \"{key}\"")

        feature_id = feature.get("id")
        if feature_id in seen_ids:
            errors.append(f"{label}: id duplicado")
        seen_ids.add(feature_id)

        status = feature.get("status")
        if status is not None and status not in allowed:
            errors.append(f"{label}: estado inválido \"{status}\"")

        acceptance = feature.get("acceptance")
        if acceptance is not None and (not isinstance(acceptance, list) or not acceptance):
            errors.append(f"{label}: \"acceptance\" debe ser un array con al menos un criterio")

    in_progress = [f for f in features if isinstance(f, dict) and f.get("status") == "in_progress"]
    if data.get("rules", {}).get("one_feature_at_a_time", True) and len(in_progress) > 1:
        names = ", ".join(str(f.get("name", f.get("id"))) for f in in_progress)
        errors.append(f"Hay {len(in_progress)} features en in_progress (máximo 1): {names}")

    return errors


def main(argv: list[str]) -> int:
    path = argv[1] if len(argv) > 1 else "feature_list.json"
    errors = validate(path)

    if errors:
        for error in errors:
            print(f"[FAIL]  {error}")
        return 1

    with open(path, encoding="utf-8") as handle:
        total = len(json.load(handle)["features"])
    print(f"[OK]    {path} válido ({total} features)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
