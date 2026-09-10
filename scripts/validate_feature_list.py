"""Valida feature_list.json contra las reglas del arnés.

Propósito
    Comprobar que el alcance del proyecto está en un estado coherente antes de
    dejar avanzar una sesión: estados válidos, como mucho una feature
    `in_progress`, ids y nombres únicos, prioridad válida, tipos correctos y
    campos obligatorios presentes.

    Este módulo mira solo la FORMA del alcance. La relación de cada feature con
    el requisito del que sale (specs/) la comprueba scripts/validate_requirements.py:
    un error, una causa.

Por qué las reglas del arnés no se leen del JSON
    `rules` describe cómo funciona el arnés, y ese archivo lo puede editar
    cualquier agente con permiso de escritura. Leer de ahí el vocabulario de
    estados o el interruptor de "una feature a la vez" convertía la regla en
    una sugerencia: bastaba con ampliar `valid_status` o poner
    `one_feature_at_a_time: false`. Ahora las reglas viven en el código y lo
    que hace este validador es comprobar que el JSON **coincide** con ellas; si
    alguien las cambió, es un `[FAIL]` explícito.

Quién lo ejecuta
    `init.ps1` e `init.sh` (sección 4). Ambos llaman a este mismo módulo para
    que la lógica de validación no se duplique ni se desincronice entre
    Windows y POSIX. También puedes ejecutarlo a mano.

Uso
    python scripts/validate_feature_list.py [ruta]     # por defecto feature_list.json

Salida
    Una línea por comprobación con prefijo [OK] / [FAIL], y cuando todo está en
    orden, cuál es la siguiente feature según el orden de trabajo.

Exit codes
    0  el archivo es válido
    1  el archivo es inválido (o no se pudo leer)
"""
from __future__ import annotations

import json
import os
import re
import sys

VALID_STATUS = ("draft", "pending", "in_progress", "done", "blocked")
PRIORIDADES = ("critica", "alta", "media", "baja")
REQUIRED_FEATURE_KEYS = (
    "id",
    "name",
    "title",
    "description",
    "spec",
    "prioridad",
    "acceptance",
    "status",
)
NAME_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
SPEC_RE = re.compile(r"^specs/REQ-\d{3}_[a-z0-9]+(?:_[a-z0-9]+)*\.md$")

# Reglas del arnés que el JSON puede declarar pero no cambiar.
REGLAS_FIJAS = {
    "one_feature_at_a_time": True,
    "require_tests_to_close": True,
    "orden_de_trabajo": "prioridad_luego_id",
}


def prioridad_rank(prioridad: object) -> int:
    """0 es lo más crítico. Un valor desconocido va al final."""
    try:
        return PRIORIDADES.index(str(prioridad))
    except ValueError:
        return len(PRIORIDADES)


def orden_de_trabajo(features: list) -> list:
    """Las `pending` en el orden en que hay que hacerlas."""
    pendientes = [f for f in features if isinstance(f, dict) and f.get("status") == "pending"]
    return sorted(pendientes, key=lambda f: (prioridad_rank(f.get("prioridad")), f.get("id", 0)))


def informes_de_cierre(root: str, name: str) -> list[str]:
    """Qué le falta a una feature `done` para estar realmente cerrada.

    El ciclo dice que una feature se cierra tras un APPROVED del reviewer, pero
    hasta ahora ningún código miraba ese veredicto: bastaba con escribir "done"
    en el JSON. Esto no vuelve infalsificable el review —el informe lo escribe
    un agente— pero obliga a que el artefacto exista y quede en git, que es lo
    que permite auditarlo después.
    """
    faltan: list[str] = []
    impl = os.path.join(root, "progress", f"impl_{name}.md")
    review = os.path.join(root, "progress", f"review_{name}.md")

    if not os.path.isfile(impl):
        faltan.append(f"falta el informe del implementer (progress/impl_{name}.md)")

    if not os.path.isfile(review):
        faltan.append(f"falta el informe del reviewer (progress/review_{name}.md)")
        return faltan

    try:
        with open(review, encoding="utf-8") as handle:
            contenido = handle.read()
    except OSError as exc:
        faltan.append(f"no se pudo leer progress/review_{name}.md: {exc}")
        return faltan

    if "CHANGES_REQUESTED" in contenido and "APPROVED" not in contenido:
        faltan.append(f"el reviewer pidió cambios en progress/review_{name}.md")
    elif "APPROVED" not in contenido:
        faltan.append(f"progress/review_{name}.md no dice APPROVED por ningún lado")
    return faltan


def hay_tests(root: str) -> bool:
    """¿Existe al menos un archivo de test? No los ejecuta: eso es del verificador."""
    tests_dir = os.path.join(root, "tests")
    if not os.path.isdir(tests_dir):
        return False
    for _carpeta, _dirs, archivos in os.walk(tests_dir):
        if any(a.startswith("test") and a.endswith(".py") for a in archivos):
            return True
    return False


