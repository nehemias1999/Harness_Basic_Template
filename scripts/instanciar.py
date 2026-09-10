"""Instancia un proyecto nuevo a partir de la plantilla del arnés.

Propósito
    Rellenar los placeholders, vaciar el alcance heredado y dejar el
    repositorio en estado "proyecto recién empezado". Lo ejecuta un humano UNA
    vez, justo después de copiar o clonar la plantilla.

Por qué está en Python y no en cada shell
    `bootstrap.ps1` y `bootstrap.sh` son dos puertas a esta misma casa. La
    lógica vive aquí por el mismo motivo que la de los validadores: son ~200
    líneas de decisiones sobre qué borrar y qué conservar, y mantenerlas
    duplicadas en PowerShell y en bash garantiza que un día digan cosas
    distintas. Los wrappers solo traducen argumentos.

Qué hace
    1. Se planta si el repositorio ya es un proyecto instanciado (salvo --force).
    2. `feature_list.json`: escribe project/description y vacía `features`.
    3. Sustituye `<TU_PROYECTO>` y `<DESCRIPCION_PROYECTO>` en README.md y en
       docs/{architecture,conventions,verification}.md.
    4. Resetea `progress/current.md` y `progress/history.md` a su plantilla.
    5. Borra informes residuales y los requisitos del proyecto anterior.
    6. Deja el repositorio git listo y desconecta el `origin` de la plantilla.

Lo que NO hace
    Definir el alcance. El borrador de `docs/architecture.md` y los requisitos
    los redacta el agente `analyst` (`/requisitos`), pero aprobarlos es tuyo, y
    hasta que lo hagas el verificador no se pone verde.

Uso
    python scripts/instanciar.py --name mi-proyecto [--description "Qué hace."]
                                 [--force] [--reset-git] [--no-git] [--dry-run]

Exit codes
    0  instanciado · 1 faltan archivos de la plantilla, o ya era un proyecto
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROJECT_PLACEHOLDER = "<TU_PROYECTO>"
DESCRIPTION_PLACEHOLDER = "<DESCRIPCION_PROYECTO>"

REQUERIDOS = ("feature_list.json", "README.md", "progress/current.md", "progress/history.md")

# Lista explícita a propósito: `docs/scripts.md` y `CHECKPOINTS.md` *hablan* de
# los placeholders, así que sustituirlos ahí destrozaría su documentación.
CON_PLACEHOLDERS = (
    "README.md",
    "docs/architecture.md",
    "docs/conventions.md",
    "docs/verification.md",
)

INFORME_RE = re.compile(r"^(explore|impl|review|intake)_.*\.md$")
SPEC_RE = re.compile(r"^REQ-\d{3}_.*\.md$")

URL_DE_LA_PLANTILLA = "Harness_Basic_Template"

PLANTILLA_CURRENT = """# Sesión actual

> Este archivo se vacía al cerrar cada sesión y se mueve a `history.md`.
> Mientras trabajas, **mantenlo actualizado en tiempo real**, no al final.

- **Feature en curso:** _ninguna_
- **Inicio:** _—_
- **Agente:** _—_

## Plan

_Describe en 3-5 bullets qué vas a hacer antes de tocar código._

## Bitácora

_Anota aquí cada paso significativo: archivos creados, decisiones, bloqueos._

- ...

## Próximo paso

_Si la sesión se interrumpe, lo primero que debe hacer la siguiente sesión._
"""

PLANTILLA_HISTORY = """# Historial de sesiones

> Bitácora **append-only**. Al cerrar cada sesión se añade al final el resumen
> que vivía en `progress/current.md`. Nunca se edita ni se borra una entrada
> anterior: este archivo es la memoria del proyecto entre context windows.

Formato de cada entrada:

```markdown
## <YYYY-MM-DD> — feature <id> <name>

- **Agente:** <quién trabajó>
- **Resultado:** done | blocked
- **Archivos tocados:** <lista>
- **Verificación:** <salida resumida de init>
- **Notas:** <decisiones o bloqueos relevantes para la siguiente sesión>
```

---

