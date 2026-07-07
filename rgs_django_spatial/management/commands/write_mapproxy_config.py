"""Schrijf de gegenereerde MapProxy-config naar een map (lokale docker-compose)."""
import os

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Schrijf de gegenereerde MapProxy-config als <output_dir>/urbanworks.yaml."

    def add_arguments(self, parser):
        parser.add_argument("output_dir")

    def handle(self, *args, **options):
        from rgs_django_spatial.mapproxy import render_mapproxy_yaml

        os.makedirs(options["output_dir"], exist_ok=True)
        dst = os.path.join(options["output_dir"], "urbanworks.yaml")
        with open(dst, "w", encoding="utf-8") as f:
            f.write(render_mapproxy_yaml())
        self.stdout.write(self.style.SUCCESS(f"Geschreven: {dst}"))
