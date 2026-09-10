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


class TestPreToolUse(unittest.TestCase):
    """La capa que verifica no se edita mientras se trabaja."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self._patch = mock.patch.object(hh, "REPO_ROOT", self.root)
        self._patch.start()
        # Sin marca de mantenimiento y sin la variable de entorno.
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()
        os.environ.pop("HARNESS_MANTENIMIENTO", None)

    def tearDown(self) -> None:
        self._env.stop()
        self._patch.stop()
        self._tmp.cleanup()

    def _correr(self, entrada: dict) -> tuple[int, str]:
        err = io.StringIO()
        with mock.patch.object(hh, "_entrada_del_hook", return_value=entrada), \
             redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = hh.evento_pre_tool_use()
        return code, err.getvalue()

    def _escritura(self, ruta: str, herramienta: str = "Write") -> tuple[int, str]:
        return self._correr({"tool_name": herramienta, "tool_input": {"file_path": ruta}})

    def _shell(self, comando: str) -> tuple[int, str]:
        return self._correr({"tool_name": "Bash", "tool_input": {"command": comando}})

    def test_bloquea_escribir_en_los_validadores(self) -> None:
        code, err = self._escritura("scripts/validate_requirements.py")
        self.assertEqual(code, 2)
        self.assertIn("capa que verifica", err)

    def test_bloquea_escribir_en_los_hooks(self) -> None:
        self.assertEqual(self._escritura(".claude/settings.json", "Edit")[0], 2)

    def test_bloquea_escribir_en_el_verificador(self) -> None:
        self.assertEqual(self._escritura("init.sh")[0], 2)
        self.assertEqual(self._escritura("init.ps1")[0], 2)

    def test_bloquea_escribir_en_el_contrato(self) -> None:
        for ruta in ("AGENTS.md", "CLAUDE.md", "CHECKPOINTS.md"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self._escritura(ruta)[0], 2)

    def test_deja_pasar_el_codigo_del_proyecto(self) -> None:
        for ruta in ("src/modulo.py", "tests/test_modulo.py", "feature_list.json",
                     "progress/current.md", "specs/REQ-001_algo.md", "docs/architecture.md"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self._escritura(ruta)[0], hh.PASA)

    def test_bloquea_una_escritura_de_shell_disfrazada(self) -> None:
        # El matcher Edit|Write no ve esto; PreToolUse sobre Bash, sí.
        self.assertEqual(self._shell("echo pass > scripts/validate_requirements.py")[0], 2)
        self.assertEqual(self._shell("rm -rf scripts/tests")[0], 2)

    def test_no_estorba_a_una_lectura_de_shell(self) -> None:
        self.assertEqual(self._shell("cat scripts/validate_requirements.py")[0], hh.PASA)
        self.assertEqual(self._shell("python scripts/validate_requirements.py .")[0], hh.PASA)

    def test_la_marca_de_mantenimiento_abre_la_puerta(self) -> None:
        with open(os.path.join(self.root, hh.MARCA_MANTENIMIENTO), "w") as handle:
            handle.write("")
        self.assertEqual(self._escritura("scripts/validate_requirements.py")[0], hh.PASA)

    def test_la_variable_de_entorno_tambien(self) -> None:
        os.environ["HARNESS_MANTENIMIENTO"] = "1"
        try:
            self.assertEqual(self._escritura("init.ps1")[0], hh.PASA)
        finally:
            os.environ.pop("HARNESS_MANTENIMIENTO", None)

    def test_una_ruta_de_fuera_del_repo_no_es_asunto_suyo(self) -> None:
        self.assertEqual(self._escritura("/tmp/otro/scripts/cosa.py")[0], hh.PASA)


if __name__ == "__main__":
    unittest.main()
