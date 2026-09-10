"""Tests de scripts/instanciar.py.

El bootstrap es el script más destructivo del arnés: vacía el alcance, borra
los requisitos y puede borrar `.git`. Lo que más importa cubrir es que **se
plante** cuando el repositorio ya es un proyecto, y que el simulacro no
escriba nada.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import instanciar  # noqa: E402


PLANTILLA_FEATURE_LIST = {
    "project": "<TU_PROYECTO>",
    "description": "<Una línea describiendo qué hace el proyecto.>",
    "rules": {"one_feature_at_a_time": True},
    "features": [{"id": 1, "name": "heredada", "status": "done"}],
}


class InstanciarCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        for carpeta in ("progress", "docs", "specs"):
            os.makedirs(os.path.join(self.root, carpeta))
        self.escribir("feature_list.json", json.dumps(PLANTILLA_FEATURE_LIST, ensure_ascii=False))
        self.escribir("README.md", "# <TU_PROYECTO>\n\n> <DESCRIPCION_PROYECTO>\n")
        self.escribir("docs/architecture.md", "# Arquitectura de <TU_PROYECTO>\n")
        self.escribir("progress/current.md", "# Sesión actual\n\nbasura de la sesión anterior\n")
        self.escribir("progress/history.md", "# Historial de sesiones\n\n---\n\n_Sin sesiones._\n")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- helpers ---------------------------------------------------------
    def escribir(self, rel: str, contenido: str) -> None:
        with open(os.path.join(self.root, rel), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(contenido)

    def leer(self, rel: str) -> str:
        with open(os.path.join(self.root, rel), encoding="utf-8") as handle:
            return handle.read()

    def existe(self, rel: str) -> bool:
        return os.path.exists(os.path.join(self.root, rel))

    def correr(self, **kwargs) -> tuple[int, str]:
        opciones = {
            "name": "mi-proyecto",
            "description": "Hace algo.",
            "force": False,
            "reset_git": False,
            "no_git": True,
            "dry_run": False,
        }
        opciones.update(kwargs)
        args = argparse.Namespace(**opciones)
        salida = io.StringIO()
        with redirect_stdout(salida):
            code = instanciar.Instanciador(self.root, args).ejecutar()
        return code, salida.getvalue()


class TestInstanciacion(InstanciarCase):
    def test_camino_feliz(self) -> None:
        code, _salida = self.correr()
        self.assertEqual(code, 0)

        datos = json.loads(self.leer("feature_list.json"))
        self.assertEqual(datos["project"], "mi-proyecto")
        self.assertEqual(datos["description"], "Hace algo.")
        self.assertEqual(datos["features"], [])
        self.assertIn("mi-proyecto", self.leer("README.md"))
        self.assertNotIn("<TU_PROYECTO>", self.leer("README.md"))
        self.assertIn("Feature en curso", self.leer("progress/current.md"))

    def test_sin_description_conserva_el_placeholder(self) -> None:
        self.correr(description="")
        self.assertIn("<DESCRIPCION_PROYECTO>", self.leer("README.md"))

    def test_falta_un_archivo_de_la_plantilla(self) -> None:
        os.remove(os.path.join(self.root, "progress", "history.md"))
        code, salida = self.correr()
        self.assertEqual(code, 1)
        self.assertIn("Falta un archivo de la plantilla", salida)


class TestNoDestruirUnProyectoVivo(InstanciarCase):
    """El guardarraíl que importa."""

    def test_se_planta_si_ya_tiene_nombre(self) -> None:
        datos = json.loads(self.leer("feature_list.json"))
        datos["project"] = "proyecto-vivo"
        self.escribir("feature_list.json", json.dumps(datos, ensure_ascii=False))

        code, salida = self.correr()
        self.assertEqual(code, 1)
        self.assertIn("ya es un proyecto instanciado", salida)
        # Y no tocó nada.
        self.assertEqual(json.loads(self.leer("feature_list.json"))["project"], "proyecto-vivo")

    def test_se_planta_si_hay_requisitos(self) -> None:
        self.escribir("specs/REQ-001_algo.md", "---\nid: REQ-001\n---\n")
        code, salida = self.correr()
        self.assertEqual(code, 1)
        self.assertIn("1 requisito(s) en specs/", salida)
        self.assertTrue(self.existe("specs/REQ-001_algo.md"))

    def test_con_force_sigue_adelante(self) -> None:
        self.escribir("specs/REQ-001_algo.md", "---\nid: REQ-001\n---\n")
        code, _salida = self.correr(force=True)
        self.assertEqual(code, 0)
        self.assertFalse(self.existe("specs/REQ-001_algo.md"))

    def test_history_con_entradas_no_se_pisa_sin_force(self) -> None:
        self.escribir(
            "progress/history.md",
            "# Historial\n\n---\n\n## 2026-01-01 — feature 1 algo\n\n- Resultado: done\n",
        )
        _code, salida = self.correr()
        self.assertIn("tiene entradas de sesiones anteriores", salida)
        self.assertIn("2026-01-01", self.leer("progress/history.md"))


class TestSimulacro(InstanciarCase):
    def test_dry_run_no_escribe_nada(self) -> None:
        antes = self.leer("feature_list.json")
        self.escribir("specs/REQ-001_algo.md", "---\nid: REQ-001\n---\n")

        code, salida = self.correr(dry_run=True, force=True)
        self.assertEqual(code, 0)
        self.assertIn("simulado", salida)
        self.assertEqual(self.leer("feature_list.json"), antes)
        self.assertTrue(self.existe("specs/REQ-001_algo.md"))


class TestLimpieza(InstanciarCase):
    def test_borra_los_informes_de_la_sesion_anterior(self) -> None:
        for nombre in ("impl_algo.md", "review_algo.md", "explore_x.md", "intake_r1.md"):
            self.escribir(f"progress/{nombre}", "informe viejo\n")
        self.escribir("progress/notas_mias.md", "esto no es un informe\n")

        self.correr()

        for nombre in ("impl_algo.md", "review_algo.md", "explore_x.md", "intake_r1.md"):
            self.assertFalse(self.existe(f"progress/{nombre}"), nombre)
        self.assertTrue(self.existe("progress/notas_mias.md"))

    def test_crea_specs_si_no_existe(self) -> None:
        os.rmdir(os.path.join(self.root, "specs"))
        self.correr()
        self.assertTrue(os.path.isdir(os.path.join(self.root, "specs")))

    def test_conserva_la_plantilla_de_specs(self) -> None:
        self.escribir("specs/_plantilla_req.md", "plantilla\n")
        self.correr()
        self.assertTrue(self.existe("specs/_plantilla_req.md"))


if __name__ == "__main__":
    unittest.main()
