"""Firma requisitos: el paso mecánico de la aprobación.

Propósito
    Convertir tu OK en estado verificable, sin que dependa de que un agente
    recuerde siete pasos en el orden correcto. Aprobar significa tocar cuatro
    cosas a la vez —el estado del spec, la fecha, la huella del contenido y el
    estado de sus features— y a medio camino el repositorio queda incoherente.
    Eso es trabajo de un script, no de la prosa de un `.md`.

    Lo que NO automatiza es la decisión. Vos nombrás qué se aprueba; el script
    se niega si lo que nombraste tiene preguntas sin responder o ya estaba
    aprobado.

Uso
    python scripts/aprobar.py 1 2            # REQ-001 y REQ-002
    python scripts/aprobar.py REQ-003        # da igual cómo escribas el id
    python scripts/aprobar.py todos          # todos los que estén en draft
    python scripts/aprobar.py 1 arquitectura # y además firma docs/architecture.md
    python scripts/aprobar.py todos --dry-run

Qué hace por cada requisito nombrado
    1. `estado: draft` -> `aprobado`, con `aprobado_el` y `actualizado` de hoy.
    2. Calcula y escribe `aprobado_hash`: la huella del texto aprobado.
    3. Añade la fila de la bitácora (§8).
    4. Pasa sus features de `draft` a `pending`.

La palabra `arquitectura`
    Borra la nota de plantilla de `docs/architecture.md`, que es el acto por el
    que ese documento queda aprobado. Va aparte y hay que nombrarla a propósito:
    es el criterio contra el que el reviewer juzga todo el código, y aprobarlo
    de rebote junto a un requisito sería exactamente el descuido que el arnés
    intenta evitar.

Exit codes
    0  firmado (o simulado) · 1 no se pudo: el motivo va impreso
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validate_requirements as vr  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TODOS = "todos"
ARQUITECTURA = "arquitectura"
MARCADOR_PLANTILLA = "Este archivo es una plantilla"
ID_RE = re.compile(r"^(?:req-)?0*(\d{1,3})$", re.IGNORECASE)
# Ojo con `\s*$`: se come el salto de línea final y la fila nueva queda
# separada por un blanco, que en markdown parte la tabla en dos.
FILA_BITACORA_RE = re.compile(r"^\|.*\|[ 	]*$", re.MULTILINE)


def ok(mensaje: str) -> None:
    print(f"[OK]    {mensaje}")


def warn(mensaje: str) -> None:
    print(f"[WARN]  {mensaje}")


def fail(mensaje: str) -> None:
    print(f"[FAIL]  {mensaje}")


def normalizar_id(texto: str) -> str | None:
    """`1`, `001`, `REQ-001`, `req-1` -> `REQ-001`. None si no es un id."""
    match = ID_RE.match(texto.strip())
    if not match:
        return None
    return f"REQ-{int(match.group(1)):03d}"


def quien_firma(root: str) -> str:
    """El nombre de quien aprueba, para la bitácora."""
    try:
        salida = subprocess.run(
            ["git", "config", "user.name"],
            cwd=root, capture_output=True, text=True, encoding="utf-8",
        )
        nombre = salida.stdout.strip()
    except OSError:
        nombre = ""
    return nombre or "humano"


class Aprobador:
    def __init__(self, root: str, objetivos: list[str], dry_run: bool, por: str = "") -> None:
        self.root = root
        self.objetivos = objetivos
        self.dry_run = dry_run
        self.por = por or quien_firma(root)
        self.hoy = datetime.date.today().isoformat()
        self.specs, self.errores_de_formato = vr.load_specs(root)

    # -- utilidades ------------------------------------------------------
    def leer(self, rel: str) -> str:
        with open(os.path.join(self.root, rel), encoding="utf-8") as handle:
            return handle.read()

    def escribir(self, rel: str, contenido: str) -> None:
        if self.dry_run:
            return
        with open(os.path.join(self.root, rel), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(contenido)

    def sufijo(self) -> str:
        return " (simulado)" if self.dry_run else ""

    # -- resolución de lo que se pidió ------------------------------------
    def resolver(self) -> tuple[list[str], bool, list[str]]:
        """Devuelve (rutas de specs a firmar, si toca arquitectura, errores)."""
        errores: list[str] = []
        arquitectura = False
        pedidos: list[str] = []

        for objetivo in self.objetivos:
            plano = objetivo.strip().lower().rstrip(",")
            if plano == ARQUITECTURA:
                arquitectura = True
                continue
            if plano == TODOS:
                pedidos.extend(
                    rel for rel, spec in sorted(self.specs.items())
                    if spec["estado"] == vr.DRAFT
                )
                continue

            req_id = normalizar_id(plano)
            if not req_id:
                errores.append(
                    f'no entiendo "{objetivo}": usa un id (1, 001, REQ-001), '
                    f'"{TODOS}" o "{ARQUITECTURA}"'
                )
                continue

            rutas = [rel for rel, spec in self.specs.items() if spec["id"] == req_id]
            if not rutas:
                errores.append(f"{req_id}: no existe ningún requisito con ese id")
                continue
            pedidos.extend(rutas)

        # Sin duplicados, en orden estable.
        vistos: list[str] = []
        for ruta in pedidos:
            if ruta not in vistos:
                vistos.append(ruta)
        return vistos, arquitectura, errores

    def comprobar(self, rutas: list[str]) -> list[str]:
        """Motivos por los que algo de lo pedido no se puede firmar."""
        problemas: list[str] = []
        for rel in rutas:
            spec = self.specs[rel]
            if spec["estado"] == "aprobado":
                problemas.append(f"{spec['id']}: ya estaba aprobado")
            elif spec["estado"] != vr.DRAFT:
                problemas.append(
                    f"{spec['id']}: está en estado \"{spec['estado']}\", no en draft"
                )
            if spec["_preguntas_abiertas"]:
                problemas.append(
                    f"{spec['id']}: tiene {spec['_preguntas_abiertas']} pregunta(s) sin "
                    f"responder. Respondelas y marcá la casilla antes de aprobar"
                )
        return problemas

    # -- firma -------------------------------------------------------------
    def firmar(self, rel: str) -> None:
        spec = self.specs[rel]
        contenido = self.leer(rel)
        cabecera, _, cuerpo = contenido.partition("\n---\n")

        campos = []
        for linea in cabecera.splitlines():
            clave = linea.split(":", 1)[0].strip()
            if clave == "estado":
                campos.append("estado: aprobado")
            elif clave == "aprobado_el":
                campos.append(f"aprobado_el: {self.hoy}")
            elif clave == "actualizado":
                campos.append(f"actualizado: {self.hoy}")
            elif clave == "aprobado_hash":
                continue  # se recalcula abajo
            else:
                campos.append(linea)
        if not any(c.startswith("aprobado_el:") for c in campos):
            campos.append(f"aprobado_el: {self.hoy}")

        cuerpo = self.agregar_bitacora(cuerpo, spec.get("ronda", "?"))
        nuevo = "\n".join(campos) + "\n---\n" + cuerpo

        # La huella ignora el frontmatter y la bitácora, así que da igual el
        # orden; se calcula sobre el texto ya final para que no haya sorpresas.
        huella = vr.huella_del_spec(nuevo)
        campos.append(f"aprobado_hash: {huella}")
        nuevo = "\n".join(campos) + "\n---\n" + cuerpo

        self.escribir(rel, nuevo)
        ok(f"{spec['id']} -> aprobado el {self.hoy}, huella {huella}{self.sufijo()}")

    def agregar_bitacora(self, cuerpo: str, ronda: str) -> str:
        fila = f"| {ronda} | {self.hoy} | aprobado | {self.por} |"
        marca = re.search(r"^##\s*8\..*$", cuerpo, re.MULTILINE)
        if not marca:
            return cuerpo.rstrip("\n") + f"\n\n## 8. Bitácora de revisiones\n\n{fila}\n"
        seccion = cuerpo[marca.end():]
        filas = list(FILA_BITACORA_RE.finditer(seccion))
        if not filas:
            return cuerpo.rstrip("\n") + f"\n{fila}\n"
        corte = marca.end() + filas[-1].end()
        return cuerpo[:corte] + f"\n{fila}" + cuerpo[corte:]

    def promover_features(self, rutas: list[str]) -> int:
        ruta_json = os.path.join(self.root, "feature_list.json")
        with open(ruta_json, encoding="utf-8") as handle:
            datos = json.load(handle)

        promovidas = 0
        for feature in datos.get("features") or []:
            if not isinstance(feature, dict):
                continue
            if feature.get("spec") in rutas and feature.get("status") == vr.DRAFT:
                feature["status"] = "pending"
                promovidas += 1
                ok(
                    f"feature {feature.get('id')} {feature.get('name')} "
                    f"-> pending{self.sufijo()}"
                )

        if promovidas and not self.dry_run:
            with open(ruta_json, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(datos, indent=2, ensure_ascii=False) + "\n")
        return promovidas

    def comprobar_arquitectura(self) -> list[str]:
        try:
            contenido = self.leer("docs/architecture.md")
        except OSError as exc:
            return [f"no se pudo leer docs/architecture.md: {exc}"]

        if MARCADOR_PLANTILLA not in contenido:
            return []

        huecos = placeholders_pendientes(contenido)
        if huecos:
            return [
                f"docs/architecture.md todavía tiene placeholders sin rellenar "
                f"({', '.join(huecos[:4])}). No se aprueba a medias: devolvéselo "
                f"al analyst"
            ]
        return []

    def firmar_arquitectura(self) -> None:
        rel = "docs/architecture.md"
        contenido = self.leer(rel)

        if MARCADOR_PLANTILLA not in contenido:
            warn("docs/architecture.md ya estaba aprobada, no había nota que quitar")
            return

        lineas = [l for l in contenido.splitlines() if MARCADOR_PLANTILLA not in l]
        self.escribir(rel, "\n".join(lineas).strip() + "\n")
        ok(f"docs/architecture.md -> aprobada (se quitó la nota de plantilla){self.sufijo()}")

    # -- orquestación -------------------------------------------------------
    def ejecutar(self) -> int:
        if self.errores_de_formato:
            for error in self.errores_de_formato:
                fail(error)
            fail("Hay specs mal formados: arreglalos antes de aprobar nada.")
            return 1

        rutas, arquitectura, errores = self.resolver()
        for error in errores:
            fail(error)
        if errores:
            return 1

        if not rutas and not arquitectura:
            warn("no hay nada que aprobar: ningún requisito en draft")
            return 0

        problemas = self.comprobar(rutas)
        if arquitectura:
            problemas.extend(self.comprobar_arquitectura())
        for problema in problemas:
            fail(problema)
        if problemas:
            # Todo o nada: firmar la mitad deja el repositorio en un estado que
            # el verificador marca en rojo y que nadie pidió.
            fail("No se firmó nada.")
            return 1

        modo = " (simulacro: no se escribe nada)" if self.dry_run else ""
        print(f"-- Firmando {len(rutas)} requisito(s){modo} ----------------------")

        for rel in rutas:
            self.firmar(rel)
        promovidas = self.promover_features(rutas)

        if arquitectura:
            self.firmar_arquitectura()

        print("")
        if rutas and not promovidas:
            warn(
                "ningún requisito tenía features en draft: derivalas con "
                "/requisitos antes de seguir, o el verificador lo va a decir"
            )
        ok(f"{len(rutas)} requisito(s) firmados, {promovidas} feature(s) en pending")
        print("        Siguiente: ejecutá el verificador y después /next-feature.")
        return 0


def placeholders_pendientes(texto: str) -> list[str]:
    """Los `<huecos>` que queden, ignorando los comentarios HTML de ayuda."""
    import validate_project_setup as vps

    return vps.find_placeholders(texto)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Firma los requisitos que le nombres."
    )
    parser.add_argument(
        "objetivos",
        nargs="+",
        metavar="ID",
        help='ids (1, 001, REQ-001), "todos", o "arquitectura"',
    )
    parser.add_argument("--dry-run", action="store_true", help="No escribe nada")
    parser.add_argument("--por", default="", help="Quién aprueba (para la bitácora)")
    parser.add_argument("--root", default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv[1:])

    return Aprobador(args.root, args.objetivos, args.dry_run, args.por).ejecutar()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
