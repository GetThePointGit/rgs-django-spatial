"""App-configuratie van rgs_django_spatial."""

from django.apps import AppConfig


class RgsDjangoSpatialConfig(AppConfig):
    """Sluit de guard op app-rijen aan (zie :mod:`rgs_django_spatial.app_lagen`)."""

    name = "rgs_django_spatial"

    def ready(self):
        """Verbind de ``pre_save``/``pre_delete``-receivers voor bronnen en lagen."""
        from django.db.models.signals import pre_delete, pre_save

        from . import app_lagen
        from .models import SpatialLayer, SpatialSource

        for model in (SpatialLayer, SpatialSource):
            pre_delete.connect(
                app_lagen.controleer_voor_verwijderen, sender=model, dispatch_uid=f"app_laag_del_{model.__name__}"
            )
            pre_save.connect(
                app_lagen.controleer_voor_opslaan, sender=model, dispatch_uid=f"app_laag_save_{model.__name__}"
            )
