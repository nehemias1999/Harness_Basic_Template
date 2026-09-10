"""Tests de scripts/validate_feature_list.py.

Viven en `scripts/tests/` y no en `tests/` por la misma razón que sus vecinos:
`tests/` es del proyecto, y el verificador lo descubre. Ver el encabezado de
test_validate_requirements.py.

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import validate_feature_list as vfl  # noqa: E402


REGLAS_SANAS = {
    "one_feature_at_a_time": True,
    "require_tests_to_close": True,
    "orden_de_trabajo": "prioridad_luego_id",
    "valid_status": list(vfl.VALID_STATUS),
}


def feature(**kwargs) -> dict:
    base = {
        "id": 1,
        "name": "una_feature",
        "title": "Una feature",
        "description": "Qué hace.",
        "spec": "specs/REQ-001_un_requisito.md",
        "prioridad": "media",
        "acceptance": ["hace algo verificable"],
        "status": "draft",
    }
    base.update(kwargs)
    return base


class FeatureListCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def escribir(self, features: list, rules: dict | None = None) -> str:
        payload = {
            "project": "prueba",
            "rules": REGLAS_SANAS if rules is None else rules,
            "features": features,
        }
        path = os.path.join(self.root, "feature_list.json")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return path

    def crear_test(self) -> None:
        os.makedirs(os.path.join(self.root, "tests"), exist_ok=True)
        with open(os.path.join(self.root, "tests", "test_algo.py"), "w") as handle:
            handle.write("# un test\n")

    def errores(self, features: list, rules: dict | None = None) -> list[str]:
        return vfl.validate(self.escribir(features, rules))

    def assertErrorCon(self, needle: str, features: list, rules: dict | None = None) -> None:
        errs = self.errores(features, rules)
        self.assertTrue(any(needle in e for e in errs), f"{needle!r} no está en {errs}")


class TestCaminoFeliz(FeatureListCase):
    def test_lista_vacia_es_valida(self) -> None:
        self.assertEqual(self.errores([]), [])

    def test_una_feature_bien_formada(self) -> None:
        self.assertEqual(self.errores([feature()]), [])

    def test_orden_de_trabajo_por_prioridad_y_luego_id(self) -> None:
        features = [
            feature(id=1, name="a", prioridad="critica", status="pending"),
            feature(id=2, name="b", prioridad="alta", status="pending"),
            feature(id=3, name="c", prioridad="critica", status="pending"),
            feature(id=4, name="d", prioridad="baja", status="draft"),
        ]
        cola = [f["id"] for f in vfl.orden_de_trabajo(features)]
        self.assertEqual(cola, [1, 3, 2])


class TestReglasDelArnes(FeatureListCase):
    """El JSON declara las reglas; no las decide."""

    def test_no_se_puede_desactivar_una_feature_a_la_vez(self) -> None:
        rules = dict(REGLAS_SANAS, one_feature_at_a_time=False)
        self.assertErrorCon('"rules.one_feature_at_a_time"', [feature()], rules)

    def test_desactivarla_no_evita_el_error_de_dos_in_progress(self) -> None:
        rules = dict(REGLAS_SANAS, one_feature_at_a_time=False)
        errs = self.errores(
            [
                feature(id=1, name="a", status="in_progress"),
                feature(id=2, name="b", status="in_progress"),
            ],
            rules,
        )
        self.assertTrue(any("in_progress (máximo 1)" in e for e in errs), errs)

    def test_no_se_pueden_inventar_estados(self) -> None:
        rules = dict(REGLAS_SANAS, valid_status=list(vfl.VALID_STATUS) + ["listo"])
        self.assertErrorCon('"rules.valid_status"', [feature()], rules)

    def test_un_estado_inventado_sigue_siendo_invalido(self) -> None:
        rules = dict(REGLAS_SANAS, valid_status=list(vfl.VALID_STATUS) + ["listo"])
        self.assertErrorCon('estado inválido "listo"', [feature(status="listo")], rules)

    def test_rules_que_no_es_objeto(self) -> None:
        self.assertErrorCon('"rules" debe ser un objeto', [], "una cadena")

    def test_require_tests_to_close_no_se_apaga(self) -> None:
        rules = dict(REGLAS_SANAS, require_tests_to_close=False)
        self.assertErrorCon('"rules.require_tests_to_close"', [feature()], rules)


class TestFormaDeLaFeature(FeatureListCase):
    def test_falta_un_campo_obligatorio(self) -> None:
        sin_spec = feature()
        del sin_spec["spec"]
        self.assertErrorCon('falta el campo "spec"', [sin_spec])

    def test_id_duplicado(self) -> None:
        self.assertErrorCon(
            "id duplicado", [feature(id=1, name="a"), feature(id=1, name="b")]
        )

    def test_name_duplicado(self) -> None:
        self.assertErrorCon(
            "name duplicado", [feature(id=1, name="misma"), feature(id=2, name="misma")]
        )

    def test_name_que_no_es_snake_case(self) -> None:
        self.assertErrorCon("snake_case", [feature(name="Una Feature")])

    def test_id_que_no_es_entero(self) -> None:
        self.assertErrorCon("entero >= 1", [feature(id="1")])

    def test_title_vacio(self) -> None:
        self.assertErrorCon('"title" no puede estar vacío', [feature(title="   ")])

    def test_spec_con_ruta_invalida(self) -> None:
        self.assertErrorCon('"spec" debe ser una ruta', [feature(spec="docs/otra.md")])

    def test_prioridad_invalida(self) -> None:
        self.assertErrorCon("prioridad inválida", [feature(prioridad="urgentisima")])

    def test_acceptance_vacio(self) -> None:
        self.assertErrorCon('"acceptance" debe ser un array', [feature(acceptance=[])])

    def test_acceptance_con_criterios_vacios(self) -> None:
        self.assertErrorCon("criterios de", [feature(acceptance=["bien", "  "])])

    def test_feature_que_no_es_objeto(self) -> None:
        self.assertErrorCon("no es un objeto", ["esto no es una feature"])


class TestCierreSinPruebas(FeatureListCase):
    def test_done_sin_ningun_test_falla(self) -> None:
        self.assertErrorCon("ni un solo test", [feature(status="done")])

    def test_done_con_tests_pasa(self) -> None:
        self.crear_test()
        self.assertEqual(self.errores([feature(status="done")]), [])

    def test_sin_features_done_no_exige_tests(self) -> None:
        self.assertEqual(self.errores([feature(status="pending")]), [])


class TestArchivo(FeatureListCase):
    def test_archivo_inexistente(self) -> None:
        errs = vfl.validate(os.path.join(self.root, "no_existe.json"))
        self.assertEqual(len(errs), 1)
        self.assertIn("No existe", errs[0])

    def test_json_invalido(self) -> None:
        path = os.path.join(self.root, "feature_list.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{ roto")
        self.assertIn("no es JSON válido", vfl.validate(path)[0])


if __name__ == "__main__":
    unittest.main()
