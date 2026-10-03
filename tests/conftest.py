"""Gedeelde testfixtures."""

import pytest


@pytest.fixture(autouse=True)
def _toegang_enumrijen(request):
    """Maak de ``enum_access_through``-rijen aan voor tests met een database.

    De scopekolommen (``access_through``) hebben een FK naar die enum; zonder
    rijen faalt de FK-controle bij het afsluiten van elke databasetest.
    """
    if request.node.get_closest_marker("django_db") is None:
        yield
        return
    request.getfixturevalue("db")
    from rgs_django_utils.models.enums.enum_access_through import EnumAccessThrough

    for pk in ("authenticated", "organisation"):
        EnumAccessThrough.objects.get_or_create(id=pk, defaults={"name": pk})
    yield
