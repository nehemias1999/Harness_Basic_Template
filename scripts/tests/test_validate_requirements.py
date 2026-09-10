"""Tests de scripts/validate_requirements.py.

Viven aquí y no en `tests/` a propósito: `tests/` es del proyecto, y el
verificador lo descubre con `unittest discover -s tests`. Si estos tests
estuvieran ahí, un proyecto recién instanciado saldría "verde" con tests que
no son suyos, y el arnés dejaría de distinguir "sin verificar" de "verificado".

Se ejecutan a mano o desde /harness-check:

    python -m unittest discover -s scripts/tests -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import validate_requirements as vr  # noqa: E402


SPEC = """---
id: {spec_id}
titulo: Un requisito de prueba
estado: {estado}
prioridad: {prioridad}
creado: 2026-09-10
actualizado: 2026-09-10
aprobado_el: {aprobado_el}
ronda: 1
---

# {spec_id} — Un requisito de prueba

## 6. Supuestos y preguntas abiertas

{preguntas}
"""


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


class HarnessCase(unittest.TestCase):
    """Monta un repo de mentira en un directorio temporal."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        os.makedirs(os.path.join(self.root, "specs"))
        os.makedirs(os.path.join(self.root, "src"))
        self.write_features([])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- helpers ---------------------------------------------------------
    def write_features(self, features: list[dict]) -> None:
        payload = {"project": "prueba", "rules": {}, "features": features}
        path = os.path.join(self.root, "feature_list.json")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def write_spec(
        self,
        name: str = "REQ-001_un_requisito.md",
        spec_id: str = "REQ-001",
        estado: str = "draft",
        prioridad: str = "media",
        aprobado_el: str = "",
        preguntas: str = "- [x] **P1:** respondida",
        body: str | None = None,
    ) -> None:
        content = body if body is not None else SPEC.format(
            spec_id=spec_id,
            estado=estado,
            prioridad=prioridad,
            aprobado_el=aprobado_el,
            preguntas=preguntas,
        )
        # Un spec aprobado lleva la huella de su contenido; la calcula
        # /aprobar-requisitos al firmarlo. Como la huella ignora el
        # frontmatter, añadir la línea no la cambia.
        if estado == "aprobado" and "aprobado_hash:" not in content:
            huella = vr.huella_del_spec(content)
            cabecera, resto = content.split("\n---\n", 1)
            content = f"{cabecera}\naprobado_hash: {huella}\n---\n{resto}"
        with open(os.path.join(self.root, "specs", name), "w", encoding="utf-8", newline="\n") as h:
            h.write(content)

    def write_module(self, name: str = "cosa.py") -> None:
        with open(os.path.join(self.root, "src", name), "w", encoding="utf-8") as handle:
            handle.write('"""Un módulo."""\n')

    def check(self) -> tuple[list[str], list[str]]:
        return vr.check(self.root)

    def assertFailsWith(self, needle: str) -> None:
        fails, _ = self.check()
        self.assertTrue(
            any(needle in f for f in fails),
            f"ningún [FAIL] contiene {needle!r}. Fallos: {fails}",
        )

    def assertNoFails(self) -> None:
        fails, _ = self.check()
        self.assertEqual(fails, [])


class TestEstadosNormales(HarnessCase):
    def test_sin_specs_ni_features_solo_avisa(self) -> None:
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(warns)

    def test_specs_sin_carpeta_solo_avisa(self) -> None:
        os.rmdir(os.path.join(self.root, "specs"))
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(any("todavía no existe specs/" in w for w in warns))

    def test_draft_con_features_draft_es_valido(self) -> None:
        self.write_spec()
        self.write_features([feature()])
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(any("esperando tu OK" in w for w in warns))

    def test_aprobado_con_features_pending_es_valido_y_sin_avisos(self) -> None:
        self.write_spec(estado="aprobado", aprobado_el="2026-09-10")
        self.write_features([feature(status="pending")])
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertEqual(warns, [])

    def test_varias_features_por_requisito(self) -> None:
        self.write_spec(estado="aprobado", aprobado_el="2026-09-10")
        self.write_features(
            [
                feature(id=1, name="una", status="pending"),
                feature(id=2, name="otra", status="pending"),
            ]
        )
        self.assertNoFails()

    def test_plantilla_con_placeholders_se_ignora(self) -> None:
        self.write_spec(name="_plantilla_req.md", body="---\nid: <REQ-00N>\n")
        self.assertNoFails()


