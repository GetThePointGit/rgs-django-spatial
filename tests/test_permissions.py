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
