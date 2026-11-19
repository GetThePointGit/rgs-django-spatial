"""Python-spiegel van de v3-stijlvalidator uit ``@getthepointgit/map``.

De backend kan de TypeScript-validator niet draaien. Deze functie controleert
de regels uit §2 van de stijlmodel-v3-spec, zodat het seed-command afbreekt
vóór het JSON wegschrijft die de lib later weigert.

Bewuste afwijkingen van de TS-validator (strenger, omdat de seed de bron is
en geen half ingevulde stijl mag wegschrijven):

- een onbekende ``kleurensetId`` is hier een fout, in TS een waarschuwing;
- een as zonder ``modus`` is hier een fout, TS valt terug op ``categorieen``;
- ``basis.kleur`` moet aanwezig zijn (een kleur of een veldverwijzing), TS
  controleert dat veld niet.
"""

import re

SUBLAAG_TYPEN = frozenset({"circle", "line", "fill", "symbol"})
GEOMETRIEEN = frozenset({"punt", "lijn", "vlak"})
EIGENSCHAPPEN = frozenset({"kleur", "straal", "breedte", "doorzicht", "halo"})
MODI = frozenset({"categorieen", "schaal", "stap", "kleurenset", "hash"})
BREEDTE_TYPEN = frozenset({"line", "circle", "fill"})

# Welke sublaagtypen een as op deze eigenschap vereist (TS: eigenschappenVoorTypes).
VEREISTE_SUBLAGEN = {
    "straal": (frozenset({"circle"}), "een straal-as vereist een circle-sublaag"),
    "breedte": (BREEDTE_TYPEN, "een breedte-as vereist een line-, circle- of fill-sublaag"),
    "halo": (frozenset({"symbol"}), "een halo-as vereist een symbol-sublaag"),
}
PLAATSINGEN = frozenset({"punt", "lijn", "lijnmidden"})
ANKERS = frozenset({"centrum", "onder", "boven", "linksonder"})

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

# Welke payload elke as-modus verplicht meebrengt.
MODUS_PAYLOAD = {
    "categorieen": ("categorieen", "categorieen ontbreken"),
    "schaal": ("stops", "stops ontbreken"),
    "stap": ("stappen", "stappen ontbreken"),
}


def _valideer_zoom(waarde, pad, fouten):
    """Toets een ``ZoomWaarde``: paren, strikt oplopend, binnen [0, 24].

    Parameters
    ----------
    waarde : dict
        Het ``{"zoom": [...]}``-object.
    pad : str
        Pad voor in de foutmelding, bijvoorbeeld ``"lagen[0].basis.breedte"``.
    fouten : list of str
        Lijst waaraan foutmeldingen worden toegevoegd.
    """
    paren = waarde.get("zoom")
    if not isinstance(paren, list) or not paren:
        fouten.append(f"{pad}: zoom moet minstens één paar bevatten")
        return
    vorige = None
    for paar in paren:
        if not isinstance(paar, (list, tuple)) or len(paar) != 2:
            fouten.append(f"{pad}: elk zoompaar is [zoom, waarde]")
            return
        niveau = paar[0]
        if not isinstance(niveau, (int, float)) or isinstance(niveau, bool) or not 0 <= niveau <= 24:
            fouten.append(f"{pad}: zoomniveau {niveau!r} valt buiten [0, 24]")
            return
        if vorige is not None and niveau <= vorige:
            fouten.append(f"{pad}: zoomniveaus moeten strikt oplopen ({vorige} → {niveau})")
            return
        vorige = niveau


