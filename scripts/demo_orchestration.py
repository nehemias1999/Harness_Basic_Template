"""Demo ejecutable del patrón Líder-Trabajador con escritura en disco.

Propósito
    Ilustrar la regla anti-teléfono-descompuesto del arnés: cada "trabajador"
    analiza un módulo de `src/`, escribe su informe completo en
    `progress/explore_<modulo>.md` y devuelve **solo la ruta**. Por el canal de
    comunicación (aquí stdout, en una sesión real el chat) no circula el
    contenido, solo referencias ligeras.

    Es la versión determinista y sin IA del patrón que ejecutan los subagentes
    reales definidos en `.claude/agents/`.

Quién lo ejecuta
    Un humano que quiere entender o demostrar el patrón, o un agente al que se
    le pide un mapa rápido de `src/`. No forma parte de la verificación: no lo
    llama `init.ps1` / `init.sh` ni ningún hook.

Parámetros
    --src DIR       Carpeta a analizar (por defecto: src)
    --out DIR       Dónde escribir los informes (por defecto: progress)
    --dry-run       No escribe nada; solo lista lo que escribiría

Uso
    python scripts/demo_orchestration.py
    python scripts/demo_orchestration.py --src src --out progress --dry-run

Salida
    Una línea por módulo con la referencia al informe, del mismo formato que
    devuelve un subagente:  done -> progress/explore_<modulo>.md

Exit codes
    0  terminó bien (incluso si no había módulos que analizar)
    1  la carpeta indicada en --src no existe
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
from datetime import datetime


def analyze(path: str) -> dict[str, object]:
    """Extrae métricas estructurales de un módulo Python sin importarlo."""
    with open(path, encoding="utf-8") as handle:
        source = handle.read()

    tree = ast.parse(source, filename=path)
    lines = source.splitlines()

    functions: list[str] = []
    classes: list[str] = []
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            args = [a.arg for a in node.args.args]
            functions.append(f"{node.name}({', '.join(args)})")
        elif isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            suffix = f"({', '.join(bases)})" if bases else ""
            classes.append(f"{node.name}{suffix}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])

    return {
        "lines": len(lines),
        "code_lines": len([ln for ln in lines if ln.strip() and not ln.strip().startswith("#")]),
        "docstring": ast.get_docstring(tree) or "",
        "functions": functions,
        "classes": classes,
        "imports": sorted(imports),
    }


def render(module: str, path: str, data: dict[str, object]) -> str:
    """Compone el informe en el formato estándar de `progress/explore_*.md`."""
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- `{item}`" for item in items) if items else "_ninguna_"

    return f"""# Exploración — {module}

- **Archivo:** `{path}`
- **Generado:** {datetime.now().isoformat(timespec="seconds")}
- **Por:** `scripts/demo_orchestration.py`

## Propósito declarado

{data["docstring"].strip() or "_el módulo no tiene docstring_"}

## Métricas

| Métrica            | Valor |
|--------------------|-------|
| Líneas totales     | {data["lines"]} |
| Líneas de código   | {data["code_lines"]} |
| Funciones          | {len(data["functions"])} |
| Clases             | {len(data["classes"])} |

## Funciones

{bullets(data["functions"])}

## Clases

{bullets(data["classes"])}

## Dependencias

{bullets(data["imports"])}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Escribe un informe por módulo de src/ y devuelve solo las rutas.",
    )
    parser.add_argument("--src", default="src", help="carpeta a analizar")
    parser.add_argument("--out", default="progress", help="carpeta donde escribir los informes")
    parser.add_argument("--dry-run", action="store_true", help="no escribe, solo lista")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.src):
        print(f"[FAIL]  No existe la carpeta {args.src}", file=sys.stderr)
        return 1

    modules = sorted(
        name for name in os.listdir(args.src)
        if name.endswith(".py") and name != "__init__.py"
    )

    if not modules:
        print(f"[WARN]  No hay módulos que analizar en {args.src}/", file=sys.stderr)
        return 0

    if not args.dry_run:
        os.makedirs(args.out, exist_ok=True)

    for filename in modules:
        module = filename[:-3]
        source_path = os.path.join(args.src, filename)
        report_path = os.path.join(args.out, f"explore_{module}.md").replace(os.sep, "/")

        if not args.dry_run:
            report = render(module, source_path.replace(os.sep, "/"), analyze(source_path))
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write(report)

        # Esto es lo único que sale por el canal: la referencia, nunca el contenido.
        print(f"done -> {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
