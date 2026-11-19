"""Omzetting van v2-stijlconfiguraties naar het v3-contract.

Het v2-contract is ``{"type": ..., "paint": ..., "editor": {"basis": ...,
"assen": ...}}``; v3 is ``{"versie": 3, "lagen": [...], "assen": [...]}``. De
rauwe ``paint`` verhuist ongewijzigd naar de sublaag en wint in de lib van de
uit ``basis`` en ``assen`` afgeleide paint — daarmee rendert een geconverteerde
stijl per constructie identiek aan wat hij vóór de conversie deed. ``basis``
voedt alleen de editor.

Deze module raakt geen Django-model: hij zet één dict om naar een andere. Het
wegschrijven doet de consumer (in waterworks het commando ``migreer_stijlen_v3``).
"""

import copy

STANDAARD_KLEUR = "#888888"
STANDAARD_DOORZICHT = 1

# Paint-sleutels per sublaagtype waaruit ``basis`` afgeleid wordt als een
# v2-rij geen ``editor`` heeft.
BASIS_UIT_PAINT = {
    "circle": {"kleur": "circle-color", "doorzicht": "circle-opacity", "straal": "circle-radius"},
    "line": {"kleur": "line-color", "doorzicht": "line-opacity", "breedte": "line-width"},
    "fill": {"kleur": "fill-color", "doorzicht": "fill-opacity"},
}


def is_v3(config) -> bool:
    """Bepaal of een stijlconfiguratie al in het v3-contract staat.

    Parameters
    ----------
    config : Any
        De waarde uit ``SpatialStyle.style_config``.

    Returns
    -------
    bool
        ``True`` als het een object met ``versie == 3`` is.
    """
    return isinstance(config, dict) and config.get("versie") == 3


def _is_getal(waarde) -> bool:
    """Bepaal of een waarde een letterlijk getal is.

    Een bool is in Python een int, maar geen zinnige straal of breedte; een
    MapLibre-expressie is een lijst en dus ook geen letterlijke waarde.

    Parameters
    ----------
    waarde : Any
        De te toetsen waarde uit de paint.

    Returns
    -------
    bool
        ``True`` bij een int of float die geen bool is.
    """
    return isinstance(waarde, (int, float)) and not isinstance(waarde, bool)


def _basis_uit_paint(soort, paint: dict) -> dict:
    """Bouw een ``basis`` uit de rauwe paint van een v2-rij zonder editor.

    Alleen letterlijke waarden worden overgenomen: een MapLibre-expressie is
    een lijst en kan de editor niet tonen. De rendering komt uit ``paint``, dus
    een benadering hier raakt het beeld niet.

    Parameters
    ----------
    soort : str or None
        Het sublaagtype (``"circle"``, ``"line"`` of ``"fill"``).
    paint : dict
        De rauwe paint van de v2-rij.

    Returns
    -------
    dict
        Een ``basis`` met altijd ``kleur`` en ``doorzicht``.
    """
    sleutels = BASIS_UIT_PAINT.get(soort, {})
    kleur = paint.get(sleutels.get("kleur", ""))
    doorzicht = paint.get(sleutels.get("doorzicht", ""))

    basis = {
        "kleur": kleur if isinstance(kleur, str) else STANDAARD_KLEUR,
        "doorzicht": doorzicht if _is_getal(doorzicht) else STANDAARD_DOORZICHT,
    }
    for naam in ("straal", "breedte"):
        waarde = paint.get(sleutels.get(naam, ""))
        if _is_getal(waarde):
            basis[naam] = waarde
    return basis


def _ontdubbel_assen(assen: list) -> tuple[list, bool]:
    """Houd per eigenschap alleen de eerste as aan.

    v2 stond twee assen op dezelfde eigenschap toe, v3 niet. Een letterlijke
    conversie zou de stijl ongeldig maken, waarna de app hem helemaal
    overslaat — slechter dan een benadering.

    Parameters
    ----------
    assen : list
        De assen uit ``editor.assen``.

    Returns
    -------
    tuple of (list, bool)
        De overgehouden assen, en of er iets is weggelaten.
    """
    gezien = set()
    behouden = []
    for as_definitie in assen:
        eigenschap = as_definitie.get("eigenschap") if isinstance(as_definitie, dict) else None
        if eigenschap in gezien:
            continue
        gezien.add(eigenschap)
        behouden.append(as_definitie)
    return behouden, len(behouden) != len(assen)


def converteer_naar_v3(config: dict) -> tuple[dict, str]:
    """Zet één stijlconfiguratie om naar het v3-contract.

    Parameters
    ----------
    config : dict
        Een v2-configuratie (``type``/``paint``/``editor``) of een die al v3 is.

    Returns
    -------
    tuple of (dict, str)
        De v3-configuratie en de status: ``"al-v3"`` als er niets te doen was,
        ``"geconverteerd"`` bij een volledige omzetting, ``"benaderd"`` als er
        iets uit de paint is afgeleid of een dubbele as is weggelaten.
    """
    if is_v3(config):
        return config, "al-v3"

    soort = config.get("type")
    paint = config.get("paint") or {}
    editor = config.get("editor")
    editor_basis = editor.get("basis") if isinstance(editor, dict) else None

    afgeleid = _basis_uit_paint(soort, paint)
    if isinstance(editor_basis, dict) and editor_basis:
        # De editor wint; alleen ontbrekende sleutels worden aangevuld, want
        # de validator wijst een sublaag zonder doorzicht af.
        basis = {**afgeleid, **copy.deepcopy(editor_basis)}
        benaderd = any(sleutel not in editor_basis for sleutel in ("kleur", "doorzicht"))
        # Een afgeleide straal/breedte hoort niet bij een editor die die niet
        # kent: het type bepaalt of hij zinvol is, en de editor is leidend.
        for naam in ("straal", "breedte"):
            if naam not in editor_basis:
                basis.pop(naam, None)
    else:
        basis = afgeleid
        benaderd = True

    laag = {"type": soort, "basis": basis}
    if paint:
        laag["paint"] = copy.deepcopy(paint)

    v3 = {"versie": 3, "lagen": [laag]}

    assen = copy.deepcopy(editor.get("assen")) if isinstance(editor, dict) else None
    if assen:
        assen, ontdubbeld = _ontdubbel_assen(assen)
        benaderd = benaderd or ontdubbeld
        v3["assen"] = assen

    return v3, "benaderd" if benaderd else "geconverteerd"