class TestElGate(HarnessCase):
    def test_feature_en_progreso_sobre_draft_falla(self) -> None:
        self.write_spec()
        self.write_features([feature(status="in_progress")])
        self.assertFailsWith("sigue en estado \"draft\"")

    def test_feature_blocked_sobre_draft_tambien_falla(self) -> None:
        self.write_spec()
        self.write_features([feature(status="blocked")])
        self.assertFailsWith("nadie aprobó ese requisito")

    def test_codigo_en_src_sin_requisito_aprobado_falla(self) -> None:
        self.write_spec()
        self.write_features([feature()])
        self.write_module()
        self.assertFailsWith("antes de definir qué había que hacer")

    def test_codigo_en_src_con_requisito_aprobado_es_valido(self) -> None:
        self.write_spec(estado="aprobado", aprobado_el="2026-09-10")
        self.write_features([feature(status="done")])
        self.write_module()
        self.assertNoFails()


class TestTrazabilidad(HarnessCase):
    def test_feature_sin_campo_spec_falla(self) -> None:
        sin_spec = feature()
        del sin_spec["spec"]
        self.write_features([sin_spec])
        self.assertFailsWith("no tiene campo \"spec\"")

    def test_puntero_colgante_falla(self) -> None:
        self.write_features([feature()])
        self.assertFailsWith("que no existe")

    def test_puntero_con_formato_invalido_falla(self) -> None:
        self.write_features([feature(spec="docs/otra_cosa.md")])
        self.assertFailsWith("debe ser una ruta specs/REQ-00N_nombre.md")

    def test_aprobado_sin_features_falla(self) -> None:
        self.write_spec(estado="aprobado", aprobado_el="2026-09-10")
        self.assertFailsWith("ninguna feature lo referencia")

    def test_aprobado_con_features_draft_solo_avisa(self) -> None:
        self.write_spec(estado="aprobado", aprobado_el="2026-09-10")
        self.write_features([feature(status="draft")])
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(any("aprobación a medias" in w for w in warns))


class TestFormatoDelSpec(HarnessCase):
    def test_nombre_de_archivo_invalido_falla(self) -> None:
        self.write_spec(name="REQ-001 Mal Nombre.md")
        self.assertFailsWith("no sigue el formato")

    def test_sin_frontmatter_falla(self) -> None:
        self.write_spec(body="# Un requisito sin frontmatter\n")
        self.assertFailsWith("no tiene frontmatter")

    def test_frontmatter_sin_cerrar_falla(self) -> None:
        self.write_spec(body="---\nid: REQ-001\ntitulo: x\n")
        self.assertFailsWith("no tiene frontmatter")

    def test_falta_una_clave_obligatoria(self) -> None:
        self.write_spec(body="---\nid: REQ-001\ntitulo: x\nprioridad: alta\n---\n")
        self.assertFailsWith("falta en el frontmatter: estado")

    def test_estado_invalido_falla(self) -> None:
        self.write_spec(estado="listo")
        self.assertFailsWith("estado inválido")

    def test_prioridad_invalida_falla(self) -> None:
        self.write_spec(prioridad="urgentisima")
        self.assertFailsWith("prioridad inválida")

    def test_id_que_no_coincide_con_el_archivo_falla(self) -> None:
        self.write_spec(spec_id="REQ-002")
        self.assertFailsWith("no coincide con el")

    def test_id_duplicado_falla(self) -> None:
        self.write_spec()
        self.write_spec(name="REQ-001_otro_nombre.md")
        self.assertFailsWith("duplicado")

    def test_aprobado_sin_fecha_falla(self) -> None:
        self.write_spec(estado="aprobado")
        self.write_features([feature(status="pending")])
        self.assertFailsWith("le falta la fecha en aprobado_el")

    def test_aprobado_con_preguntas_abiertas_falla(self) -> None:
        self.write_spec(
            estado="aprobado",
            aprobado_el="2026-09-10",
            preguntas="- [ ] **P1:** ¿esto cómo era?",
        )
        self.write_features([feature(status="pending")])
        self.assertFailsWith("pregunta(s) abierta(s) sin responder")


