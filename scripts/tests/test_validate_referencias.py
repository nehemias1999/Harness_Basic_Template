"""Tests de scripts/validate_referencias.py.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import validate_referencias as vref  # noqa: E402


class ReferenciasCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.makedirs(os.path.join(self.root, "docs"))
        os.makedirs(os.path.join(self.root, "scripts"))
        for documento in vref.DOCUMENTOS:
            self.escribir(documento, "# vacío\n")
        self.escribir("feature_list.json", json.dumps({"features": []}))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def escribir(self, rel: str, contenido: str) -> None:
        ruta = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(contenido)

    def check(self) -> list[str]:
        return vref.check(self.root)


class TestReferencias(ReferenciasCase):
    def test_repo_limpio(self) -> None:
        self.assertEqual(self.check(), [])

    def test_ruta_que_no_existe(self) -> None:
        self.escribir("AGENTS.md", "Mirá `scripts/no_existe.py` para esto.\n")
        fallos = self.check()
        self.assertTrue(any("scripts/no_existe.py" in f for f in fallos), fallos)

    def test_ruta_que_si_existe(self) -> None:
        self.escribir("scripts/existe.py", "# hola\n")
        self.escribir("AGENTS.md", "Mirá `scripts/existe.py` para esto.\n")
        self.assertEqual(self.check(), [])

    def test_un_nombre_suelto_es_un_ejemplo_no_una_ruta(self) -> None:
        # `storage.py` en una tabla de convenciones de nombres no es una
        # referencia: perseguirlo llenaba la salida de ruido.
        self.escribir("docs/conventions.md", "| Módulos | snake_case | `storage.py` |\n")
        self.assertEqual(self.check(), [])

    def test_los_placeholders_se_ignoran(self) -> None:
        self.escribir("AGENTS.md", "El informe va a `progress/impl_<feature>.md`.\n")
        self.assertEqual(self.check(), [])

    def test_requirements_txt_no_cuenta(self) -> None:
        self.escribir("CHECKPOINTS.md", "- [ ] No existe `requirements.txt` con contenido.\n")
        self.assertEqual(self.check(), [])

    def test_documento_de_referencia_ausente(self) -> None:
        os.remove(os.path.join(self.root, "AGENTS.md"))
        fallos = self.check()
        self.assertTrue(any("AGENTS.md" in f for f in fallos), fallos)

    def test_puntero_spec_colgante(self) -> None:
        self.escribir(
            "feature_list.json",
            json.dumps({"features": [{"id": 1, "spec": "specs/REQ-001_x.md"}]}),
        )
        fallos = self.check()
        self.assertTrue(any("REQ-001_x.md" in f for f in fallos), fallos)

    def test_puntero_spec_valido(self) -> None:
        self.escribir("specs/REQ-001_x.md", "---\nid: REQ-001\n---\n")
        self.escribir(
            "feature_list.json",
            json.dumps({"features": [{"id": 1, "spec": "specs/REQ-001_x.md"}]}),
        )
        self.assertEqual(self.check(), [])

    def test_feature_list_ilegible_no_revienta(self) -> None:
        self.escribir("feature_list.json", "{ roto")
        self.assertEqual(self.check(), [])


class TestElRepoDeVerdad(unittest.TestCase):
    def test_este_repositorio_no_tiene_referencias_colgantes(self) -> None:
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.assertEqual(vref.check(raiz), [])


if __name__ == "__main__":
    unittest.main()