def _valideer_eenheid(waarde, pad, sleutel, fouten):
    """Toets een doorzicht-achtige waarde: getal in [0, 1], of zo'n ZoomWaarde.

    Bij een ``ZoomWaarde`` loopt de toets recursief door de stops, zodat ook
    een stopwaarde die zelf buiten [0, 1] valt gemeld wordt.

    Parameters
    ----------
    waarde : int, float or dict
        De te toetsen waarde: een getal, een veldverwijzing (``{"veld": ...}``)
        of een ``ZoomWaarde`` (``{"zoom": [...]}``).
    pad : str
        Pad voor in de foutmelding, bijvoorbeeld ``"lagen[0].basis.doorzicht"``.
    sleutel : str
        Naam van de sleutel (bijvoorbeeld ``"doorzicht"``), voor in de foutmelding.
    fouten : list of str
        Lijst waaraan foutmeldingen worden toegevoegd.

    Returns
    -------
    None
        Foutmeldingen komen in ``fouten`` terecht; deze functie geeft niets terug.
    """
    if isinstance(waarde, dict):
        if "veld" in waarde:
            return
        _valideer_zoom(waarde, pad, fouten)
        for paar in waarde.get("zoom") or []:
            if isinstance(paar, (list, tuple)) and len(paar) == 2:
                _valideer_eenheid(paar[1], pad, sleutel, fouten)
        return
    if not isinstance(waarde, (int, float)) or isinstance(waarde, bool):
        fouten.append(f"{pad}: {sleutel} moet een getal in [0, 1] zijn, niet {waarde!r}")
    elif not 0 <= waarde <= 1:
        fouten.append(f"{pad}: {sleutel} {waarde} valt buiten [0, 1]")


def _valideer_sublaag(laag, pad, fouten):
    """Toets één sublaag en geef het sublaagtype terug (of ``None``).

    Parameters
    ----------
    laag : dict
        Eén item uit ``lagen``.
    pad : str
        Pad voor in de foutmelding, bijvoorbeeld ``"lagen[0]"``.
    fouten : list of str
        Lijst waaraan foutmeldingen worden toegevoegd.

    Returns
    -------
    str or None
        Het sublaagtype (``"circle"``, ``"line"``, ``"fill"`` of ``"symbol"``),
        of ``None`` als ``laag`` geen object is.
    """
    if not isinstance(laag, dict):
        fouten.append(f"{pad}: sublaag is geen object")
        return None

    soort = laag.get("type")
    if soort not in SUBLAAG_TYPEN:
        fouten.append(f"{pad}: onbekend sublaagtype {soort!r}")

    geometrie = laag.get("geometrie")
    if geometrie is not None and geometrie not in GEOMETRIEEN:
        fouten.append(f"{pad}: onbekende geometrie {geometrie!r}")

    basis = laag.get("basis")
    if not isinstance(basis, dict):
        fouten.append(f"{pad}: basis ontbreekt")
        return soort

    kleur = basis.get("kleur")
    if kleur is None:
        fouten.append(f"{pad}: kleur ontbreekt")
    elif not (isinstance(kleur, str) or (isinstance(kleur, dict) and kleur.get("veld"))):
        fouten.append(f"{pad}: kleur moet een kleur of een veldverwijzing zijn, niet {kleur!r}")

    if basis.get("doorzicht") is None:
        fouten.append(f"{pad}: doorzicht ontbreekt")
    for sleutel in ("doorzicht", "doorzichtBijState"):
        if basis.get(sleutel) is not None:
            _valideer_eenheid(basis[sleutel], f"{pad}.basis.{sleutel}", sleutel, fouten)

    for sleutel in ("straal", "breedte", "icoonGrootte"):
        if isinstance(basis.get(sleutel), dict) and "veld" not in basis[sleutel]:
            _valideer_zoom(basis[sleutel], f"{pad}.basis.{sleutel}", fouten)

    if "straal" in basis and soort != "circle":
        fouten.append(f"{pad}: straal hoort alleen bij een circle-sublaag")
    if "breedte" in basis and soort not in BREEDTE_TYPEN:
        fouten.append(f"{pad}: breedte hoort niet bij een {soort}-sublaag")
    if "halo" in basis and soort != "symbol":
        fouten.append(f"{pad}: halo hoort alleen bij een symbol-sublaag")

    return soort


