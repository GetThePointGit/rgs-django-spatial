"""Eén test per validatieregel, plus een geldige basisconfiguratie als ijkpunt."""

import copy

from django.test import SimpleTestCase

from rgs_django_spatial.stijl.validatie import valideer_stijl_config

GELDIG = {
    "versie": 3,
    "lagen": [
        {
            "type": "line",
            "basis": {"kleur": "#0059ff", "doorzicht": 1, "breedte": {"zoom": [[8, 2], [22, 12]]}},
        }
    ],
    "assen": [
        {
            "veld": "category",
            "eigenschap": "kleur",
            "modus": "kleurenset",
            "kleurensetId": "1e529a9d-aba9-507a-81e0-5e0392495cd8",
        }
    ],
    "label": {"veld": "ids", "plaatsing": "lijnmidden", "anker": "onder"},
}

SETS = frozenset({"1e529a9d-aba9-507a-81e0-5e0392495cd8"})


def _met(**wijzigingen):
    """Kopieer GELDIG en overschrijf topniveau-sleutels."""
    config = copy.deepcopy(GELDIG)
    config.update(wijzigingen)
    return config


class ValidatieTest(SimpleTestCase):
    def test_geldige_config_geeft_geen_fouten(self):
        self.assertEqual(valideer_stijl_config(GELDIG, kleurenset_ids=SETS), [])

    def test_geen_object(self):
        fouten = valideer_stijl_config("nee", kleurenset_ids=SETS)
        self.assertEqual(fouten, ["stijlconfig is geen object"])

    def test_verkeerde_versie(self):
        fouten = valideer_stijl_config(_met(versie=2), kleurenset_ids=SETS)
        self.assertTrue(any("versie" in f for f in fouten), fouten)

    def test_lege_lagen(self):
        fouten = valideer_stijl_config(_met(lagen=[]), kleurenset_ids=SETS)
        self.assertTrue(any("minstens één sublaag" in f for f in fouten), fouten)

    def test_onbekend_sublaagtype(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "heatmap", "basis": {"kleur": "#000000", "doorzicht": 1}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("onbekend sublaagtype" in f for f in fouten), fouten)

    def test_onbekende_geometrie(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "geometrie": "bol", "basis": {"kleur": "#000000"}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("onbekende geometrie" in f for f in fouten), fouten)

    def test_basis_ontbreekt(self):
        fouten = valideer_stijl_config(_met(lagen=[{"type": "line"}]), kleurenset_ids=SETS)
        self.assertTrue(any("basis ontbreekt" in f for f in fouten), fouten)

    def test_doorzicht_buiten_eenheidsinterval(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": "#000000", "doorzicht": 1.5}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("doorzicht" in f for f in fouten), fouten)

    def test_doorzicht_bij_state_buiten_eenheidsinterval(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": "#000000", "doorzichtBijState": -0.2}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("doorzichtBijState" in f for f in fouten), fouten)

    def test_zoomniveaus_moeten_oplopen(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": "#000000", "breedte": {"zoom": [[10, 2], [8, 4]]}}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("strikt oplopen" in f for f in fouten), fouten)

    def test_zoomniveau_buiten_bereik(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": "#000000", "breedte": {"zoom": [[8, 2], [30, 4]]}}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("buiten [0, 24]" in f for f in fouten), fouten)

    def test_lege_zoomlijst(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": "#000000", "breedte": {"zoom": []}}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("minstens één paar" in f for f in fouten), fouten)

    def test_straal_alleen_bij_circle(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": "#000000", "straal": 5}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("straal hoort alleen bij een circle" in f for f in fouten), fouten)

    def test_breedte_niet_bij_symbol(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "symbol", "basis": {"kleur": "#000000", "breedte": 2}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("breedte hoort niet" in f for f in fouten), fouten)

    def test_halo_alleen_bij_symbol(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": "#000000", "halo": {"kleur": "#ffffff"}}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("halo hoort alleen bij een symbol" in f for f in fouten), fouten)

    def test_as_zonder_veld(self):
        fouten = valideer_stijl_config(
            _met(assen=[{"eigenschap": "kleur", "modus": "categorieen", "categorieen": [{"waarde": "1"}]}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("veld ontbreekt" in f for f in fouten), fouten)

    def test_onbekende_eigenschap(self):
        fouten = valideer_stijl_config(
            _met(
                assen=[{"veld": "x", "eigenschap": "dikte", "modus": "categorieen", "categorieen": [{"waarde": "1"}]}]
            ),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("onbekende eigenschap" in f for f in fouten), fouten)

    def test_hooguit_een_as_per_eigenschap(self):
        as_een = {"veld": "a", "eigenschap": "kleur", "modus": "categorieen", "categorieen": [{"waarde": "1"}]}
        as_twee = {"veld": "b", "eigenschap": "kleur", "modus": "categorieen", "categorieen": [{"waarde": "2"}]}
        fouten = valideer_stijl_config(_met(assen=[as_een, as_twee]), kleurenset_ids=SETS)
        self.assertTrue(any("tweede as op eigenschap" in f for f in fouten), fouten)

    def test_twee_assen_op_verschillende_eigenschappen_mag(self):
        as_kleur = {
            "veld": "category",
            "eigenschap": "kleur",
            "modus": "kleurenset",
            "kleurensetId": "1e529a9d-aba9-507a-81e0-5e0392495cd8",
        }
        as_breedte = {
            "veld": "category",
            "eigenschap": "breedte",
            "modus": "kleurenset",
            "kleurensetId": "1e529a9d-aba9-507a-81e0-5e0392495cd8",
        }
        self.assertEqual(valideer_stijl_config(_met(assen=[as_kleur, as_breedte]), kleurenset_ids=SETS), [])

    def test_onbekende_modus(self):
        fouten = valideer_stijl_config(
            _met(assen=[{"veld": "x", "eigenschap": "kleur", "modus": "regenboog"}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("onbekende modus" in f for f in fouten), fouten)

    def test_onbekende_kleurenset(self):
        fouten = valideer_stijl_config(GELDIG, kleurenset_ids=frozenset())
        self.assertTrue(any("onbekende kleurensetId" in f for f in fouten), fouten)

    def test_kleurenset_zonder_id(self):
        fouten = valideer_stijl_config(
            _met(assen=[{"veld": "x", "eigenschap": "kleur", "modus": "kleurenset"}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("kleurensetId ontbreekt" in f for f in fouten), fouten)

    def test_categorieen_ontbreken(self):
        fouten = valideer_stijl_config(
            _met(assen=[{"veld": "x", "eigenschap": "kleur", "modus": "categorieen"}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("categorieen ontbreken" in f for f in fouten), fouten)

    def test_stops_ontbreken(self):
        fouten = valideer_stijl_config(
            _met(assen=[{"veld": "x", "eigenschap": "kleur", "modus": "schaal"}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("stops ontbreken" in f for f in fouten), fouten)

    def test_stappen_ontbreken(self):
        fouten = valideer_stijl_config(
            _met(assen=[{"veld": "x", "eigenschap": "kleur", "modus": "stap"}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("stappen ontbreken" in f for f in fouten), fouten)

    def test_halo_as_vereist_symbol_sublaag(self):
        fouten = valideer_stijl_config(
            _met(
                assen=[{"veld": "x", "eigenschap": "halo", "modus": "categorieen", "categorieen": [{"waarde": "1"}]}]
            ),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("halo-as vereist een symbol-sublaag" in f for f in fouten), fouten)

    def test_label_zonder_veld(self):
        fouten = valideer_stijl_config(_met(label={"anker": "onder"}), kleurenset_ids=SETS)
        self.assertTrue(any("label: veld ontbreekt" in f for f in fouten), fouten)

    def test_onbekende_plaatsing(self):
        fouten = valideer_stijl_config(_met(label={"veld": "ids", "plaatsing": "diagonaal"}), kleurenset_ids=SETS)
        self.assertTrue(any("onbekende plaatsing" in f for f in fouten), fouten)

    def test_onbekend_anker(self):
        fouten = valideer_stijl_config(_met(label={"veld": "ids", "anker": "schuin"}), kleurenset_ids=SETS)
        self.assertTrue(any("onbekend anker" in f for f in fouten), fouten)

    def test_veldverwijzing_als_kleur_is_toegestaan(self):
        config = _met(
            lagen=[{"type": "line", "basis": {"kleur": {"veld": "ui_cluster_color"}, "doorzicht": 1}}],
            assen=[],
        )
        self.assertEqual(valideer_stijl_config(config, kleurenset_ids=SETS), [])

    def test_zoomniveaus_gelijk_mag_niet(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": "#000000", "breedte": {"zoom": [[8, 2], [8, 4]]}}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("strikt oplopen (8 → 8)" in f for f in fouten), fouten)

    def test_zoomniveau_negatief(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": "#000000", "breedte": {"zoom": [[-1, 2], [10, 4]]}}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("zoomniveau -1 valt buiten [0, 24]" in f for f in fouten), fouten)

    def test_zoompaar_verkeerde_lengte(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": "#000000", "breedte": {"zoom": [[8, 2, 3]]}}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("elk zoompaar is [zoom, waarde]" in f for f in fouten), fouten)

    def test_sublaag_is_geen_object(self):
        fouten = valideer_stijl_config(_met(lagen=["circle"]), kleurenset_ids=SETS)
        self.assertTrue(any("lagen[0]: sublaag is geen object" in f for f in fouten), fouten)

    def test_as_is_geen_object(self):
        fouten = valideer_stijl_config(_met(assen=["kleur"]), kleurenset_ids=SETS)
        self.assertTrue(any("assen[0]: as is geen object" in f for f in fouten), fouten)

    def test_label_is_geen_object(self):
        fouten = valideer_stijl_config(_met(label="ids"), kleurenset_ids=SETS)
        self.assertTrue(any("label: veld ontbreekt" in f for f in fouten), fouten)

    def test_doorzicht_als_zoomwaarde_met_ongeldige_stop(self):
        """Dekt het recursieve pad van ``_valideer_eenheid``: een stop ín een ZoomWaarde die zelf buiten [0, 1] valt."""
        fouten = valideer_stijl_config(
            _met(
                lagen=[{"type": "line", "basis": {"kleur": "#000000", "doorzicht": {"zoom": [[8, 0.5], [14, 1.4]]}}}]
            ),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("doorzicht 1.4 valt buiten [0, 1]" in f for f in fouten), fouten)

    def test_straal_als_zoomwaarde_met_ongeldige_reeks(self):
        """Dekt de zoom-check voor ``straal``; tot dusver liep alleen ``breedte`` door deze check."""
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "circle", "basis": {"kleur": "#000000", "straal": {"zoom": [[10, 2], [8, 4]]}}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("basis.straal: zoomniveaus moeten strikt oplopen (10 → 8)" in f for f in fouten), fouten)

    # --- De vier gaten uit rgs-django-spatial#5 ---

    def test_label_grootte_als_zoomwaarde_is_geldig(self):
        config = _met(label={"veld": "ids", "grootte": {"zoom": [[11, 1], [12, 8], [22, 20]]}})
        self.assertEqual(valideer_stijl_config(config, kleurenset_ids=SETS), [])
        self.assertEqual(valideer_stijl_config(_met(label={"veld": "ids", "grootte": 12}), kleurenset_ids=SETS), [])

    def test_label_grootte_met_ongeldige_zoomreeks(self):
        fouten = valideer_stijl_config(
            _met(label={"veld": "ids", "grootte": {"zoom": [[12, 8], [11, 1]]}}), kleurenset_ids=SETS
        )
        self.assertTrue(any("label.grootte: zoomniveaus moeten strikt oplopen (12 → 11)" in f for f in fouten), fouten)

    def test_label_grootte_zonder_zoomparen(self):
        fouten = valideer_stijl_config(_met(label={"veld": "ids", "grootte": {}}), kleurenset_ids=SETS)
        self.assertTrue(any("label.grootte: zoom moet minstens één paar bevatten" in f for f in fouten), fouten)

    def test_label_grootte_als_tekst(self):
        fouten = valideer_stijl_config(_met(label={"veld": "ids", "grootte": "groot"}), kleurenset_ids=SETS)
        self.assertTrue(
            any("label.grootte: grootte moet een getal of een ZoomWaarde zijn" in f for f in fouten), fouten
        )

    def test_kleur_ontbreekt(self):
        fouten = valideer_stijl_config(_met(lagen=[{"type": "line", "basis": {"doorzicht": 1}}]), kleurenset_ids=SETS)
        self.assertEqual(fouten, ["lagen[0]: kleur ontbreekt"])

    def test_kleur_als_veldverwijzing_zonder_veld(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": {"zoom": [[8, "#000000"]]}, "doorzicht": 1}}]),
            kleurenset_ids=SETS,
        )
        self.assertTrue(any("lagen[0]: kleur moet een kleur of een veldverwijzing zijn" in f for f in fouten), fouten)

    def test_doorzicht_ontbreekt(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": "#000000"}}]), kleurenset_ids=SETS
        )
        self.assertEqual(fouten, ["lagen[0]: doorzicht ontbreekt"])
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": "#000000", "doorzicht": None}}]), kleurenset_ids=SETS
        )
        self.assertEqual(fouten, ["lagen[0]: doorzicht ontbreekt"])

    def test_doorzicht_moet_een_getal_zijn(self):
        fouten = valideer_stijl_config(
            _met(lagen=[{"type": "line", "basis": {"kleur": "#000000", "doorzicht": "1"}}]), kleurenset_ids=SETS
        )
        self.assertEqual(fouten, ["lagen[0].basis.doorzicht: doorzicht moet een getal in [0, 1] zijn, niet '1'"])

    def test_straal_as_vereist_circle_sublaag(self):
        as_straal = {"veld": "x", "eigenschap": "straal", "modus": "categorieen", "categorieen": [{"waarde": "1"}]}
        fouten = valideer_stijl_config(_met(assen=[as_straal]), kleurenset_ids=SETS)
        self.assertTrue(any("een straal-as vereist een circle-sublaag" in f for f in fouten), fouten)
        config = _met(
            lagen=[{"type": "circle", "basis": {"kleur": "#000000", "doorzicht": 1, "straal": 4}}], assen=[as_straal]
        )
        self.assertEqual(valideer_stijl_config(config, kleurenset_ids=SETS), [])

    def test_breedte_as_vereist_line_circle_of_fill_sublaag(self):
        as_breedte = {"veld": "x", "eigenschap": "breedte", "modus": "categorieen", "categorieen": [{"waarde": "1"}]}
        config = _met(
            lagen=[{"type": "symbol", "basis": {"kleur": "#000000", "doorzicht": 1, "icoon": "puntpeiling"}}],
            assen=[as_breedte],
        )
        fouten = valideer_stijl_config(config, kleurenset_ids=SETS)
        self.assertTrue(any("een breedte-as vereist een line-, circle- of fill-sublaag" in f for f in fouten), fouten)
        for soort in ("line", "circle", "fill"):
            with self.subTest(soort=soort):
                config = _met(
                    lagen=[{"type": soort, "basis": {"kleur": "#000000", "doorzicht": 1}}], assen=[as_breedte]
                )
                self.assertEqual(valideer_stijl_config(config, kleurenset_ids=SETS), [])

    def test_modus_ontbreekt(self):
        # Bewust strenger dan de TS-validator, die terugvalt op 'categorieen'.
        fouten = valideer_stijl_config(
            _met(assen=[{"veld": "x", "eigenschap": "kleur", "categorieen": [{"waarde": "1"}]}]), kleurenset_ids=SETS
        )
        self.assertEqual(fouten, ["assen[0]: modus ontbreekt"])


class HashEnBereikTest(SimpleTestCase):
    def _as(self, **extra):
        return {
            "versie": 3,
            "lagen": [{"type": "line", "basis": {"kleur": "#000000", "doorzicht": 1}}],
            "assen": [{"veld": "a", "eigenschap": "kleur", **extra}],
        }

    def test_hash_is_geldig_met_labelveld_en_ramp(self):
        self.assertEqual(valideer_stijl_config(self._as(modus="hash", labelVeld="b", ramp=["#000000", "#ffffff"])), [])

    def test_hash_op_breedte_wordt_afgekeurd(self):
        c = self._as(modus="hash")
        c["assen"][0]["eigenschap"] = "breedte"
        self.assertTrue(any("hash" in f for f in valideer_stijl_config(c)))

    def test_hash_met_stops_of_ramp_van_een_kleur_wordt_afgekeurd(self):
        self.assertTrue(valideer_stijl_config(self._as(modus="hash", stops=[])))
        self.assertTrue(valideer_stijl_config(self._as(modus="hash", ramp=["#000000"])))
        self.assertTrue(valideer_stijl_config(self._as(modus="hash", ramp=["#000000", "rood"])))

    def test_schaal_met_bereik_data_zonder_stops_is_geldig(self):
        self.assertEqual(valideer_stijl_config(self._as(modus="schaal", bereik="data")), [])
        self.assertTrue(valideer_stijl_config(self._as(modus="schaal", bereik="data", stops=[{"waarde": 1}])))

    def test_bereik_alleen_op_schaal_en_alleen_data(self):
        self.assertTrue(
            valideer_stijl_config(self._as(modus="categorieen", bereik="data", categorieen=[{"waarde": "x"}]))
        )
        self.assertTrue(valideer_stijl_config(self._as(modus="schaal", bereik="alles")))

    def test_bereik_data_kan_alleen_op_kleur_of_halo(self):
        # Spiegel van de lib-regel (rgs-ui-stack#175): de ramp draagt alleen kleuren.
        c = self._as(modus="schaal", bereik="data")
        c["assen"][0]["eigenschap"] = "breedte"
        self.assertTrue(any("kleur" in f for f in valideer_stijl_config(c)))

    def test_ramp_niet_toegestaan_bij_categorieen(self):
        c = self._as(modus="categorieen", categorieen=[{"waarde": "1"}], ramp=["#000000", "#ffffff"])
        fouten = valideer_stijl_config(c)
        self.assertTrue(any("ramp hoort alleen bij modus hash of schaal met bereik data" in f for f in fouten), fouten)

    def test_ramp_niet_toegestaan_bij_kleurenset(self):
        c = self._as(
            modus="kleurenset", kleurensetId="1e529a9d-aba9-507a-81e0-5e0392495cd8", ramp=["#000000", "#ffffff"]
        )
        fouten = valideer_stijl_config(c, kleurenset_ids=SETS)
        self.assertTrue(any("ramp hoort alleen bij modus hash of schaal met bereik data" in f for f in fouten), fouten)

    def test_ramp_niet_toegestaan_bij_stap(self):
        c = self._as(modus="stap", stappen=[{"tot": 1, "kleur": "#000000"}], ramp=["#000000", "#ffffff"])
        fouten = valideer_stijl_config(c)
        self.assertTrue(any("ramp hoort alleen bij modus hash of schaal met bereik data" in f for f in fouten), fouten)

    def test_ramp_niet_toegestaan_bij_schaal_met_stops(self):
        c = self._as(modus="schaal", stops=[{"waarde": 1, "kleur": "#000000"}], ramp=["#000000", "#ffffff"])
        fouten = valideer_stijl_config(c)
        self.assertTrue(any("ramp hoort alleen bij modus hash of schaal met bereik data" in f for f in fouten), fouten)

    def test_ramp_wel_toegestaan_bij_hash_en_bij_schaal_met_bereik_data(self):
        c_hash = self._as(modus="hash", ramp=["#000000", "#ffffff"])
        self.assertFalse(any("ramp hoort alleen bij" in f for f in valideer_stijl_config(c_hash)))
        c_schaal_data = self._as(modus="schaal", bereik="data", ramp=["#000000", "#ffffff"])
        self.assertFalse(any("ramp hoort alleen bij" in f for f in valideer_stijl_config(c_schaal_data)))

    def test_labelveld_niet_toegestaan_buiten_hash(self):
        varianten = [
            {"modus": "categorieen", "categorieen": [{"waarde": "1"}]},
            {"modus": "kleurenset", "kleurensetId": "1e529a9d-aba9-507a-81e0-5e0392495cd8"},
            {"modus": "stap", "stappen": [{"tot": 1, "kleur": "#000000"}]},
            {"modus": "schaal", "stops": [{"waarde": 1, "kleur": "#000000"}]},
        ]
        for extra in varianten:
            with self.subTest(**extra):
                c = self._as(labelVeld="naam", **extra)
                fouten = valideer_stijl_config(c, kleurenset_ids=SETS)
                self.assertTrue(any("labelVeld hoort alleen bij modus hash" in f for f in fouten), fouten)

    def test_labelveld_wel_toegestaan_bij_hash(self):
        c = self._as(modus="hash", labelVeld="naam")
        self.assertFalse(any("labelVeld hoort alleen bij" in f for f in valideer_stijl_config(c)))
