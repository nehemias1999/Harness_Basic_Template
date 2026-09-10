"""Comprueba que nadie trabaja sobre un requisito que nadie aprobó.

Propósito
    La aprobación de un requisito no es un "dale" en el chat: es
    `estado: aprobado` en el frontmatter de `specs/REQ-00N_*.md`, versionado en
    git, más el paso de sus features de `draft` a `pending`. Este validador
    comprueba que las dos cosas concuerdan y bloquea la sesión si alguien
    avanzó sobre un requisito que sigue en análisis.

    Es la contracara del otro gate del arnés: `validate_project_setup.py` exige
    que exista criterio de calidad, este exige que exista alcance aprobado.

Qué bloquea (`[FAIL]`)
    - Una feature con `status` distinto de `draft` cuyo spec no está aprobado.
    - Hay módulos en `src/` y ningún requisito aprobado: se empezó a programar
      antes de definir qué había que hacer.
    - Una feature sin campo `spec`, o apuntando a un archivo que no existe.
    - Un spec `aprobado` con preguntas abiertas sin responder (`- [ ]`): la
      regla de "no asumir nada", hecha ejecutable.
    - Un spec `aprobado` sin `aprobado_el`, o sin ninguna feature que lo
      referencie.
    - Una feature con prioridad MÁS ALTA que la de su requisito. Bajarla es
      legal (una parte accesoria); subirla es una contradicción silenciosa.
    - Nombre de archivo fuera de `REQ-00N_nombre_snake_case.md`, `id` duplicado,
      `id` del frontmatter que no coincide con el del nombre, `estado` o
      `prioridad` inválidos.

Qué solo avisa (`[WARN]`)
    - Todavía no existe `specs/`, o no hay ningún requisito.
    - Hay requisitos en `draft` esperando el OK del humano.
    - Un spec aprobado cuyas features siguen todas en `draft` (aprobación a
      medias: falta terminar `/aprobar-requisitos`).
    - Hay una feature `in_progress` de menor prioridad que algo encolado. El
      arnés avisa del adelantamiento; decidir si se interrumpe es del humano.

Quién lo ejecuta
    `init.ps1` e `init.sh` (sección 5). Ambos usan este mismo módulo para que
    las reglas no se desincronicen entre Windows y POSIX. También a mano.

Uso
    python scripts/validate_requirements.py [raiz_del_repo]

Exit codes
    0  la trazabilidad requisito -> feature es coherente (los [WARN] no bloquean)
    1  hay trabajo sobre algo sin aprobar, o la trazabilidad está rota
"""
from __future__ import annotations

import json
import os
import re
import sys

SPEC_DIR = "specs"
SPEC_FILE_RE = re.compile(r"^REQ-(\d{3})_[a-z0-9]+(?:_[a-z0-9]+)*\.md$")
SPEC_POINTER_RE = re.compile(r"^specs/REQ-\d{3}_[a-z0-9]+(?:_[a-z0-9]+)*\.md$")
OPEN_QUESTION_RE = re.compile(r"^\s*-\s*\[ \]", re.MULTILINE)

VALID_ESTADO = ("draft", "aprobado", "descartado")
PRIORIDADES = ("critica", "alta", "media", "baja")
REQUIRED_KEYS = ("id", "titulo", "estado", "prioridad")

# Todo lo que no es `draft` significa que alguien ya trabajó sobre la feature.
# `blocked` cuenta: para bloquearse hubo que empezar.
WORKED_STATUS = ("pending", "in_progress", "done", "blocked")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Frontmatter YAML plano (`clave: valor`). None si no hay o no cierra.

    Deliberadamente mínimo: el arnés no tiene dependencias externas, así que no
    hay PyYAML. A cambio, la plantilla del spec obliga a claves planas.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.split(" #")[0].strip().strip("\"'")
        if key and key not in fields:
            fields[key] = value
    return None


def prioridad_rank(prioridad: str) -> int:
    """0 es lo más crítico. Un valor desconocido va al final."""
    try:
        return PRIORIDADES.index(prioridad)
    except ValueError:
        return len(PRIORIDADES)