def _valideer_ramp(ramp, pad, fouten):
    """Toets een optionele kleurenramp: minstens twee ``#rrggbb``-kleuren.

    Parameters
    ----------
    ramp : list of str or None
        De ``ramp`` van een hash- of bereik-as; ``None`` betekent "standaardramp".
    pad : str
        Pad voor in de foutmelding, bijvoorbeeld ``"assen[0]"``.
    fouten : list of str
        Lijst waaraan foutmeldingen worden toegevoegd.
    """
    if ramp is None:
        return
    if not isinstance(ramp, list) or len(ramp) < 2 or not all(isinstance(k, str) and HEX.match(k) for k in ramp):
        fouten.append(f"{pad}: ramp moet minstens twee hex-kleuren (#rrggbb) bevatten")


def _valideer_as(as_definitie, pad, typen, kleurenset_ids, gezien, fouten):
    """Toets één as en registreer de gebruikte eigenschap in ``gezien``.

    Parameters
    ----------
    as_definitie : dict
        Eén item uit ``assen``.
    pad : str
        Pad voor in de foutmelding, bijvoorbeeld ``"assen[0]"``.
    typen : set of str
        Sublaagtypen die in deze stijlconfiguratie voorkomen, om te toetsen
        dat de gestuurde eigenschap bij minstens één sublaag hoort
        (``VEREISTE_SUBLAGEN``).
    kleurenset_ids : container of str
        Ids van de kleurensets die in dezelfde seed bestaan.
    gezien : set of str
        Eigenschappen die al door een eerdere as gebruikt zijn; wordt hier
        bijgewerkt.
    fouten : list of str
        Lijst waaraan foutmeldingen worden toegevoegd.

    Returns
    -------
    None
        Foutmeldingen komen in ``fouten`` terecht; deze functie geeft niets terug.
    """
    if not isinstance(as_definitie, dict):
        fouten.append(f"{pad}: as is geen object")
        return

    if not as_definitie.get("veld"):
        fouten.append(f"{pad}: veld ontbreekt")

    eigenschap = as_definitie.get("eigenschap")
    if eigenschap not in EIGENSCHAPPEN:
        fouten.append(f"{pad}: onbekende eigenschap {eigenschap!r}")
    elif eigenschap in gezien:
        fouten.append(f"{pad}: tweede as op eigenschap {eigenschap!r}")
    else:
        gezien.add(eigenschap)

    if eigenschap in VEREISTE_SUBLAGEN:
        vereist, melding = VEREISTE_SUBLAGEN[eigenschap]
        if not typen & vereist:
            fouten.append(f"{pad}: {melding}")

    modus = as_definitie.get("modus")
    if modus is None:
        fouten.append(f"{pad}: modus ontbreekt")
        return
    if modus not in MODI:
        fouten.append(f"{pad}: onbekende modus {modus!r}")
        return

    bereik = as_definitie.get("bereik")
    if bereik is not None and (bereik != "data" or modus != "schaal"):
        fouten.append(f"{pad}: bereik kan alleen 'data' zijn, op een schaal-as")

    # ramp en labelVeld doen alleen iets bij modus 'hash' (allebei) en, voor
    # ramp, bij 'schaal' met bereik 'data'. Bij elke andere modus (categorieen,
    # kleurenset, stap, schaal zonder bereik data) worden ze stilzwijgend
    # genegeerd door de lib; hier is dat een fout, zodat een stijl niet een
    # ramp/labelVeld bevat die nergens gebruikt wordt.
    if "ramp" in as_definitie and not (modus == "hash" or (modus == "schaal" and bereik == "data")):
        fouten.append(f"{pad}: ramp hoort alleen bij modus hash of schaal met bereik data")
    if "labelVeld" in as_definitie and modus != "hash":
        fouten.append(f"{pad}: labelVeld hoort alleen bij modus hash")

    if modus == "hash":
        if eigenschap != "kleur":
            fouten.append(f"{pad}: modus 'hash' kan alleen op eigenschap 'kleur'")
        for sleutel in ("categorieen", "stops", "stappen", "kleurensetId"):
            if sleutel in as_definitie:
                fouten.append(f"{pad}: {sleutel} hoort niet bij modus 'hash'")
        if "labelVeld" in as_definitie and not isinstance(as_definitie["labelVeld"], str):
            fouten.append(f"{pad}: labelVeld moet een veldnaam zijn")
        _valideer_ramp(as_definitie.get("ramp"), pad, fouten)
        return
    if modus == "schaal" and bereik == "data":
        # De ramp draagt alleen kleuren; voor een getalseigenschap is er geen
        # bereik-equivalent (zelfde regel als in de lib).
        if eigenschap not in ("kleur", "halo"):
            fouten.append(f"{pad}: bereik 'data' kan alleen op eigenschap 'kleur' of 'halo'")
        if "stops" in as_definitie:
            fouten.append(f"{pad}: bereik 'data' en stops sluiten elkaar uit")
        _valideer_ramp(as_definitie.get("ramp"), pad, fouten)
        return

    if modus == "kleurenset":
        kleurenset = as_definitie.get("kleurensetId")
        if not kleurenset:
            fouten.append(f"{pad}: kleurensetId ontbreekt bij modus 'kleurenset'")
        elif str(kleurenset) not in kleurenset_ids:
            fouten.append(f"{pad}: onbekende kleurensetId {kleurenset}")
        return

    if modus in MODUS_PAYLOAD:
        sleutel, melding = MODUS_PAYLOAD[modus]
        if not as_definitie.get(sleutel):
            fouten.append(f"{pad}: {melding} bij modus {modus!r}")


