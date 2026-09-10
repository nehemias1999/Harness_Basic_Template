"""Tests de scripts/harness_hook.py.

Lo que hay que proteger aquí es un detalle fácil de perder en una refactor y
difícil de notar: **el exit code**. Un hook que sale con 1 no bloquea nada, y
un arnés cuyos hooks no bloquean da una sensación de control que no existe.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import harness_hook as hh  # noqa: E402


class TestEventoStop(unittest.TestCase):
    def _correr(self, returncode: int, stdout: str = "", entrada: dict | None = None):
        resultado = mock.Mock(returncode=returncode, stdout=stdout, stderr="")
        err = io.StringIO()
        with mock.patch.object(hh.subprocess, "run", return_value=resultado) as run, \
             mock.patch.object(hh, "_entrada_del_hook", return_value=entrada or {}), \
             redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = hh.evento_stop()
        return code, err.getvalue(), run

    def test_verificador_verde_no_bloquea(self) -> None:
        code, _err, _run = self._correr(0)
        self.assertEqual(code, hh.PASA)

    def test_verificador_rojo_bloquea_con_exit_2(self) -> None:
        code, err, _run = self._correr(1, "[OK]    algo\n[FAIL]  falta aprobar REQ-001\n")
        self.assertEqual(code, 2)
        self.assertIn("falta aprobar REQ-001", err)

    def test_el_motivo_va_por_stderr(self) -> None:
        # Es el canal que Claude Code le devuelve al modelo: por stdout el
        # bloqueo sería mudo.
        _code, err, _run = self._correr(1, "[FAIL]  algo\n")
        self.assertTrue(err.strip())

    def test_no_insiste_si_ya_venia_de_un_bloqueo(self) -> None:
        code, _err, run = self._correr(1, "[FAIL]  algo\n", entrada={"stop_hook_active": True})
        self.assertEqual(code, hh.PASA)
        run.assert_not_called()

    def test_si_el_verificador_no_arranca_bloquea(self) -> None:
        err = io.StringIO()
        with mock.patch.object(hh.subprocess, "run", side_effect=OSError("no existe")), \
             mock.patch.object(hh, "_entrada_del_hook", return_value={}), \
             redirect_stderr(err):
            code = hh.evento_stop()
        self.assertEqual(code, 2)
        self.assertIn("no se pudo ejecutar el verificador", err.getvalue())


class TestComandoDelVerificador(unittest.TestCase):
    def test_windows_usa_el_ps1(self) -> None:
        with mock.patch.object(hh.os, "name", "nt"):
            self.assertIn("./init.ps1", hh.comando_del_verificador())

    def test_posix_usa_el_sh(self) -> None:
        with mock.patch.object(hh.os, "name", "posix"):
            comando = hh.comando_del_verificador()
        self.assertEqual(comando[0], "./init.sh")
        self.assertIn("--quiet", comando)


class TestEventoPostEdit(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self._patch = mock.patch.object(hh, "REPO_ROOT", self.root)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()

    def _tests_dir(self) -> str:
        ruta = os.path.join(self.root, "tests")
        os.makedirs(ruta, exist_ok=True)
        return ruta

    def _correr(self) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = hh.evento_post_edit("tests")
        return code, out.getvalue(), err.getvalue()

    def test_sin_carpeta_de_tests_no_bloquea(self) -> None:
        code, out, _err = self._correr()
        self.assertEqual(code, hh.PASA)
        self.assertIn("nada que ejecutar", out)

    def test_cero_tests_no_bloquea(self) -> None:
        self._tests_dir()
        code, out, _err = self._correr()
        self.assertEqual(code, hh.PASA)
        self.assertIn("0 tests", out)

    def test_tests_verdes_no_bloquean(self) -> None:
        ruta = self._tests_dir()
        with open(os.path.join(ruta, "test_ok.py"), "w", encoding="utf-8") as handle:
            handle.write(
                "import unittest\n"
                "class T(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertTrue(True)\n"
            )
        code, out, _err = self._correr()
        self.assertEqual(code, hh.PASA)
        self.assertIn("verde", out)

    def test_tests_rotos_bloquean_con_exit_2(self) -> None:
        ruta = self._tests_dir()
        with open(os.path.join(ruta, "test_roto.py"), "w", encoding="utf-8") as handle:
            handle.write(
                "import unittest\n"
                "class T(unittest.TestCase):\n"
                "    def test_roto(self):\n"
                "        self.assertTrue(False)\n"
            )
        code, _out, err = self._correr()
        self.assertEqual(code, 2)
        self.assertIn("ROTOS", err)

    def test_error_de_import_bloquea(self) -> None:
        # unittest no revienta al descubrir: convierte el import roto en un
        # test que falla. Da igual por qué camino llegue — lo que importa es
        # que bloquee y que el motivo se vea.
        ruta = self._tests_dir()
        with open(os.path.join(ruta, "test_import.py"), "w", encoding="utf-8") as handle:
            handle.write("import un_modulo_que_no_existe\n")
        code, _out, err = self._correr()
        self.assertEqual(code, 2)
        self.assertIn("un_modulo_que_no_existe", err)

    def test_si_el_discover_revienta_bloquea(self) -> None:
        self._tests_dir()
        with mock.patch.object(hh, "_contar_tests", return_value=None):
            code, _out, err = self._correr()
        self.assertEqual(code, 2)
        self.assertIn("error de import", err)

    def test_el_directorio_de_tests_es_un_argumento_no_una_interpolacion(self) -> None:
        # El hook viejo metía el nombre dentro de una cadena de código Python:
        # una comilla en el parámetro y se ejecutaba lo que uno quisiera.
        code, out, err = self._correr()
        self.assertIn(code, (hh.PASA, 2))
        self.assertNotIn("Traceback", out + err)


if __name__ == "__main__":
    unittest.main()
