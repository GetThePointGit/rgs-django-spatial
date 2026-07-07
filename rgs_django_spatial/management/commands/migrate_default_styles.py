"""Migreer bestaande default_style-JSON (op spatial_map_layer) naar stijlrecords.

Eenmalig/idempotent: per kaartlaag met een default_style en zonder bestaande
SpatialLayerStyle-records wordt één SpatialStyle + koppeling "Standaard"
aangemaakt. De default_style-kolom blijft staan als overgangs-fallback.
"""
from django.core.management.base import BaseCommand


def wil_migreren(default_style, bestaande_stijl_count: int) -> bool:
    """Bepaal of een kaartlaag een standaard-stijlrecord moet krijgen."""
    return bool(default_style) and bestaande_stijl_count == 0


def zorg_voor_standaard_stijl(map_layer) -> bool:
    """Maak (idempotent) een standaard-stijlrecord voor deze kaartlaag.

    Returns
    -------
    bool
        True als er een record is aangemaakt.
    """
    from rgs_django_spatial.models import SpatialLayerStyle, SpatialStyle

    laag = map_layer.layer
    if not wil_migreren(map_layer.default_style, SpatialLayerStyle.objects.filter(layer=laag).count()):
        return False
    stijl, _ = SpatialStyle.objects.get_or_create(
        name=f"{laag.name} — standaard",
        defaults={"style_config": map_layer.default_style},
    )
    SpatialLayerStyle.objects.get_or_create(
        layer=laag,
        style=stijl,
        defaults={"name": "Standaard", "order": 0, "active": True},
    )
    return True


class Command(BaseCommand):
    help = "Migreer default_style-JSON naar SpatialStyle/SpatialLayerStyle-records (idempotent)."

    def handle(self, *args, **options):
        from rgs_django_spatial.models import SpatialMapLayer

        gedaan = 0
        for ml in SpatialMapLayer.objects.select_related("layer").all():
            if zorg_voor_standaard_stijl(ml):
                gedaan += 1
        self.stdout.write(self.style.SUCCESS(f"Klaar: {gedaan} stijlrecord(s) aangemaakt."))