def _validar_reglas(rules: object) -> list[str]:
    """Comprueba que nadie aflojó las reglas del arnés desde el JSON."""
    errors: list[str] = []
    if not isinstance(rules, dict):
        return ['"rules" debe ser un objeto']

    declarados = rules.get("valid_status")
    if declarados is not None and list(declarados) != list(VALID_STATUS):
        errors.append(
            '"rules.valid_status" no coincide con los estados del arnés '
            f"({', '.join(VALID_STATUS)}). Inventar o quitar estados desde el "
            "JSON no cambia las reglas, solo rompe la validación"
        )

    for clave, esperado in REGLAS_FIJAS.items():
        valor = rules.get(clave)
        if valor is not None and valor != esperado:
            errors.append(
                f'"rules.{clave}" vale {valor!r} y el arnés trabaja con {esperado!r}. '
                f"Esa regla no se desactiva editando el JSON"
            )
    return errors


def _validar_feature(feature: object, index: int, seen_ids: set, seen_names: set) -> list[str]:
    errors: list[str] = []
    if not isinstance(feature, dict):
        return [f"feature #{index} no es un objeto"]

    label = f"feature {feature.get('id', f'#{index}')}"

    for key in REQUIRED_FEATURE_KEYS:
        if key not in feature:
            errors.append(f'{label}: falta el campo "{key}"')

    feature_id = feature.get("id")
    if "id" in feature and (not isinstance(feature_id, int) or feature_id < 1):
        errors.append(f'{label}: "id" debe ser un entero >= 1')
    if feature_id in seen_ids:
        errors.append(f"{label}: id duplicado")
    seen_ids.add(feature_id)

    name = feature.get("name")
    if "name" in feature:
        if not isinstance(name, str) or not NAME_RE.match(name):
            errors.append(f'{label}: "name" debe ser snake_case (vale "{name}")')
        elif name in seen_names:
            # Los informes del implementer y del reviewer se llaman por el
            # `name` de la feature: dos features iguales se pisan el informe.
            errors.append(f'{label}: name duplicado "{name}"')
        else:
            seen_names.add(name)

    for key in ("title", "description"):
        valor = feature.get(key)
        if key in feature and (not isinstance(valor, str) or not valor.strip()):
            errors.append(f'{label}: "{key}" no puede estar vacío')

    spec = feature.get("spec")
    if "spec" in feature and (not isinstance(spec, str) or not SPEC_RE.match(spec)):
        errors.append(
            f'{label}: "spec" debe ser una ruta specs/REQ-00N_nombre.md (vale "{spec}")'
        )

    prioridad = feature.get("prioridad")
    if "prioridad" in feature and prioridad not in PRIORIDADES:
        errors.append(
            f'{label}: prioridad inválida "{prioridad}" (usa: {", ".join(PRIORIDADES)})'
        )

    status = feature.get("status")
    if status is not None and status not in VALID_STATUS:
        errors.append(f'{label}: estado inválido "{status}"')

    acceptance = feature.get("acceptance")
    if acceptance is not None:
        if not isinstance(acceptance, list) or not acceptance:
            errors.append(f'{label}: "acceptance" debe ser un array con al menos un criterio')
        elif any(not isinstance(c, str) or not c.strip() for c in acceptance):
            errors.append(f'{label}: hay criterios de "acceptance" vacíos o que no son texto')

    return errors


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
            errors.append(f'Falta la clave obligatoria "{key}"')

    errors.extend(_validar_reglas(data.get("rules", {})))

    features = data.get("features")
    if features is None:
        return errors
    if not isinstance(features, list):
        return errors + ['"features" debe ser un array']

    seen_ids: set = set()
    seen_names: set = set()
    for index, feature in enumerate(features):
        errors.extend(_validar_feature(feature, index, seen_ids, seen_names))

    in_progress = [f for f in features if isinstance(f, dict) and f.get("status") == "in_progress"]
    if len(in_progress) > 1:
        names = ", ".join(str(f.get("name", f.get("id"))) for f in in_progress)
        errors.append(f"Hay {len(in_progress)} features en in_progress (máximo 1): {names}")

    # require_tests_to_close, hecho ejecutable: cerrar una feature sin un solo
    # test no es "verificado", es "nadie miró". El verificador los ejecuta; aquí
    # solo se comprueba que existan.
    root = os.path.dirname(os.path.abspath(path))
    cerradas = [f for f in features if isinstance(f, dict) and f.get("status") == "done"]
    if cerradas and not hay_tests(root):
        errors.append(
            f"hay {len(cerradas)} feature(s) en done y ni un solo test en tests/: "
            f"una feature no se cierra sin pruebas (rules.require_tests_to_close)"
        )

    # Nadie se autoaprueba: el cierre exige los dos informes del ciclo.
    for feature in cerradas:
        name = feature.get("name")
        if not isinstance(name, str) or not name:
            continue
        for problema in informes_de_cierre(root, name):
            errors.append(f"feature {feature.get('id')} {name} está en done y {problema}")

    return errors


def main(argv: list[str]) -> int:
    path = argv[1] if len(argv) > 1 else "feature_list.json"
    errors = validate(path)

    if errors:
        for error in errors:
            print(f"[FAIL]  {error}")
        return 1

    with open(path, encoding="utf-8") as handle:
        features = json.load(handle)["features"]
    print(f"[OK]    {path} válido ({len(features)} features)")

    cola = orden_de_trabajo(features)
    if cola:
        siguiente = cola[0]
        print(
            f"[OK]    siguiente: feature {siguiente['id']} {siguiente['name']} "
            f"[{siguiente['prioridad']}] — {len(cola)} pendiente(s)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
