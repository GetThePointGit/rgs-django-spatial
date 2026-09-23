"""Tabel-permissies van de spatial_*-modellen.

Dekt GetThePointGit/rgs-django-spatial#1 / GetThePointGit/waterworks#376 en
de organisatie-scope uit GetThePointGit/waterworks-ui#219: `select` blijft
voor elke ingelogde gebruiker (`auth`) beschikbaar; insert/update/delete
zijn voor `org_adm`, beperkt tot rijen van de actieve organisatie (laag, bron,
thema en de koppeltabellen via hun laag). Staf (sys_adm -> dev -> dev_man)
heeft een eigen regel zonder rijfilter. `SpatialMap` is niet aangepast
(blijft select-only voor `auth`) en dient als negatieve controle.
"""

from django.test import SimpleTestCase, override_settings
from rgs_django_utils.database.permission_helper import PermissionHelper

from rgs_django_spatial.models import (
    SpatialKleurenset,
    SpatialLayer,
    SpatialLayerStyle,
    SpatialMap,
    SpatialMapLayer,
    SpatialSource,
    SpatialStyle,
    SpatialTheme,
)
from rgs_django_spatial.models._scope import ORG_SCOPE_FILTER

# Zelfde rolketen als settings.PERMISSION_TREE in waterworks (verkort tot de
# takken die hier relevant zijn): auth -> org_mem -> org_uman -> org_adm ->
# sys_adm -> dev -> dev_man. Staf erft org_adm via deze keten.
TEST_TREE = {
    "public": [],
    "auth": ["public"],
    "org_mem": ["auth"],
    "org_uman": ["org_mem"],
    "org_adm": ["org_uman"],
    "sys_adm": ["org_adm"],
    "dev": ["sys_adm"],
    "dev_man": ["dev"],
}

MUTATION_MODELS = [
    SpatialLayer,
    SpatialSource,
    SpatialTheme,
    SpatialMapLayer,
    SpatialStyle,
    SpatialLayerStyle,
    SpatialKleurenset,
]

SCOPE_FILTERS = {
    SpatialLayer: ORG_SCOPE_FILTER,
    SpatialSource: ORG_SCOPE_FILTER,
    SpatialTheme: ORG_SCOPE_FILTER,
    SpatialMapLayer: {"layer": ORG_SCOPE_FILTER},
    SpatialLayerStyle: {"layer": ORG_SCOPE_FILTER},
}