def load_specs(root: str) -> tuple[dict[str, dict], list[str]]:
    """Devuelve ({ruta relativa: datos del spec}, errores de formato)."""
    specs: dict[str, dict] = {}
    fails: list[str] = []
    spec_dir = os.path.join(root, SPEC_DIR)

    if not os.path.isdir(spec_dir):
        return specs, fails

    seen_ids: dict[str, str] = {}
    for name in sorted(os.listdir(spec_dir)):
        if not name.endswith(".md") or name.startswith("_"):
            continue

        rel = f"{SPEC_DIR}/{name}"
        match = SPEC_FILE_RE.match(name)
        if not match:
            fails.append(
                f"{rel}: el nombre no sigue el formato REQ-00N_nombre_snake_case.md"
            )
            continue

        fields = parse_frontmatter(_read(os.path.join(spec_dir, name)))
        if fields is None:
            fails.append(f"{rel}: no tiene frontmatter, o no está cerrado con ---")
            continue

        missing = [key for key in REQUIRED_KEYS if not fields.get(key)]
        if missing:
            fails.append(f"{rel}: falta en el frontmatter: {', '.join(missing)}")
            continue

        spec_id = fields["id"]
        if spec_id != f"REQ-{match.group(1)}":
            fails.append(
                f"{rel}: el id del frontmatter ({spec_id}) no coincide con el "
                f"del nombre del archivo (REQ-{match.group(1)})"
            )
        if spec_id in seen_ids:
            fails.append(f"{rel}: id {spec_id} duplicado (ya lo usa {seen_ids[spec_id]})")
        seen_ids[spec_id] = rel

        if fields["estado"] not in VALID_ESTADO:
            fails.append(
                f"{rel}: estado inválido \"{fields['estado']}\" "
                f"(usa: {', '.join(VALID_ESTADO)})"
            )
        if fields["prioridad"] not in PRIORIDADES:
            fails.append(
                f"{rel}: prioridad inválida \"{fields['prioridad']}\" "
                f"(usa: {', '.join(PRIORIDADES)})"
            )

        fields["_ruta"] = rel
        fields["_preguntas_abiertas"] = len(
            OPEN_QUESTION_RE.findall(_read(os.path.join(spec_dir, name)))
        )
        specs[rel] = fields

    return specs, fails


