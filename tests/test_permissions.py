"""Tabel-permissies van de spatial_*-modellen: mutaties alleen voor org_adm.

Dekt GetThePointGit/rgs-django-spatial#1 / GetThePointGit/waterworks#376:
`select` blijft voor elke ingelogde gebruiker (`auth`) beschikbaar, maar
insert/update/delete zijn verplaatst naar `org_adm` (en erven dus door naar
staf hoger in de rolketen: sys_adm -> dev -> dev_man). `SpatialMap` is in dit
ticket niet aangepast (blijft select-only voor `auth`) en dient als
negatieve controle.
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

    def test_org_adm_gets_full_crud(self):
        for model in MUTATION_MODELS:
            with self.subTest(model=model.__name__):
                perms = self.helper.get_rol_table_permissions(model)
                self.assertEqual(perms["org_adm"]["select"], {}, f"{model.__name__}: org_adm erft select van auth")
                self.assertEqual(perms["org_adm"]["insert"], {}, f"{model.__name__}: org_adm moet mogen inserten")
                self.assertEqual(perms["org_adm"]["update"], {}, f"{model.__name__}: org_adm moet mogen updaten")
                self.assertEqual(perms["org_adm"]["delete"], {}, f"{model.__name__}: org_adm moet mogen deleten")

    def test_staff_roles_inherit_org_adm_mutation_rights(self):
        """sys_adm/dev/dev_man erven mutatierechten via de rolketen naar org_adm."""
        for model in MUTATION_MODELS:
            for role in ("sys_adm", "dev", "dev_man"):
                with self.subTest(model=model.__name__, role=role):
                    perms = self.helper.get_rol_table_permissions(model)
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
