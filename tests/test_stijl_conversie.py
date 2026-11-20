"""De omzetting van v2-stijlconfiguraties naar het v3-contract.

De rauwe ``paint`` gaat één-op-één mee en wint in de lib van de afgeleide
paint, dus deze tests bewaken vooral dat ``paint`` onaangeroerd blijft: dat is
de garantie dat het beeld op de kaart niet verandert.
"""

from django.test import SimpleTestCase

from rgs_django_spatial.stijl.conversie import converteer_naar_v3, is_v3
from rgs_django_spatial.stijl.validatie import valideer_stijl_config


def v2_lijn():
    """Bouw een v2-lijnstijl met editor en één as."""
    return {
        "type": "line",
        "paint": {"line-color": "#0f0", "line-width": 2},
        "editor": {
            "basis": {"kleur": "#00ff00", "doorzicht": 1, "breedte": 2},
            "assen": [
                {
                    "veld": "status",
                    "eigenschap": "kleur",
                    "modus": "categorieen",
                    "categorieen": [{"waarde": "a", "kleur": "#111111"}],
                }
            ],
        },
    }


class IsV3Test(SimpleTestCase):
    def test_een_config_met_versie_3_is_v3(self):
        self.assertTrue(is_v3({"versie": 3, "lagen": []}))

    def test_een_v2_config_is_geen_v3(self):
        self.assertFalse(is_v3(v2_lijn()))

    def test_iets_dat_geen_object_is_is_geen_v3(self):
        self.assertFalse(is_v3(None))
        self.assertFalse(is_v3("line"))


class ConversieMetEditorTest(SimpleTestCase):
    def test_een_v3_config_gaat_ongewijzigd_terug(self):
        origineel = {"versie": 3, "lagen": [{"type": "line", "basis": {"kleur": "#fff", "doorzicht": 1}}]}

        resultaat, status = converteer_naar_v3(origineel)

        self.assertEqual(status, "al-v3")
        self.assertEqual(resultaat, origineel)

    def test_type_paint_en_basis_landen_op_de_sublaag(self):
        resultaat, status = converteer_naar_v3(v2_lijn())

        self.assertEqual(status, "geconverteerd")
        self.assertEqual(resultaat["versie"], 3)
        self.assertEqual(len(resultaat["lagen"]), 1)
        laag = resultaat["lagen"][0]
        self.assertEqual(laag["type"], "line")
        self.assertEqual(laag["basis"], {"kleur": "#00ff00", "doorzicht": 1, "breedte": 2})

    def test_de_paint_gaat_onaangeroerd_mee(self):
        # Dit is de kern van de conversie: zolang paint gelijk blijft, rendert
        # de stijl na conversie precies zoals ervoor.
        origineel = v2_lijn()
        verwacht = dict(origineel["paint"])

        resultaat, _ = converteer_naar_v3(origineel)

        self.assertEqual(resultaat["lagen"][0]["paint"], verwacht)

    def test_de_assen_verhuizen_naar_het_topniveau(self):
        resultaat, _ = converteer_naar_v3(v2_lijn())

        self.assertEqual(resultaat["assen"], v2_lijn()["editor"]["assen"])
        self.assertNotIn("assen", resultaat["lagen"][0])

    def test_zonder_assen_komt_er_geen_lege_assen_sleutel(self):
        v2 = v2_lijn()
        del v2["editor"]["assen"]

        resultaat, _ = converteer_naar_v3(v2)

        self.assertNotIn("assen", resultaat)

    def test_de_invoer_wordt_niet_gemuteerd(self):
        # De converter draait over rijen uit de database; een mutatie van de
        # invoer zou stilletjes de oude waarde onbruikbaar maken bij een
        # dry-run of bij een fout halverwege.
        v2 = v2_lijn()

        converteer_naar_v3(v2)

        self.assertEqual(v2, v2_lijn())

    def test_een_circle_houdt_zijn_straal(self):
        v2 = {
            "type": "circle",
            "paint": {"circle-color": "#f00", "circle-radius": 5},
            "editor": {"basis": {"kleur": "#ff0000", "doorzicht": 0.9, "straal": 5}},
        }

        resultaat, status = converteer_naar_v3(v2)

        self.assertEqual(status, "geconverteerd")
        self.assertEqual(resultaat["lagen"][0]["basis"]["straal"], 5)

    def test_een_fill_heeft_geen_straal_of_breedte(self):
        v2 = {
            "type": "fill",
            "paint": {"fill-color": "#00f", "fill-opacity": 0.35},
            "editor": {"basis": {"kleur": "#0000ff", "doorzicht": 0.35}},
        }

        resultaat, _ = converteer_naar_v3(v2)

        basis = resultaat["lagen"][0]["basis"]
        self.assertNotIn("straal", basis)
        self.assertNotIn("breedte", basis)

    def test_het_resultaat_haalt_de_validator(self):
        for naam, v2 in (
            ("line", v2_lijn()),
            (
                "circle",
                {
                    "type": "circle",
                    "paint": {"circle-color": "#f00"},
                    "editor": {"basis": {"kleur": "#ff0000", "doorzicht": 0.9, "straal": 5}},
                },
            ),
            (
                "fill",
                {
                    "type": "fill",
                    "paint": {"fill-color": "#00f"},
                    "editor": {"basis": {"kleur": "#0000ff", "doorzicht": 0.35}},
                },
            ),
        ):
            with self.subTest(type=naam):
                resultaat, _ = converteer_naar_v3(v2)
                self.assertEqual(valideer_stijl_config(resultaat), [])
                # De Python-validator eist doorzicht niet, de TS-validator wel;
                # daarom hier expliciet.
                self.assertIsInstance(resultaat["lagen"][0]["basis"]["doorzicht"], (int, float))


