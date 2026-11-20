"""Stijlmodel v3 voor kaartlagen: validatie, schaalhelpers en de omzetting van v2 (#22).

Python-spiegel van de stijlvalidatie in ``@getthepointgit/map``. De modules raken geen
Django-model en kennen geen domein van een consumer: ze werken op de dict in
``SpatialStyle.config``.

- :mod:`~rgs_django_spatial.stijl.validatie`: :func:`valideer_stijl_config` geeft de lijst
  fouten van een stijlconfiguratie; een seed breekt daarmee af vóór hij iets wegschrijft dat
  de kaart later weigert;
- :mod:`~rgs_django_spatial.stijl.schalen`: bouwstenen voor stijldefinities (``zoom``,
  ``stops``, kleurenramps en vaste kleurschalen);
- :mod:`~rgs_django_spatial.stijl.conversie`: :func:`converteer_naar_v3` zet een v2-config om.
"""

from rgs_django_spatial.stijl.conversie import converteer_naar_v3, is_v3
from rgs_django_spatial.stijl.validatie import valideer_stijl_config

__all__ = ["converteer_naar_v3", "is_v3", "valideer_stijl_config"]
