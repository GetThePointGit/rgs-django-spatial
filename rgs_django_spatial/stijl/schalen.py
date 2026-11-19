"""Zoomwaardes en kleurschalen voor de stijldefinities.

Een jaarschaal is geen kleurenset: een kleurenset houdt categorieën, een
jaarschaal is een as met ``stops``. Beide jaarschalen staan hier zodat de
stijlmodules er één bron voor hebben.
"""

# Kleurenramps voor schaal-assen met ``bereik: "data"`` (min/max uit de data);
# gekopieerd uit ``kleur-ramps.ts`` in waterworks-ui, licht → donker.
RAMP_BLAUW = ["#e8f1fb", "#b6d4f5", "#74aeea", "#3a82d2", "#1b4f8f"]
RAMP_AMBER = ["#fdf3dd", "#f8dd9a", "#f0bd4e", "#d9941a", "#a1660a"]


def zoom(*paren: tuple[float, float]) -> dict:
    """Bouw een ``ZoomWaarde`` uit (zoomniveau, waarde)-paren.

    Parameters
    ----------
    *paren : tuple of (float, float)
        Paren van zoomniveau en waarde, met strikt oplopende zoomniveaus
        binnen [0, 24].

    Returns
    -------
    dict
        ``{"zoom": [[niveau, waarde], ...]}``.
    """
    return {"zoom": [[niveau, waarde] for niveau, waarde in paren]}


def stops(paren) -> list[dict]:
    """Zet (waarde, kleur)-paren om in ``StijlStop``-objecten.

    Parameters
    ----------
    paren : iterable of (float, str)
        Drempelwaarde en bijbehorende kleur.

    Returns
    -------
    list of dict
        Lijst van ``{"waarde": ..., "kleur": ...}``.
    """
    return [{"waarde": waarde, "kleur": kleur} for waarde, kleur in paren]


def jaarschaal_rdylgn() -> list[tuple[int, str]]:
    """RdYlGn-schaal 2020–2040 voor gepland en berekend baggerjaar.

    Returns
    -------
    list of (int, str)
        Jaartal en kleur, oplopend.
    """
    return [
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
    ]


def jaarschaal_inmeten() -> list[tuple[int, str]]:
    """Schaal 2000–2030 voor het jaar van inmeten.

    Returns
    -------
    list of (int, str)
        Jaartal en kleur, oplopend.
    """
    return [
        (2000, "#9f0101"),
        (2007, "#ed6701"),
        (2015, "#eced08"),
        (2022, "#73ff00"),
        (2030, "#015209"),
    ]


def toetsklasseschaal() -> list[tuple[int, str]]:
    """Kleurschaal 0–100 voor een toetsklasse (``c_class``).

    Dezelfde schaal voor watergangen en profiellocaties: één toetsklasse
    vervangt de vijf losse criteriumstijlen van de oude WIT.

    Returns
    -------
    list of (int, str)
        Klassewaarde en kleur, oplopend.
    """
    return [
        (0, "#9f0101"),
        (25, "#ed5b01"),
        (50, "#edc708"),
        (75, "#73ff00"),
        (100, "#015209"),
    ]