def check(root: str) -> tuple[list[str], list[str]]:
    """Devuelve (fallos, avisos)."""
    fails: list[str] = []
    warns: list[str] = []

    specs, spec_fails = load_specs(root)
    fails.extend(spec_fails)

    if not os.path.isdir(os.path.join(root, SPEC_DIR)):
        warns.append(
            "todavía no existe specs/: el proyecto no tiene alcance aprobado, "
            "así que no hay nada que desarrollar. Empieza por /requisitos"
        )
    elif not specs:
        warns.append(
            "specs/ no tiene ningún requisito todavía: no hay alcance aprobado, "
            "así que no hay nada que desarrollar. Empieza por /requisitos"
        )

    # --- feature_list.json --------------------------------------------------
    try:
        data = json.loads(_read(os.path.join(root, "feature_list.json")))
    except (OSError, json.JSONDecodeError):
        # No duplicamos el diagnóstico: de la forma del archivo se ocupa la
        # sección anterior del verificador.
        return ["No se pudo leer feature_list.json (ver sección 4)"], warns

    features = data.get("features")
    if not isinstance(features, list):
        return ["\"features\" no es un array (ver sección 4)"], warns

    referenced: dict[str, list[dict]] = {}
    for feature in features:
        if not isinstance(feature, dict):
            continue

        label = f"feature {feature.get('id', '?')} {feature.get('name', '')}".strip()
        status = feature.get("status")
        spec_path = feature.get("spec")

        if not spec_path:
            fails.append(
                f"{label}: no tiene campo \"spec\". Toda feature sale de un "
                f"requisito de specs/"
            )
            continue
        if not SPEC_POINTER_RE.match(str(spec_path)):
            fails.append(
                f"{label}: \"spec\" debe ser una ruta specs/REQ-00N_nombre.md "
                f"(vale \"{spec_path}\")"
            )
            continue

        spec = specs.get(spec_path)
        if spec is None:
            fails.append(f"{label}: apunta a {spec_path}, que no existe")
            continue

        referenced.setdefault(spec_path, []).append(feature)

        if status in WORKED_STATUS and spec["estado"] != "aprobado":
            fails.append(
                f"{label}: status \"{status}\" pero {spec_path} sigue en estado "
                f"\"{spec['estado']}\" (nadie aprobó ese requisito)"
            )

        prioridad = feature.get("prioridad")
        if prioridad in PRIORIDADES and spec["prioridad"] in PRIORIDADES:
            if prioridad_rank(prioridad) < prioridad_rank(spec["prioridad"]):
                fails.append(
                    f"{label}: prioridad \"{prioridad}\" es más alta que la de su "
                    f"requisito (\"{spec['prioridad']}\"). Una feature puede bajarla, "
                    f"no subirla: cambia la del requisito si de verdad es más urgente"
                )

    # --- coherencia por requisito -------------------------------------------
    aprobados = 0
    en_draft: list[str] = []
    for rel, spec in sorted(specs.items()):
        estado = spec["estado"]
        suyas = referenced.get(rel, [])

        if estado == "draft":
            en_draft.append(f"{spec['id']} [{spec['prioridad']}]")
            continue
        if estado != "aprobado":
            continue

        aprobados += 1
        if not spec.get("aprobado_el"):
            fails.append(f"{rel}: está aprobado pero le falta la fecha en aprobado_el")
        if spec["_preguntas_abiertas"]:
            fails.append(
                f"{rel}: está aprobado con {spec['_preguntas_abiertas']} pregunta(s) "
                f"abierta(s) sin responder. Un requisito no se aprueba con huecos: "
                f"respóndelas y marca la casilla, o vuelve el spec a draft"
            )
        if not suyas:
            fails.append(
                f"{rel}: está aprobado pero ninguna feature lo referencia. "
                f"Deriva sus features o vuélvelo a draft"
            )
        elif all(f.get("status") == "draft" for f in suyas):
            warns.append(
                f"{rel}: aprobado pero sus {len(suyas)} feature(s) siguen en draft "
                f"(aprobación a medias: termina /aprobar-requisitos)"
            )

    if en_draft:
        warns.append(
            f"{len(en_draft)} requisito(s) en draft esperando tu OK: "
            f"{', '.join(en_draft)}"
        )

    # --- no se programa sin requisitos --------------------------------------
    src_dir = os.path.join(root, "src")
    modules = []
    if os.path.isdir(src_dir):
        modules = [f for f in os.listdir(src_dir) if f.endswith(".py") and f != "__init__.py"]
    if modules and aprobados == 0:
        fails.append(
            f"hay {len(modules)} módulo(s) en src/ y ningún requisito aprobado: "
            f"se empezó a programar antes de definir qué había que hacer"
        )

    # --- adelantamiento por prioridad ---------------------------------------
    en_curso = [f for f in features if isinstance(f, dict) and f.get("status") == "in_progress"]
    encoladas = [f for f in features if isinstance(f, dict) and f.get("status") == "pending"]
    for feature in en_curso:
        rank = prioridad_rank(str(feature.get("prioridad")))
        urgentes = [f for f in encoladas if prioridad_rank(str(f.get("prioridad"))) < rank]
        if urgentes:
            ids = ", ".join(str(f.get("id")) for f in urgentes)
            warns.append(
                f"feature {feature.get('id')} {feature.get('name')} "
                f"({feature.get('prioridad')}) está in_progress y hay trabajo de más "
                f"prioridad encolado (id {ids}): termínala, o pásala a blocked con "
                f"motivo antes de seguir"
            )

    return fails, warns


def main(argv: list[str]) -> int:
    root = argv[1] if len(argv) > 1 else "."
    fails, warns = check(root)

    for warn in warns:
        print(f"[WARN]  {warn}")
    for fail in fails:
        print(f"[FAIL]  {fail}")

    if fails:
        print("[FAIL]  Hay trabajo sobre requisitos sin aprobar, o la trazabilidad")
        print("        está rota: resuélvelo antes de avanzar.")
        return 1

    specs, _ = load_specs(root)
    aprobados = sum(1 for s in specs.values() if s.get("estado") == "aprobado")
    try:
        total_features = len(json.loads(_read(os.path.join(root, "feature_list.json")))["features"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        total_features = 0
    print(
        f"[OK]    {len(specs)} requisitos ({aprobados} aprobados), "
        f"{total_features} features trazadas"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