def _valideer_label(label, fouten):
    """Toets het labelblok.

    Parameters
    ----------
    label : dict
        Het ``label``-object uit de stijlconfiguratie.
    fouten : list of str
        Lijst waaraan foutmeldingen worden toegevoegd.

    Returns
    -------
    None
        Foutmeldingen komen in ``fouten`` terecht; deze functie geeft niets terug.
    """
    if not isinstance(label, dict) or not label.get("veld"):
        fouten.append("label: veld ontbreekt")
        return
    plaatsing = label.get("plaatsing")
    if plaatsing is not None and plaatsing not in PLAATSINGEN:
        fouten.append(f"label: onbekende plaatsing {plaatsing!r}")
    anker = label.get("anker")
    if anker is not None and anker not in ANKERS:
        fouten.append(f"label: onbekend anker {anker!r}")
    grootte = label.get("grootte")
    if grootte is None or (isinstance(grootte, (int, float)) and not isinstance(grootte, bool)):
        return
    if isinstance(grootte, dict):
        _valideer_zoom(grootte, "label.grootte", fouten)
    else:
        fouten.append(f"label.grootte: grootte moet een getal of een ZoomWaarde zijn, niet {grootte!r}")


def valideer_stijl_config(config, *, kleurenset_ids=frozenset()) -> list[str]:
    """Toets één v3-stijlconfiguratie.

    Parameters
    ----------
    config : dict
        Het ``style_config``-object zoals het naar de database gaat.
    kleurenset_ids : container of str, optional
        Ids van de kleurensets die in dezelfde seed bestaan. Een as met modus
        ``"kleurenset"`` die daarbuiten wijst, is een fout.

    Returns
    -------
    list of str
        Foutmeldingen; een lege lijst betekent dat de configuratie geldig is.
    """
    if not isinstance(config, dict):
        return ["stijlconfig is geen object"]

    fouten: list[str] = []
    if config.get("versie") != 3:
        fouten.append(f"versie moet 3 zijn, niet {config.get('versie')!r}")

    lagen = config.get("lagen")
    if not isinstance(lagen, list) or not lagen:
        fouten.append("lagen moet minstens één sublaag bevatten")
        lagen = []

    typen = set()
    for index, laag in enumerate(lagen):
        soort = _valideer_sublaag(laag, f"lagen[{index}]", fouten)
        if soort is not None:
            typen.add(soort)

    gezien: set[str] = set()
    for index, as_definitie in enumerate(config.get("assen") or []):
        _valideer_as(as_definitie, f"assen[{index}]", typen, kleurenset_ids, gezien, fouten)

    if config.get("label") is not None:
        _valideer_label(config["label"], fouten)

    return fouten
