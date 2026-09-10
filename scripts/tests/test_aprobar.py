"""Tests de scripts/aprobar.py.

La firma toca cuatro cosas a la vez y a medio camino el repositorio queda
incoherente. Lo que más importa cubrir es que no firme cuando no debe, y que
cuando se niega **no haya escrito nada**.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aprobar  # noqa: E402
import validate_requirements as vr  # noqa: E402


SPEC = """---
id: {spec_id}
titulo: Un requisito
estado: {estado}
prioridad: alta
creado: 2026-09-01
actualizado: 2026-09-01
aprobado_el:
aprobado_hash:
ronda: 2
---

# {spec_id} — Un requisito

## 5. Criterios de aceptación

1. Hace algo verificable.

## 6. Supuestos y preguntas abiertas

{preguntas}

## 8. Bitácora de revisiones

| ronda | fecha | qué cambió | a pedido de |
|-------|-------|-----------|-------------|
| 1 | 2026-09-01 | versión inicial | humano |
"""

ARQUITECTURA_BORRADOR = """# Arquitectura

> **Este archivo es una plantilla: rellénalo antes de escribir la primera feature.** — BORRADOR sin aprobar

## Principios

1. Tres capas: cli, dominio, almacenamiento.
"""


class AprobarCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.makedirs(os.path.join(self.root, "specs"))
        os.makedirs(os.path.join(self.root, "docs"))
        self.escribir("docs/architecture.md", ARQUITECTURA_BORRADOR)
        self.spec("REQ-001", "req_uno")
        self.features(
            [
                self.feature(1, "una", "specs/REQ-001_req_uno.md"),
                self.feature(2, "otra", "specs/REQ-001_req_uno.md"),
            ]
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- helpers ---------------------------------------------------------
    def escribir(self, rel: str, contenido: str) -> None:
        with open(os.path.join(self.root, rel), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(contenido)

    def leer(self, rel: str) -> str:
        with open(os.path.join(self.root, rel), encoding="utf-8") as handle:
            return handle.read()

    def spec(self, spec_id: str, nombre: str, estado: str = "draft",
             preguntas: str = "- [x] **P1:** respondida") -> str:
        rel = f"specs/{spec_id}_{nombre}.md"
        self.escribir(rel, SPEC.format(spec_id=spec_id, estado=estado, preguntas=preguntas))
        return rel

    def feature(self, fid: int, nombre: str, spec: str, status: str = "draft") -> dict:
        return {
            "id": fid, "name": nombre, "title": nombre, "description": "x",
            "spec": spec, "prioridad": "alta", "acceptance": ["algo"], "status": status,
        }

    def features(self, lista: list[dict]) -> None:
        self.escribir(
            "feature_list.json",
            json.dumps({"project": "p", "rules": {}, "features": lista}, ensure_ascii=False),
        )

    def estado_de_features(self) -> list[str]:
        return [f["status"] for f in json.loads(self.leer("feature_list.json"))["features"]]

    def correr(self, *objetivos: str, dry_run: bool = False) -> tuple[int, str]:
        salida = io.StringIO()
        with redirect_stdout(salida):
            code = aprobar.Aprobador(self.root, list(objetivos), dry_run, por="tester").ejecutar()
        return code, salida.getvalue()


class TestFirma(AprobarCase):
    def test_firma_por_id(self) -> None:
        code, _ = self.correr("1")
        self.assertEqual(code, 0)

        contenido = self.leer("specs/REQ-001_req_uno.md")
        self.assertIn("estado: aprobado", contenido)
        self.assertIn("aprobado_hash: ", contenido)
        self.assertNotIn("aprobado_hash:\n", contenido)
        self.assertEqual(self.estado_de_features(), ["pending", "pending"])

    def test_la_huella_escrita_es_la_que_valida(self) -> None:
        self.correr("1")
        contenido = self.leer("specs/REQ-001_req_uno.md")
        campos, _ = vr.parse_frontmatter(contenido)
        self.assertEqual(campos["aprobado_hash"], vr.huella_del_spec(contenido))

    def test_el_resultado_pasa_el_validador(self) -> None:
        self.correr("1")
        fails, _warns = vr.check(self.root)
        self.assertEqual(fails, [])

    def test_acepta_cualquier_forma_del_id(self) -> None:
        for texto in ("1", "001", "REQ-001", "req-1"):
            with self.subTest(texto=texto):
                self.assertEqual(aprobar.normalizar_id(texto), "REQ-001")

    def test_todos_firma_los_draft(self) -> None:
        self.spec("REQ-002", "req_dos")
        self.spec("REQ-003", "req_tres", estado="aprobado")
        code, salida = self.correr("todos")
        self.assertEqual(code, 0)
        self.assertIn("REQ-001", salida)
        self.assertIn("REQ-002", salida)
        self.assertNotIn("REQ-003 ->", salida)

    def test_agrega_la_fila_de_la_bitacora_pegada_a_la_tabla(self) -> None:
        self.correr("1")
        lineas = [l for l in self.leer("specs/REQ-001_req_uno.md").splitlines() if l.startswith("|")]
        self.assertEqual(len(lineas), 4)  # cabecera, separador, la vieja y la nueva
        self.assertIn("tester", lineas[-1])

    def test_dos_veces_el_mismo_id_no_lo_firma_dos_veces(self) -> None:
        code, salida = self.correr("1", "001")
        self.assertEqual(code, 0)
        self.assertEqual(salida.count("REQ-001 -> aprobado"), 1)


class TestSeNiega(AprobarCase):
    """Y cuando se niega, no escribe nada."""

    def test_con_preguntas_abiertas(self) -> None:
        self.spec("REQ-001", "req_uno", preguntas="- [ ] **P1:** ¿esto cómo era?")
        antes = self.leer("specs/REQ-001_req_uno.md")

        code, salida = self.correr("1")
        self.assertEqual(code, 1)
        self.assertIn("pregunta(s) sin responder", salida)
        self.assertEqual(self.leer("specs/REQ-001_req_uno.md"), antes)
        self.assertEqual(self.estado_de_features(), ["draft", "draft"])

    def test_ya_aprobado(self) -> None:
        self.spec("REQ-001", "req_uno", estado="aprobado")
        code, salida = self.correr("1")
        self.assertEqual(code, 1)
        self.assertIn("ya estaba aprobado", salida)

    def test_id_inexistente(self) -> None:
        code, salida = self.correr("99")
        self.assertEqual(code, 1)
        self.assertIn("no existe ningún requisito", salida)

    def test_palabra_que_no_es_nada(self) -> None:
        code, salida = self.correr("dale")
        self.assertEqual(code, 1)
        self.assertIn("no entiendo", salida)

    def test_un_id_malo_no_firma_el_bueno(self) -> None:
        # Todo o nada: firmar la mitad deja un estado que nadie pidió.
        self.spec("REQ-002", "req_dos")
        code, _salida = self.correr("1", "99")
        self.assertEqual(code, 1)
        self.assertIn("estado: draft", self.leer("specs/REQ-001_req_uno.md"))

    def test_spec_mal_formado_frena_todo(self) -> None:
        self.escribir("specs/REQ-009_roto.md", "sin frontmatter\n")
        code, salida = self.correr("1")
        self.assertEqual(code, 1)
        self.assertIn("arreglalos antes de aprobar", salida)


class TestArquitectura(AprobarCase):
    def test_se_nombra_aparte(self) -> None:
        self.correr("1")
        # Firmar un requisito no toca la arquitectura.
        self.assertIn(aprobar.MARCADOR_PLANTILLA, self.leer("docs/architecture.md"))

    def test_firma_la_arquitectura(self) -> None:
        code, _ = self.correr("1", "arquitectura")
        self.assertEqual(code, 0)
        self.assertNotIn(aprobar.MARCADOR_PLANTILLA, self.leer("docs/architecture.md"))

    def test_con_huecos_no_firma_nada(self) -> None:
        self.escribir(
            "docs/architecture.md",
            ARQUITECTURA_BORRADOR + "\n2. Capas: <modulo_1>, <modulo_2>.\n",
        )
        code, salida = self.correr("1", "arquitectura")
        self.assertEqual(code, 1)
        self.assertIn("placeholders sin rellenar", salida)
        # Y el requisito tampoco se firmó.
        self.assertIn("estado: draft", self.leer("specs/REQ-001_req_uno.md"))

    def test_arquitectura_ya_aprobada_solo_avisa(self) -> None:
        self.escribir("docs/architecture.md", "# Arquitectura\n\n1. Tres capas.\n")
        code, salida = self.correr("arquitectura")
        self.assertEqual(code, 0)
        self.assertIn("ya estaba aprobada", salida)


class TestSimulacro(AprobarCase):
    def test_dry_run_no_escribe(self) -> None:
        antes_spec = self.leer("specs/REQ-001_req_uno.md")
        antes_json = self.leer("feature_list.json")

        code, salida = self.correr("todos", "arquitectura", dry_run=True)
        self.assertEqual(code, 0)
        self.assertIn("simulado", salida)
        self.assertEqual(self.leer("specs/REQ-001_req_uno.md"), antes_spec)
        self.assertEqual(self.leer("feature_list.json"), antes_json)
        self.assertIn(aprobar.MARCADOR_PLANTILLA, self.leer("docs/architecture.md"))


class TestNadaQueAprobar(AprobarCase):
    def test_sin_drafts_avisa_y_no_falla(self) -> None:
        self.spec("REQ-001", "req_uno", estado="aprobado")
        code, salida = self.correr("todos")
        self.assertEqual(code, 0)
        self.assertIn("no hay nada que aprobar", salida)


if __name__ == "__main__":
    unittest.main()
