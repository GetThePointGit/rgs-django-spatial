"""Ververs PMTiles van WFS-bronnen waarvan het refresh-interval is verstreken.

Draait serieel en synchroon (bedoeld voor een Kubernetes CronJob of handmatig
in dev). Interval komt van de kleinste ``refresh_interval`` (minuten) van de
gekoppelde lagen; een bron zonder geslaagde build is altijd aan de beurt.
"""
from django.core.management.base import BaseCommand
from django.db.models import Min
from django.utils import timezone

# Spiegelt rgs_django_spatial.tiles.spatial_service.WFS_SOURCE_TYPE; niet top-level van
# spatial_service importeren, want dat trekt (via pmtiles) indirect osgeo/GDAL
# binnen — te zwaar voor een simpele stringvergelijking in dit commando.
WFS_SOURCE_TYPE = "wfs"

# Hoe lang een bron in 'bezig' mag staan voordat we 'm als vastgelopen
# (stale) beschouwen, bv. door een pod-restart mid-build.
STALE_BEZIG_MIN = 60


def is_due(source_type_id, tile_status, tiles_updated_at, refresh_interval_min, now) -> bool:
    """Bepaal of een bron ververst moet worden (pure functie, testbaar)."""
    if source_type_id != WFS_SOURCE_TYPE:
        return False
    if tile_status == "bezig":
        # Een normale build zet 'bezig' vlak voor het werk en ruimt het zelf
        # weer op (→ 'klaar'/'fout'). Staat 'bezig' er nog na een pod-restart
        # mid-build, dan blijft dat anders voor altijd hangen. Behandel het
        # dan als stale en probeer opnieuw: build_tiles_for_source doet een
        # atomic replace met idempotente output, dus een eventuele dubbele
        # (overlappende) build is onschadelijk.
        if tiles_updated_at is None:
            return True
        return (now - tiles_updated_at).total_seconds() >= STALE_BEZIG_MIN * 60
    if tiles_updated_at is None:
        return True
    if refresh_interval_min is None:
        return False
    return (now - tiles_updated_at).total_seconds() >= refresh_interval_min * 60


class Command(BaseCommand):
    help = "Genereer PMTiles opnieuw voor WFS-bronnen waarvan het verversingsinterval is verstreken."

    def handle(self, *args, **options):
        from rgs_django_spatial.models import SpatialSource

        from rgs_django_spatial.tiles.spatial_service import build_tiles_for_source

        now = timezone.now()
        gedaan = 0
        qs = SpatialSource.objects.filter(source_type_id=WFS_SOURCE_TYPE).annotate(
            min_interval=Min("spatiallayer__refresh_interval"),
        )
        for src in qs:
            if not is_due(src.source_type_id, src.tile_status, src.tiles_updated_at, src.min_interval, now):
                continue
            self.stdout.write(f"Verversen: {src.name} (id {src.id})")
            build_tiles_for_source(src.id)  # synchroon; zet zelf klaar/fout
            gedaan += 1
        self.stdout.write(self.style.SUCCESS(f"Klaar: {gedaan} bron(nen) ververst."))
