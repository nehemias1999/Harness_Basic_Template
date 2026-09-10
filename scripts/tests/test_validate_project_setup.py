"""Tests de scripts/validate_project_setup.py.

Lo que más importa cubrir aquí es la regla condicional: la arquitectura sin
aprobar solo bloquea cuando ya hay trabajo fuera de `draft`. Si eso se rompe,
o bien la fase de análisis corre en rojo (y el rojo deja de significar algo), o
bien se programa sin criterio de calidad.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import validate_project_setup as vps  # noqa: E402


ARQUITECTURA_LISTA = """# Arquitectura

## Principios

1. Capas claras: cli, dominio, almacenamiento.
2. Sin dependencias externas.
"""

ARQUITECTURA_BORRADOR = """# Arquitectura

> **Este archivo es una plantilla: rellénalo antes de escribir la primera feature.**

## Principios

1. Capas claras.
"""

ARQUITECTURA_CON_HUECOS = """# Arquitectura

## Principios

1. Capas: <modulo_1>, <modulo_2>.
"""


def feature(status: str = "draft") -> dict:
    return {
        "id": 1,
        "name": "una_feature",
        "title": "Una feature",
        "description": "Qué hace.",
        "spec": "specs/REQ-001_un_requisito.md",
        "prioridad": "media",
        "acceptance": ["algo verificable"],
        "status": status,
    }


class ProjectSetupCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.makedirs(os.path.join(self.root, "docs"))
        os.makedirs(os.path.join(self.root, "src"))
        self.escribir("README.md", "# mi-proyecto\n\n> Hace algo.\n")
        self.escribir("docs/architecture.md", ARQUITECTURA_LISTA)
        self.features([])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def escribir(self, rel: str, contenido: str) -> None:
        path = os.path.join(self.root, rel)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(contenido)

    def features(self, features: list, project: str = "mi-proyecto") -> None:
        payload = {
            "project": project,
            "description": "Hace algo.",
            "rules": {},
            "features": features,
        }
        self.escribir("feature_list.json", json.dumps(payload, ensure_ascii=False))

    def check(self):
        return vps.check(self.root)


class TestArquitecturaCondicional(ProjectSetupCase):
    def test_borrador_con_todo_en_draft_solo_avisa(self) -> None:
        self.escribir("docs/architecture.md", ARQUITECTURA_BORRADOR)
        self.features([feature("draft")])
        fails, warns, _ = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(any("borrador sin aprobar" in w for w in warns), warns)

    def test_borrador_con_una_feature_fuera_de_draft_bloquea(self) -> None:
        self.escribir("docs/architecture.md", ARQUITECTURA_BORRADOR)
        self.features([feature("pending")])
        fails, _warns, _ = self.check()
        self.assertTrue(any("plantilla sin rellenar" in f for f in fails), fails)

    def test_placeholders_con_trabajo_empezado_bloquean(self) -> None:
        self.escribir("docs/architecture.md", ARQUITECTURA_CON_HUECOS)
        self.features([feature("in_progress")])
        fails, _warns, _ = self.check()
        self.assertTrue(any("placeholders" in f for f in fails), fails)

    def test_arquitectura_lista_no_dice_nada(self) -> None:
        self.features([feature("done")])
        fails, warns, _ = self.check()
        self.assertEqual(fails, [])
        self.assertFalse([w for w in warns if "architecture" in w], warns)


class TestPlaceholdersDelProyecto(ProjectSetupCase):
    def test_project_sin_rellenar_bloquea(self) -> None:
        self.features([], project="<TU_PROYECTO>")
        fails, _warns, _ = self.check()
        self.assertTrue(any('"project" sigue sin rellenar' in f for f in fails), fails)

    def test_readme_con_placeholder_bloquea(self) -> None:
        self.escribir("README.md", "# <TU_PROYECTO>\n")
        fails, _warns, _ = self.check()
        self.assertTrue(any("README.md todavía contiene" in f for f in fails), fails)


class TestPlantillaSinInstanciar(ProjectSetupCase):
    def test_se_detecta_el_repo_pristino(self) -> None:
        self.features([], project="<TU_PROYECTO>")
        self.escribir("docs/architecture.md", ARQUITECTURA_BORRADOR)
        self.escribir("README.md", "# <TU_PROYECTO>\n\n> <DESCRIPCION_PROYECTO>\n")
        _fails, _warns, pristine = self.check()
        self.assertTrue(pristine)

    def test_un_proyecto_a_medio_configurar_no_es_pristino(self) -> None:
        # Con el nombre puesto ya no es la plantilla: hay que ver los fallos
        # concretos, no el mensaje de "ejecuta bootstrap".
        self.escribir("docs/architecture.md", ARQUITECTURA_BORRADOR)
        _fails, _warns, pristine = self.check()
        self.assertFalse(pristine)


if __name__ == "__main__":
    unittest.main()