class TestPrioridad(HarnessCase):
    def test_feature_puede_bajar_la_prioridad(self) -> None:
        self.write_spec(estado="aprobado", prioridad="alta", aprobado_el="2026-09-10")
        self.write_features([feature(status="pending", prioridad="baja")])
        self.assertNoFails()

    def test_feature_no_puede_subir_la_prioridad(self) -> None:
        self.write_spec(estado="aprobado", prioridad="media", aprobado_el="2026-09-10")
        self.write_features([feature(status="pending", prioridad="critica")])
        self.assertFailsWith("es más alta que la de su requisito")

    def test_avisa_del_adelantamiento(self) -> None:
        self.write_spec(estado="aprobado", prioridad="critica", aprobado_el="2026-09-10")
        self.write_features(
            [
                feature(id=1, name="en_curso", status="in_progress", prioridad="media"),
                feature(id=2, name="urgente", status="pending", prioridad="critica"),
            ]
        )
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(any("más prioridad encolado" in w for w in warns))

    def test_no_avisa_si_lo_encolado_es_menos_urgente(self) -> None:
        self.write_spec(estado="aprobado", prioridad="critica", aprobado_el="2026-09-10")
        self.write_features(
            [
                feature(id=1, name="en_curso", status="in_progress", prioridad="critica"),
                feature(id=2, name="despues", status="pending", prioridad="baja"),
            ]
        )
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertEqual(warns, [])


class TestEscenariosAdversarios(HarnessCase):
    """Los intentos de saltarse el gate que encontró la auditoría.

    Todos estos pasaban antes. Están aquí para que no vuelvan.
    """

    def test_un_estado_inventado_no_escapa_del_gate(self) -> None:
        # Ampliando rules.valid_status se podía inventar un estado que ningún
        # validador miraba. Ahora todo lo que no es draft cuenta como trabajo.
        self.write_spec()
        self.write_features([feature(status="listo")])
        self.assertFailsWith("nadie aprobó ese requisito")

    def test_codigo_en_subcarpeta_de_src_tambien_cuenta(self) -> None:
        self.write_spec()
        self.write_features([feature()])
        os.makedirs(os.path.join(self.root, "src", "paquete"))
        with open(os.path.join(self.root, "src", "paquete", "mod.py"), "w") as handle:
            handle.write("x = 1\n")
        self.assertFailsWith("antes de definir qué había que hacer")

    def test_codigo_que_no_es_python_tambien_cuenta(self) -> None:
        self.write_spec()
        self.write_features([feature()])
        with open(os.path.join(self.root, "src", "app.ts"), "w") as handle:
            handle.write("const x = 1\n")
        self.assertFailsWith("antes de definir qué había que hacer")

    def test_fecha_de_aprobacion_tiene_que_ser_una_fecha(self) -> None:
        self.write_spec(estado="aprobado", aprobado_el="cuando sea")
        self.write_features([feature(status="pending")])
        self.assertFailsWith("tiene que ser una fecha")

    def test_checkbox_dentro_de_un_bloque_de_codigo_no_bloquea(self) -> None:
        self.write_spec(
            estado="aprobado",
            aprobado_el="2026-09-10",
            preguntas="```\n- [ ] ejemplo de la plantilla\n```",
        )
        self.write_features([feature(status="pending")])
        self.assertNoFails()

    def test_checkbox_con_otra_grafia_igual_bloquea(self) -> None:
        for grafia in ("- [  ] P1", "* [ ] P1", "+ [] P1"):
            with self.subTest(grafia=grafia):
                self.write_spec(
                    estado="aprobado", aprobado_el="2026-09-10", preguntas=grafia
                )
                self.write_features([feature(status="pending")])
                self.assertFailsWith("pregunta(s) abierta(s) sin responder")

    def test_frontmatter_con_claves_repetidas_falla(self) -> None:
        self.write_spec(
            body=(
                "---\nid: REQ-001\ntitulo: T\nestado: draft\n"
                "estado: aprobado\nprioridad: alta\n---\n"
            )
        )
        self.assertFailsWith("el frontmatter repite")

    def test_spec_descartado_con_features_draft_avisa(self) -> None:
        self.write_spec(estado="descartado")
        self.write_features([feature(status="draft")])
        fails, warns = self.check()
        self.assertEqual(fails, [])
        self.assertTrue(any("está descartado" in w for w in warns), warns)

    def test_spec_descartado_con_feature_viva_falla(self) -> None:
        self.write_spec(estado="descartado")
        self.write_features([feature(status="in_progress")])
        self.assertFailsWith("nadie aprobó ese requisito")

    def test_feature_list_ilegible_no_calla_lo_de_specs(self) -> None:
        self.write_spec(name="REQ-001 Mal Nombre.md")
        with open(os.path.join(self.root, "feature_list.json"), "w") as handle:
            handle.write("{ esto no es json")
        fails, _ = self.check()
        self.assertTrue(any("no sigue el formato" in f for f in fails), fails)
        self.assertTrue(any("feature_list.json" in f for f in fails), fails)

    def test_id_que_no_coincide_no_se_carga(self) -> None:
        # Antes se reportaba el fallo pero el spec se seguía usando para
        # trazabilidad, lo que daba diagnósticos contradictorios.
        self.write_spec(spec_id="REQ-002")
        self.write_features([feature()])
        fails, _ = self.check()
        self.assertTrue(any("no coincide" in f for f in fails), fails)
        self.assertTrue(any("que no existe" in f for f in fails), fails)