class ConversieZonderEditorTest(SimpleTestCase):
    def test_basis_wordt_afgeleid_uit_de_paint(self):
        v2 = {"type": "line", "paint": {"line-color": "#0f0", "line-opacity": 0.5, "line-width": 3}}

        resultaat, status = converteer_naar_v3(v2)

        self.assertEqual(status, "benaderd")
        self.assertEqual(resultaat["lagen"][0]["basis"], {"kleur": "#0f0", "doorzicht": 0.5, "breedte": 3})

    def test_de_paint_gaat_ook_hier_onaangeroerd_mee(self):
        v2 = {"type": "line", "paint": {"line-color": "#0f0"}}

        resultaat, _ = converteer_naar_v3(v2)

        self.assertEqual(resultaat["lagen"][0]["paint"], {"line-color": "#0f0"})

    def test_ontbrekende_paint_sleutels_vallen_terug_op_de_standaardwaarden(self):
        v2 = {"type": "fill", "paint": {}}

        resultaat, status = converteer_naar_v3(v2)

        self.assertEqual(status, "benaderd")
        self.assertEqual(resultaat["lagen"][0]["basis"], {"kleur": "#888888", "doorzicht": 1})

    def test_een_expressie_in_de_paint_levert_de_standaardwaarde(self):
        # Een MapLibre-expressie is een lijst, geen letterlijke waarde. Die
        # kan de editor niet tonen; de rendering komt uit paint, dus dit is
        # onschadelijk.
        v2 = {"type": "line", "paint": {"line-color": ["get", "kleur"], "line-width": ["get", "breedte"]}}

        resultaat, _ = converteer_naar_v3(v2)

        basis = resultaat["lagen"][0]["basis"]
        self.assertEqual(basis["kleur"], "#888888")
        self.assertNotIn("breedte", basis)

    def test_een_onbekend_type_levert_alleen_de_standaardwaarden(self):
        v2 = {"type": "heatmap", "paint": {"heatmap-radius": 20}}

        resultaat, status = converteer_naar_v3(v2)

        self.assertEqual(status, "benaderd")
        self.assertEqual(resultaat["lagen"][0]["basis"], {"kleur": "#888888", "doorzicht": 1})

    def test_een_lege_editor_telt_als_geen_editor(self):
        v2 = {"type": "line", "paint": {"line-color": "#0f0"}, "editor": {}}

        _, status = converteer_naar_v3(v2)

        self.assertEqual(status, "benaderd")

    def test_een_editor_zonder_doorzicht_krijgt_er_alsnog_een(self):
        # De v3-validator wijst een sublaag zonder doorzicht af, dus een
        # onvolledige editor mag niet tot een ongeldige stijl leiden.
        v2 = {"type": "line", "paint": {"line-opacity": 0.4}, "editor": {"basis": {"kleur": "#00ff00"}}}

        resultaat, status = converteer_naar_v3(v2)

        self.assertEqual(status, "benaderd")
        self.assertEqual(resultaat["lagen"][0]["basis"], {"kleur": "#00ff00", "doorzicht": 0.4})


class DubbeleAsTest(SimpleTestCase):
    def test_de_tweede_as_op_dezelfde_eigenschap_vervalt(self):
        v2 = {
            "type": "line",
            "paint": {"line-color": "#0f0"},
            "editor": {
                "basis": {"kleur": "#00ff00", "doorzicht": 1},
                "assen": [
                    {"veld": "eerste", "eigenschap": "kleur", "modus": "categorieen", "categorieen": []},
                    {"veld": "tweede", "eigenschap": "kleur", "modus": "categorieen", "categorieen": []},
                    {"veld": "derde", "eigenschap": "breedte", "modus": "schaal", "stops": [[0, 1]]},
                ],
            },
        }

        resultaat, status = converteer_naar_v3(v2)

        self.assertEqual(status, "benaderd")
        self.assertEqual([as_["veld"] for as_ in resultaat["assen"]], ["eerste", "derde"])

    def test_zonder_dubbele_as_blijft_de_status_geconverteerd(self):
        v2 = {
            "type": "line",
            "paint": {"line-color": "#0f0"},
            "editor": {
                "basis": {"kleur": "#00ff00", "doorzicht": 1},
                "assen": [{"veld": "status", "eigenschap": "kleur", "modus": "categorieen", "categorieen": []}],
            },
        }

        _, status = converteer_naar_v3(v2)

        self.assertEqual(status, "geconverteerd")

    def test_het_resultaat_van_een_randgeval_haalt_de_validator(self):
        for naam, v2 in (
            ("geen editor", {"type": "line", "paint": {"line-color": "#0f0"}}),
            ("lege paint", {"type": "fill", "paint": {}}),
            (
                "dubbele as",
                {
                    "type": "line",
                    "paint": {"line-color": "#0f0"},
                    "editor": {
                        "basis": {"kleur": "#00ff00", "doorzicht": 1},
                        "assen": [
                            # Niet-lege categorieen: de validator eist bij modus
                            # "categorieen" een gevulde payload.
                            {
                                "veld": "a",
                                "eigenschap": "kleur",
                                "modus": "categorieen",
                                "categorieen": [{"waarde": "x", "kleur": "#111111"}],
                            },
                            {
                                "veld": "b",
                                "eigenschap": "kleur",
                                "modus": "categorieen",
                                "categorieen": [{"waarde": "y", "kleur": "#222222"}],
                            },
                        ],
                    },
                },
            ),
        ):
            with self.subTest(geval=naam):
                resultaat, _ = converteer_naar_v3(v2)
                self.assertEqual(valideer_stijl_config(resultaat), [])
                self.assertIsInstance(resultaat["lagen"][0]["basis"]["doorzicht"], (int, float))