@override_settings(PERMISSION_TREE=TEST_TREE)
class TestSpatialMutationPermissionsMovedToOrgAdm(SimpleTestCase):
    """`auth` mag alleen selecteren; org_adm (en staf) mag muteren."""

    def setUp(self):
        self.helper = PermissionHelper()

    def test_auth_keeps_select_only(self):
        for model in MUTATION_MODELS:
            with self.subTest(model=model.__name__):
                perms = self.helper.get_rol_table_permissions(model)
                self.assertEqual(perms["auth"]["select"], {}, f"{model.__name__}: auth moet select behouden")
                self.assertIsNone(perms["auth"]["insert"], f"{model.__name__}: auth mag niet meer insert")
                self.assertIsNone(perms["auth"]["update"], f"{model.__name__}: auth mag niet meer update")
                self.assertIsNone(perms["auth"]["delete"], f"{model.__name__}: auth mag niet meer delete")

    def test_org_adm_muteert_alleen_binnen_de_eigen_organisatie(self):
        """Laag/bron/thema: rijfilter op de actieve organisatie (waterworks-ui#219)."""
        for model, filt in SCOPE_FILTERS.items():
            with self.subTest(model=model.__name__):
                perms = self.helper.get_rol_table_permissions(model)
                self.assertEqual(perms["org_adm"]["insert"], filt)
                self.assertEqual(perms["org_adm"]["update"], filt)
                self.assertEqual(perms["org_adm"]["delete"], filt)

    def test_org_adm_select_blijft_breed_behalve_bij_bronnen(self):
        """Lezen is nog niet afgeschermd (waterworks#548).

        Alleen de org_adm-select op spatial_source is beperkt, omdat org_adm de
        credentials mag lezen.
        """
        for model in MUTATION_MODELS:
            with self.subTest(model=model.__name__):
                perms = self.helper.get_rol_table_permissions(model)
                verwacht = ORG_SCOPE_FILTER if model is SpatialSource else {}
                self.assertEqual(perms["org_adm"]["select"], verwacht)

    def test_org_adm_muteert_ongebonden_stijlen_en_kleurensets_vrij(self):
        """Stijlen en kleurensets hebben nog geen scope (vervolgticket waterworks#548)."""
        for model in (SpatialStyle, SpatialKleurenset):
            with self.subTest(model=model.__name__):
                perms = self.helper.get_rol_table_permissions(model)
                self.assertEqual(perms["org_adm"]["insert"], {})
                self.assertEqual(perms["org_adm"]["update"], {})
                self.assertEqual(perms["org_adm"]["delete"], {})

    def test_staf_muteert_alles_zonder_rijfilter(self):
        """sys_adm/dev/dev_man: expliciete regel, erft het org_adm-filter niet.

        Staf heeft vaak geen x-hasura-org-id.
        """
        for model in MUTATION_MODELS:
            for role in ("sys_adm", "dev", "dev_man"):
                with self.subTest(model=model.__name__, role=role):
                    perms = self.helper.get_rol_table_permissions(model)
                    self.assertEqual(perms[role]["select"], {})
                    self.assertEqual(perms[role]["insert"], {})
                    self.assertEqual(perms[role]["update"], {})
                    self.assertEqual(perms[role]["delete"], {})

    def test_org_mem_and_org_uman_have_no_mutation_rights(self):
        """org_mem/org_uman zitten tussen auth en org_adm in en mogen niet muteren."""
        for model in MUTATION_MODELS:
            for role in ("org_mem", "org_uman"):
                with self.subTest(model=model.__name__, role=role):
                    perms = self.helper.get_rol_table_permissions(model)
                    self.assertEqual(perms[role]["select"], {}, f"{model.__name__}/{role}: select via auth")
                    self.assertIsNone(perms[role]["insert"])
                    self.assertIsNone(perms[role]["update"])
                    self.assertIsNone(perms[role]["delete"])

    def test_spatial_map_is_unaffected_select_only(self):
        """SpatialMap valt buiten dit ticket: blijft select-only voor auth, geen org_adm-mutaties."""
        perms = self.helper.get_rol_table_permissions(SpatialMap)
        self.assertEqual(perms["auth"]["select"], {})
        self.assertIsNone(perms["auth"]["insert"])
        self.assertIsNone(perms["auth"]["update"])
        self.assertIsNone(perms["auth"]["delete"])
        self.assertIsNone(perms["org_adm"]["insert"])
        self.assertIsNone(perms["org_adm"]["update"])
        self.assertIsNone(perms["org_adm"]["delete"])