_Sin sesiones registradas todavía._
"""


def ok(mensaje: str) -> None:
    print(f"[OK]    {mensaje}")


def warn(mensaje: str) -> None:
    print(f"[WARN]  {mensaje}")


def fail(mensaje: str) -> None:
    print(f"[FAIL]  {mensaje}")


class Instanciador:
    def __init__(self, root: str, args: argparse.Namespace) -> None:
        self.root = root
        self.args = args

    # -- utilidades ------------------------------------------------------
    def ruta(self, *partes: str) -> str:
        return os.path.join(self.root, *partes)

    def leer(self, rel: str) -> str:
        with open(self.ruta(rel), encoding="utf-8") as handle:
            return handle.read()

    def escribir(self, rel: str, contenido: str) -> None:
        if self.args.dry_run:
            return
        with open(self.ruta(rel), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(contenido)

    def borrar(self, rel: str) -> None:
        if self.args.dry_run:
            return
        os.remove(self.ruta(rel))

    def anuncio(self, mensaje: str) -> None:
        ok(f"{mensaje}{' (simulado)' if self.args.dry_run else ''}")

    # -- pasos -----------------------------------------------------------
    def comprobar_plantilla(self) -> bool:
        faltan = [f for f in REQUERIDOS if not os.path.isfile(self.ruta(f))]
        for archivo in faltan:
            fail(f"Falta un archivo de la plantilla: {archivo}")
        return not faltan

    def ya_es_un_proyecto(self) -> list[str]:
        """Razones por las que esto no parece la plantilla recién copiada."""
        razones: list[str] = []
        try:
            project = str(json.loads(self.leer("feature_list.json")).get("project", "")).strip()
        except (OSError, json.JSONDecodeError):
            project = ""
        if project and project != PROJECT_PLACEHOLDER:
            razones.append(f"feature_list.json ya es del proyecto '{project}'")

        specs = self.requisitos_heredados()
        if specs:
            razones.append(f"hay {len(specs)} requisito(s) en specs/")
        return razones

    def requisitos_heredados(self) -> list[str]:
        spec_dir = self.ruta("specs")
        if not os.path.isdir(spec_dir):
            return []
        return sorted(f for f in os.listdir(spec_dir) if SPEC_RE.match(f))

    def reescribir_feature_list(self) -> None:
        datos = json.loads(self.leer("feature_list.json"))
        datos["project"] = self.args.name
        if self.args.description:
            datos["description"] = self.args.description
        datos["features"] = []
        self.escribir(
            "feature_list.json",
            json.dumps(datos, indent=2, ensure_ascii=False) + "\n",
        )
        self.anuncio(f"feature_list.json -> project '{self.args.name}', 0 features")

    def sustituir_placeholders(self) -> None:
        for rel in CON_PLACEHOLDERS:
            if not os.path.isfile(self.ruta(rel)):
                continue
            contenido = self.leer(rel)
            nuevo = contenido.replace(PROJECT_PLACEHOLDER, self.args.name)
            if self.args.description:
                nuevo = nuevo.replace(DESCRIPTION_PLACEHOLDER, self.args.description)
            if nuevo == contenido:
                continue
            self.escribir(rel, nuevo)
            self.anuncio(f"{rel} -> placeholders sustituidos")

    def resetear_progress(self) -> None:
        historial = self.leer("progress/history.md")
        tiene_entradas = "## " in historial.split("---", 2)[-1]
        if tiene_entradas and not self.args.force:
            warn(
                "progress/history.md tiene entradas de sesiones anteriores. "
                "Usa --force para reiniciarlo."
            )
        else:
            self.escribir("progress/history.md", PLANTILLA_HISTORY)
            self.anuncio("progress/history.md -> reiniciado")

        self.escribir("progress/current.md", PLANTILLA_CURRENT)
        self.anuncio("progress/current.md -> reiniciado")

    def limpiar_informes(self) -> None:
        progress = self.ruta("progress")
        if not os.path.isdir(progress):
            return
        for archivo in sorted(os.listdir(progress)):
            if INFORME_RE.match(archivo):
                self.borrar(os.path.join("progress", archivo))
                self.anuncio(f"progress/{archivo} -> borrado")

    def preparar_specs(self) -> None:
        spec_dir = self.ruta("specs")
        if not os.path.isdir(spec_dir):
            if not self.args.dry_run:
                os.makedirs(spec_dir)
            self.anuncio("specs/ -> creada")

        # Los requisitos son del proyecto anterior. Si se quedan, el paso
        # anterior vacía `features` y quedan specs aprobados sin ninguna
        # feature que los referencie: el verificador nace en rojo.
        for archivo in self.requisitos_heredados():
            self.borrar(os.path.join("specs", archivo))
            self.anuncio(f"specs/{archivo} -> borrado")

    # -- git -------------------------------------------------------------
    def git(self, *argumentos: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *argumentos],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def configurar_git(self) -> str | None:
        """Devuelve una nota final para el humano, si hace falta.

        Dos motivos para tocar git aquí: el reviewer identifica los archivos
        tocados comparando contra el historial —sin repo trabaja a ciegas—, y
        si clonaste la plantilla, `origin` sigue apuntando a ella y tu primer
        push mandaría el proyecto nuevo al repositorio del template.
        """
        if self.args.no_git:
            warn("git: omitido por --no-git (el reviewer compara contra el historial)")
            return None
        if shutil.which("git") is None:
            warn("git no está instalado: el reviewer no podrá comparar contra el historial")
            return None
        if self.args.dry_run:
            ok("git: sin cambios (simulado)")
            return None

        tiene_git = os.path.isdir(self.ruta(".git"))

        if tiene_git and self.args.reset_git:
            shutil.rmtree(self.ruta(".git"))
            ok(".git heredado de la plantilla -> borrado")
            tiene_git = False

        if not tiene_git:
            self.git("init", "--quiet")
            self.git("add", "-A")
            if not self.git("config", "user.email").stdout.strip():
                self.git("config", "user.email", "harness@localhost")
                self.git("config", "user.name", "Harness bootstrap")
                warn("git: no había identidad configurada, se puso una local provisional")
            commit = self.git("commit", "--quiet", "-m", f"chore: instancia el arnés para {self.args.name}")
            if commit.returncode == 0:
                ok("git: repositorio inicializado con el commit base del arnés")
            else:
                warn("git: el commit base falló; hazlo a mano antes de trabajar")
            return "Añade el remote de tu proyecto: git remote add origin <url>"

        origin = self.git("remote", "get-url", "origin").stdout.strip()
        if origin and URL_DE_LA_PLANTILLA in origin:
            self.git("remote", "remove", "origin")
            ok(f"git: remote 'origin' -> {origin} (era la plantilla, se desconectó)")
            return "Añade el remote de tu proyecto: git remote add origin <url>"
        if origin:
            ok(f"git: remote 'origin' -> {origin} (no es la plantilla, se deja como está)")
        else:
            ok("git: repositorio existente sin remote, nada que desconectar")

        if self.git("log", "--oneline", "-1").returncode == 0 and not self.args.reset_git:
            warn("git: conservas el historial de la plantilla. Usa --reset-git para empezar de cero.")
        return None

    # -- orquestación -----------------------------------------------------
    def ejecutar(self) -> int:
        if not self.comprobar_plantilla():
            return 1

        razones = self.ya_es_un_proyecto()
        if razones and not self.args.force:
            fail("Este repositorio ya es un proyecto instanciado:")
            for razon in razones:
                print(f"          - {razon}")
            print("")
            print("        Instanciar vacía las features, borra los requisitos de specs/")
            print("        y reinicia progress/. Sobre un proyecto vivo eso no se recupera.")
            print("")
            print("        Si de verdad quieres volver a instanciarlo, dilo explícitamente:")
            print("")
            print(f'          --name "{self.args.name}" --force')
            print("")
            print("        Y si solo querías ver qué haría: añade --dry-run.")
            return 1

        modo = " (simulacro: no se escribe nada)" if self.args.dry_run else ""
        print(f"-- Instanciando proyecto '{self.args.name}'{modo} ----------------------")

        self.reescribir_feature_list()
        self.sustituir_placeholders()
        self.resetear_progress()
        self.limpiar_informes()
        self.preparar_specs()
        nota = self.configurar_git()

        print("")
        print("-- Siguiente paso (a mano) ----------------------------")
        print("  1. Abre Claude Code en la raíz y pásale tus requisitos en lenguaje normal")
        print("     (o usa /requisitos). El analyst los deja en specs/ y redacta un")
        print("     borrador de docs/architecture.md.")
        print("  2. Léelos y pídele los cambios que hagan falta: cada vuelta es una ronda.")
        print("  3. Cuando estés conforme: /aprobar-requisitos. Ahí las features pasan a")
        print("     pending y se aprueba la arquitectura.")
        print("  4. Ejecuta el verificador — debe quedar verde.")
        print("  5. /next-feature para arrancar el desarrollo.")
        if nota:
            print(f"  6. {nota}")
        print("")
        ok(f"Proyecto '{self.args.name}' instanciado{modo}")
        return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Instancia un proyecto nuevo a partir de la plantilla del arnés."
    )
    parser.add_argument("--name", required=True, help="Nombre del proyecto nuevo")
    parser.add_argument("--description", default="", help="Una línea describiendo el proyecto")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Instancia aunque el repositorio ya sea un proyecto, y reinicia history.md",
    )
    parser.add_argument(
        "--reset-git",
        action="store_true",
        help="Borra el .git heredado de la plantilla y empieza un historial nuevo",
    )
    parser.add_argument("--no-git", action="store_true", help="No toca git en absoluto")
    parser.add_argument(
        "--dry-run", action="store_true", help="Lista los cambios sin aplicarlos"
    )
    parser.add_argument("--root", default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv[1:])

    if not args.name.strip():
        fail("--name no puede estar vacío")
        return 1

    return Instanciador(args.root, args).ejecutar()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
