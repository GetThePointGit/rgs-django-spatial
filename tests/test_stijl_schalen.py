"""De twee jaarschalen en de twee vormhelpers.

De jaarschalen zijn bewust absoluut (2020–2040 resp. 2000–2030) en niet
relatief aan het huidige jaar: een geseed jaartal veroudert, een vast venster
niet.
"""

from django.test import SimpleTestCase

from rgs_django_spatial.stijl.schalen import jaarschaal_inmeten, jaarschaal_rdylgn, stops, toetsklasseschaal, zoom


class SchalenTest(SimpleTestCase):
    def test_zoom_bouwt_paren(self):
        self.assertEqual(zoom((8, 2), (10, 5), (22, 12)), {"zoom": [[8, 2], [10, 5], [22, 12]]})

    def test_zoom_paren_lopen_strikt_op(self):
        for schaal in (zoom((8, 2), (10, 5), (22, 12)), zoom((6, 0), (22, 12))):
            niveaus = [paar[0] for paar in schaal["zoom"]]
            self.assertEqual(niveaus, sorted(set(niveaus)))

    def test_stops_bouwt_stijlstops(self):
        self.assertEqual(
            stops([(2020, "#a50026"), (2040, "#006837")]),
            [{"waarde": 2020, "kleur": "#a50026"}, {"waarde": 2040, "kleur": "#006837"}],
        )

    def test_jaarschaal_rdylgn(self):
        self.assertEqual(
            jaarschaal_rdylgn(),
            [
                (2020, "#a50026"),
                (2022, "#d73027"),
                (2024, "#f46d43"),
                (2026, "#fdae61"),
                (2028, "#fee08b"),
                (2030, "#ffffbf"),
                (2032, "#d9ef8b"),
                (2034, "#a6d96a"),
                (2036, "#66bd63"),
                (2038, "#1a9850"),
                (2040, "#006837"),
            ],
        )

    def test_jaarschaal_inmeten(self):
        self.assertEqual(
            jaarschaal_inmeten(),
            [
                (2000, "#9f0101"),
                (2007, "#ed6701"),
                (2015, "#eced08"),
                (2022, "#73ff00"),
                (2030, "#015209"),
            ],
        )

    def test_jaarschalen_zijn_oplopend(self):
        for schaal in (jaarschaal_rdylgn(), jaarschaal_inmeten()):
            jaren = [jaar for jaar, _ in schaal]
            self.assertEqual(jaren, sorted(set(jaren)))

    def test_toetsklasseschaal(self):
        self.assertEqual(
            toetsklasseschaal(),
            [
                (0, "#9f0101"),
                (25, "#ed5b01"),
                (50, "#edc708"),
                (75, "#73ff00"),
                (100, "#015209"),
            ],
        )