class TestHuellaDeLoAprobado(HarnessCase):
    """Aprobar tiene que significar "aprobé *esto*", no "escribí la palabra"."""

    def test_editar_un_spec_aprobado_se_detecta(self) -> None:
        self.write_spec(estado="aprobado", aprobado_el="2026-09-10")
        self.write_features([feature(status="pending")])
        self.assertNoFails()

        ruta = os.path.join(self.root, "specs", "REQ-001_un_requisito.md")
        with open(ruta, encoding="utf-8") as handle:
            contenido = handle.read()
        with open(ruta, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(contenido + "\n## 5. Criterios\n\n1. Y además, borrar todo.\n")

        self.assertFailsWith("cambió DESPUÉS de aprobarse")

    def test_aprobado_sin_huella_falla(self) -> None:
        self.write_spec(
            body=(
                "---\nid: REQ-001\ntitulo: T\nestado: aprobado\n"
                "prioridad: alta\naprobado_el: 2026-09-10\n---\n# REQ-001\n"
            )
        )
        self.write_features([feature(status="pending")])
        self.assertFailsWith("no tiene aprobado_hash")

    def test_tocar_la_bitacora_no_invalida_la_aprobacion(self) -> None:
        # §7 y §8 cambian legítimamente después de aprobar.
        self.write_spec(estado="aprobado", aprobado_el="2026-09-10")
        self.write_features([feature(status="pending")])
        ruta = os.path.join(self.root, "specs", "REQ-001_un_requisito.md")
        with open(ruta, "a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n## 8. Bitácora\n\n| 2 | 2026-09-11 | se derivó otra feature |\n")
        self.assertNoFails()

    def test_la_huella_ignora_el_frontmatter(self) -> None:
        cuerpo = "# T\n\n## 3. Alcance\n\nBuscar notas.\n"
        uno = vr.huella_del_spec("---\nid: REQ-001\nestado: draft\n---\n" + cuerpo)
        dos = vr.huella_del_spec("---\nid: REQ-001\nestado: aprobado\nronda: 9\n---\n" + cuerpo)
        self.assertEqual(uno, dos)

    def test_la_huella_ignora_espacios_al_final_de_linea(self) -> None:
        uno = vr.huella_del_spec("---\na: b\n---\n## 3. Alcance\n\nAlgo.\n")
        dos = vr.huella_del_spec("---\na: b\n---\n## 3. Alcance   \n\nAlgo.  \n")
        self.assertEqual(uno, dos)


class TestParserDeFrontmatter(unittest.TestCase):
    def test_quita_comillas(self) -> None:
        fields, repetidas = vr.parse_frontmatter("---\ntitulo: \"Con comillas\"\n---\n")
        self.assertEqual(fields, {"titulo": "Con comillas"})
        self.assertEqual(repetidas, [])

    def test_no_trunca_un_titulo_con_almohadilla(self) -> None:
        fields, _ = vr.parse_frontmatter("---\ntitulo: Arregla el bug #123\n---\n")
        self.assertEqual(fields["titulo"], "Arregla el bug #123")

    def test_reporta_claves_repetidas(self) -> None:
        fields, repetidas = vr.parse_frontmatter(
            "---\nestado: draft\nestado: aprobado\n---\n"
        )
        self.assertEqual(fields["estado"], "draft")
        self.assertEqual(repetidas, ["estado"])

    def test_sin_apertura_devuelve_none(self) -> None:
        self.assertIsNone(vr.parse_frontmatter("# Solo un título\n"))


if __name__ == "__main__":
    unittest.main()