@override_settings(PERMISSION_TREE=TEST_TREE)
class TestSpatialSourceAuthenticationConfigIsSecret(SimpleTestCase):
    """``authentication_config`` draagt het credential zelf, niet alleen metadata.

    Dekt I-N2 (eindreview 2026-09-13-rechtenmodel-en-organisatie-scoping,
    fixronde A3): tot deze test was het veld ``FPerm("---", auth="isu")`` net
    als elk ander veld op ``SpatialSource``, waardoor élke ingelogde
    gebruiker -- van elke organisatie, met of zonder lidmaatschap -- de
    authenticatiegegevens van álle kaartbronnen kon lezen via een gewone
    ``select`` op ``spatial_source``. Alleen ``org_adm`` (en staf hoger in de
    keten) mag het veld nog lezen of schrijven; dat is dezelfde rol die de
    rij zelf al mag muteren (``get_permissions()``), dus dit versmalt geen
    bestaande workflow. ``source_config`` (url/upstream, geen credentials) en
    ``authentication_type`` (alleen het type) blijven bewust wel op
    ``auth="isu"`` staan -- die twee zijn negatieve controles hieronder.
    """

    def setUp(self):
        self.helper = PermissionHelper()

    def test_org_adm_en_staf_mogen_het_geheim_lezen_en_schrijven(self):
        field_perms = self.helper.get_rol_field_permissions(SpatialSource)["authentication_config"]
        for role in ("org_adm", "sys_adm", "dev", "dev_man"):
            with self.subTest(role=role):
                self.assertTrue(field_perms[role]["select"], f"{role} moet authentication_config mogen lezen")
                self.assertTrue(field_perms[role]["insert"], f"{role} moet authentication_config mogen zetten")
                self.assertTrue(field_perms[role]["update"], f"{role} moet authentication_config mogen wijzigen")

    def test_gewone_rollen_mogen_het_geheim_niet_lezen(self):
        """auth/org_mem/org_uman: wel lid, geen beheerder -- geen toegang tot het geheim."""
        field_perms = self.helper.get_rol_field_permissions(SpatialSource)["authentication_config"]
        for role in ("public", "auth", "org_mem", "org_uman"):
            with self.subTest(role=role):
                self.assertFalse(field_perms[role]["select"], f"{role} mag authentication_config niet lezen")
                self.assertFalse(field_perms[role]["insert"], f"{role} mag authentication_config niet zetten")
                self.assertFalse(field_perms[role]["update"], f"{role} mag authentication_config niet wijzigen")

    def test_niet_geheime_velden_blijven_voor_elke_ingelogde_gebruiker_leesbaar(self):
        """Negatieve controle: source_config en authentication_type zijn geen geheim."""
        field_perms = self.helper.get_rol_field_permissions(SpatialSource)
        for field in ("source_config", "authentication_type_id"):
            with self.subTest(field=field):
                self.assertTrue(field_perms[field]["auth"]["select"], f"{field} moet leesbaar blijven voor auth")


@override_settings(PERMISSION_TREE=TEST_TREE)
class TestScopeKolommen(SimpleTestCase):
    """access_through/access_id: org_adm zet ze bij aanmaken, alleen staf wijzigt ze."""

    def setUp(self):
        self.helper = PermissionHelper()

    def test_rechten_op_scopekolommen(self):
        for model in (SpatialLayer, SpatialSource, SpatialTheme):
            field_perms = self.helper.get_rol_field_permissions(model)
            for kolom in ("access_through_id", "access_id"):
                with self.subTest(model=model.__name__, kolom=kolom):
                    perms = field_perms[kolom]
                    self.assertTrue(perms["auth"]["select"])
                    self.assertFalse(perms["auth"]["insert"])
                    self.assertTrue(perms["org_adm"]["insert"])
                    self.assertFalse(perms["org_adm"]["update"], "org_adm mag de scope niet omzetten")
                    self.assertTrue(perms["sys_adm"]["update"])
                    self.assertNotIn("preset_insert", perms["org_adm"])

    def test_naam_uniek_per_scope(self):
        for model in (SpatialLayer, SpatialSource, SpatialTheme):
            with self.subTest(model=model.__name__):
                self.assertFalse(model._meta.get_field("name").unique)
                constraint = next(c for c in model._meta.constraints if c.name.endswith("_name_per_scope"))
                self.assertEqual(tuple(constraint.fields), ("name", "access_through", "access_id"))
                self.assertIs(constraint.nulls_distinct, False)

    def test_scope_default_is_applicatiebreed(self):
        for model in (SpatialLayer, SpatialSource, SpatialTheme):
            with self.subTest(model=model.__name__):
                veld = model._meta.get_field("access_through")
                self.assertEqual(veld.default, "authenticated")
                self.assertEqual(veld.db_default, "authenticated")
