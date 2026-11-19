"""Koppeling tussen een kaartlaag en een stijl, met een eigen scope.

Een koppelrij is applicatiebreed, van één organisatie (urbanworks#433) of van
één project (waterworks#548):

- op een **projectlaag** volgt de koppelrij altijd de scope van de laag;
- op een **organisatielaag** volgt de koppelrij de scope van de laag, behalve
  als het een projectrij is: een project mag een eigen rij op een
  organisatielaag hangen;
- op een **applicatiebrede laag** (ook de app-laag) staan de applicatiebrede
  koppelrijen (de standaardstijlen, beheerd door staf) en mag elke organisatie
  eigen rijen hangen: een extra stijl, of een **variant** die via ``vervangt``
  een standaardrij voor die organisatie vervangt. Verdwijnt de variant, dan
  geldt de standaardrij weer;
- een **projectrij** werkt hetzelfde, één niveau dieper: een extra stijl, of
  een variant die via ``vervangt`` een applicatiebrede rij of een rij van een
  organisatie vervangt. ``vervangt`` wijst altijd naar een rij die zelf niets
  vervangt, zodat er geen ketens ontstaan;
- ``standaard`` wijst per scope hoogstens één rij aan als voorgeselecteerde
  stijl. Heeft een scope er geen, dan geldt die van het niveau erboven en
  uiteindelijk ``spatial_map_layer.default_style`` (en ``standaard_in``).

Welke rijen voor een gebruiker gelden, lost de client op (``@getthepointgit/map``):
applicatiebreed plus de actieve organisatie plus het actieve project, min de
vervangen rijen. Volgorde: project, dan organisatie, dan applicatiebreed.

De regels staan op drie plekken: :meth:`SpatialLayerStyle.clean` (formulieren,
ORM), de constraints in ``Meta`` en, omdat Hasura Django omzeilt, de trigger
``spatial_layer_style_scope`` (migratie 0011 en 0012, alleen PostgreSQL).
"""

import re
from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.db.models import Q
from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.models.enums.enum_access_through import EnumAccessThrough

from ._scope import (
    LEES_SCOPE_FILTER,
    ORG_SCOPE_FILTER,
    SCOPES_MET_ID,
    access_id_field,
    access_through_field,
    scope_fperm,
    scoped_table_permissions,
)
from ._sections import section_maps

_MASKER = re.compile(r"[A-Z]+")
_ONBEKEND_TEKEN = re.compile(r"[^A-Za-z]")


def _hoofdletter_hint(waarde: str) -> str | None:
    """Geef een hint als ``waarde`` alleen ongeldig is door kleine letters.

    Parameters
    ----------
    waarde : str
        De ruwe invoer van het veld ``modules`` of ``standaard_in``.

    Returns
    -------
    str or None
        Een melding die de bijbehorende hoofdletters voorstelt, of ``None``
        als ``waarde`` ook tekens bevat die geen letter zijn (die tekens
        krijgen de generieke melding).
    """
    if _ONBEKEND_TEKEN.search(waarde):
        return None
    kleine_letters = sorted({letter.upper() for letter in waarde if letter.islower()})
    if not kleine_letters:
        return None
    return f"Gebruik hoofdletters: {''.join(kleine_letters)}."


def normaliseer_masker(waarde: str | None) -> str | None:
    """Maak een modulemasker schoon: witruimte weg, leeg wordt ``None``.

    Parameters
    ----------
    waarde : str or None
        Ruwe invoer (uit een formulier, Hasura of de seed).

    Returns
    -------
    str or None
        Het masker zonder omringende witruimte, of ``None`` als er niets overblijft.
    """
    if waarde is None:
        return None
    waarde = waarde.strip()
    return waarde or None


def valideer_module_velden(
    modules: str | None,
    standaard_in: str | None,
    andere_standaard_in: Iterable[str | None],
) -> dict[str, list[str]]:
    """Toets ``modules`` en ``standaard_in`` van één stijlkoppeling.

    Parameters
    ----------
    modules : str or None
        Letters waarin de stijl kiesbaar is; ``None`` = alle modules.
    standaard_in : str or None
        Letters waarin de stijl voorgeselecteerd is.
    andere_standaard_in : iterable of str or None
        ``standaard_in`` van de andere koppelingen op dezelfde laag.

    Returns
    -------
    dict of str to list of str
        Foutmeldingen per veld, in de vorm van ``ValidationError.message_dict``.
        Leeg betekent geldig.
    """
    fouten: dict[str, list[str]] = {}
    for veld, waarde in (("modules", modules), ("standaard_in", standaard_in)):
        if waarde is None:
            continue
        if not _MASKER.fullmatch(waarde):
            hint = _hoofdletter_hint(waarde)
            fouten[veld] = [hint] if hint else ["Alleen hoofdletters A-Z, zonder spaties."]
        elif len(set(waarde)) != len(waarde):
            fouten[veld] = ["Elke letter hoogstens één keer."]
    if fouten or standaard_in is None:
        return fouten

    if modules is not None:
        buiten = "".join(letter for letter in standaard_in if letter not in modules)
        if buiten:
            return {"standaard_in": [f"Standaard in {buiten}, maar daar niet beschikbaar (modules={modules})."]}

    bezet = set()
    for andere in andere_standaard_in:
        bezet.update(andere or "")
    dubbel = [letter for letter in standaard_in if letter in bezet]
    if dubbel:
        return {"standaard_in": [f"Deze kaartlaag heeft al een standaardstijl voor {', '.join(dubbel)}."]}
    return {}


class SpatialLayerStyle(models.Model):
    # Expliciet gedeclareerd (matcht de impliciete PK) zodat 'auth' insert mag:
    # de upsert vanuit de frontend conflicteert op spatial_layer_style_pkey en
    # stuurt 'id' mee, dus 'id' moet in de insert_input zitten.
    id = models.BigAutoField(
        primary_key=True,
        config=models.Config(permissions=models.FPerm(auth="is-")),
    )
    layer = models.ForeignKey(
        "SpatialLayer",
        on_delete=models.CASCADE,
        verbose_name="kaartlaag",
        related_name="styles",
        config=models.Config(
            doc_short="Kaartlaag waartoe deze stijl behoort",
            # Alleen bij aanmaken: Hasura kan geen update-check genereren, dus
            # omhangen naar een laag buiten de eigen scope moet op kolomniveau
            # dicht (waterworks-ui#219). Staf mag het wel.
            permissions=models.FPerm("---", auth="is-", sys_adm="isu"),
        ),
    )
    style = models.ForeignKey(
        "SpatialStyle",
        on_delete=models.PROTECT,
        verbose_name="stijl",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Stijl van de kaartlaag",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    name = models.TextStringField(
        verbose_name="naam",
        config=models.Config(
            doc_short="Naam van de kaartbron",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    order = models.IntegerField(
        verbose_name="volgorde",
        config=models.Config(
            doc_short="Volgorde van de stijlen binnen de kaartlaag. Lage getallen worden eerst getoond",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    active = models.BooleanField(
        verbose_name="selecteerbaar",
        default=False,
        config=models.Config(
            doc_short="Geeft aan of deze stijl selecteerbaar is",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    warnings = models.JSONField(
        verbose_name="waarschuwingen",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Eventuele waarschuwingen met betrekking tot deze stijl gekoppeld aan deze laag",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    modules = models.TextStringField(
        verbose_name="modules",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Moduleletters waarin deze stijl beschikbaar is (bv. 'DP'); leeg = alle modules",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    standaard_in = models.TextStringField(
        verbose_name="standaard in",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Moduleletters waarin deze stijl voorgeselecteerd is; per laag hoogstens één stijl per letter",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    # Eigen scope (urbanworks#433, waterworks#548); op een projectlaag altijd die van de laag.
    access_through = access_through_field(
        "Bereik van de stijlkoppeling: applicatiebreed, één organisatie of één project"
    )
    access_id = access_id_field("Organisatie- of project-id als de stijlkoppeling van één organisatie of project is")
    vervangt = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="vervangt",
        related_name="vervangers",
        config=models.Config(
            doc_short=(
                "Stijlkoppeling van dezelfde laag die deze organisatie- of projectrij vervangt "
                "(applicatiebreed, of voor een projectrij ook van een organisatie); "
                "leeg = een eigen extra stijl"
            ),
            # Alleen bij aanmaken (zoals `layer`): er is geen update-check.
            permissions=scope_fperm("---", auth="-s-", org_adm="is-", sys_adm="isu"),
        ),
    )
    standaard = models.BooleanField(
        verbose_name="standaard",
        default=False,
        db_default=False,
        config=models.Config(
            doc_short=(
                "Voorgeselecteerde stijl van de laag binnen deze scope; hoogstens één per laag per scope. "
                "Zonder zo'n rij geldt spatial_map_layer.default_style"
            ),
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    class Meta:
        db_table = "spatial_layer_style"
        verbose_name = "kaartlaag stijl"
        verbose_name_plural = "kaartlaag stijlen"
        ordering = ["layer", "order"]

        constraints = [
            # Laag + stijl uniek per scope: een organisatierij mag dezelfde stijl
            # gebruiken als een standaardrij (andere volgorde of standaard).
            models.UniqueConstraint(
                fields=["layer", "style", "access_through", "access_id"],
                nulls_distinct=False,
                name="unique_layer_style_per_scope",
            ),
            models.UniqueConstraint(
                fields=["layer", "access_through", "access_id"],
                condition=Q(standaard=True),
                nulls_distinct=False,
                name="spatial_layer_style_standaard_per_scope",
            ),
            # Hoogstens één vervanger per vervangen rij per organisatie of project.
            models.UniqueConstraint(
                fields=["vervangt", "access_through", "access_id"],
                condition=Q(vervangt__isnull=False),
                name="spatial_layer_style_vervanger_per_scope",
            ),
            models.CheckConstraint(
                condition=Q(vervangt__isnull=True) | Q(access_through__in=SCOPES_MET_ID),
                name="spatial_layer_style_vervangt_met_scope",
            ),
        ]

    class TableDescription:
        section = section_maps
        order = 6
        modules = "*"

    def _andere_standaard_in(self) -> list[str | None]:
        """Geef ``standaard_in`` van de andere koppelingen op dezelfde laag.

        Returns
        -------
        list of str or None
            Eén waarde per andere koppeling; ``None`` als die nergens standaard is.
        """
        return list(
            SpatialLayerStyle.objects.filter(layer_id=self.layer_id)
            .exclude(pk=self.pk)
            .values_list("standaard_in", flat=True)
        )

    def _valideer_modules(self) -> None:
        """Normaliseer en toets de modulevelden.

        Raises
        ------
        django.core.exceptions.ValidationError
            Met de meldingen per veld uit :func:`valideer_module_velden`.
        """
        self.modules = normaliseer_masker(self.modules)
        self.standaard_in = normaliseer_masker(self.standaard_in)
        andere = self._andere_standaard_in() if self.standaard_in else []
        fouten = valideer_module_velden(self.modules, self.standaard_in, andere)
        if fouten:
            raise ValidationError(fouten)

    def _volg_laagscope(self) -> None:
        """Neem op een project- of organisatielaag de scope van de laag over.

        Op een projectlaag altijd; op een organisatielaag behalve als de rij een
        projectrij is. Zelfde regel als de trigger ``spatial_layer_style_scope``;
        hier herhaald zodat de instantie na ``save()`` klopt en de regel ook
        zonder PostgreSQL geldt.
        """
        if self.layer_id is None:
            return
        laag = self.layer
        van_project = self.access_through_id == EnumAccessThrough.PROJECT
        if laag.access_through_id == EnumAccessThrough.PROJECT or (
            laag.access_through_id == EnumAccessThrough.ORGANISATION and not van_project
        ):
            self.access_through_id = laag.access_through_id
            self.access_id = laag.access_id

    def _valideer_scope(self) -> None:
        """Toets scope, ``vervangt`` en ``standaard`` van deze koppelrij.

        Raises
        ------
        django.core.exceptions.ValidationError
            Met de meldingen per veld.
        """
        fouten: dict[str, list[str]] = {}
        van_org = self.access_through_id == EnumAccessThrough.ORGANISATION
        van_project = self.access_through_id == EnumAccessThrough.PROJECT
        if van_org and self.access_id is None:
            fouten["access_id"] = ["Een stijlkoppeling van een organisatie heeft een organisatie-id nodig."]
        if van_project and self.access_id is None:
            fouten["access_id"] = ["Een stijlkoppeling van een project heeft een project-id nodig."]
        if not (van_org or van_project) and self.access_id is not None:
            fouten["access_id"] = ["Een applicatiebrede stijlkoppeling heeft geen organisatie-id."]

        # Een organisatiestijl hoort bij een rij van die organisatie, of bij een
        # projectrij (het pakket weet niet van welke organisatie een project is;
        # of de stijl leesbaar is bepaalt de leesregel van de stijl zelf). Een
        # projectstijl hoort alleen bij een rij van dat project.
        stijl = self.style if self.style_id is not None else None
        if stijl is not None and stijl.access_through_id == EnumAccessThrough.ORGANISATION:
            if not van_project and (not van_org or stijl.access_id != self.access_id):
                fouten["style"] = ["De stijl is van een andere organisatie dan deze stijlkoppeling."]
        if stijl is not None and stijl.access_through_id == EnumAccessThrough.PROJECT:
            if not van_project or stijl.access_id != self.access_id:
                fouten["style"] = ["De stijl is van een ander project dan deze stijlkoppeling."]

        if self.vervangt_id is not None:
            doel = self.vervangt
            vervangbaar = [EnumAccessThrough.AUTHENTICATED]
            if van_project:
                vervangbaar.append(EnumAccessThrough.ORGANISATION)
            if not (van_org or van_project):
                fouten["vervangt"] = [
                    "Alleen een stijlkoppeling van een organisatie of project kan een andere stijl vervangen."
                ]
            elif doel.pk == self.pk or doel.layer_id != self.layer_id:
                fouten["vervangt"] = ["De vervangen stijlkoppeling hoort bij een andere kaartlaag."]
            elif doel.vervangt_id is not None:
                fouten["vervangt"] = ["Een stijlkoppeling die zelf iets vervangt kan niet vervangen worden."]
            elif doel.access_through_id not in vervangbaar:
                fouten["vervangt"] = (
                    [
                        "Een projectrij kan alleen een applicatiebrede stijlkoppeling of die van een organisatie vervangen."
                    ]
                    if van_project
                    else ["Alleen een applicatiebrede stijlkoppeling kan vervangen worden."]
                )
            elif (
                SpatialLayerStyle.objects.filter(
                    vervangt_id=self.vervangt_id,
                    access_through_id=self.access_through_id,
                    access_id=self.access_id,
                )
                .exclude(pk=self.pk)
                .exists()
            ):
                fouten["vervangt"] = (
                    ["Dit project heeft al een variant van deze stijl."]
                    if van_project
                    else ["Deze organisatie heeft al een variant van deze standaardstijl."]
                )

        if self.standaard and (
            SpatialLayerStyle.objects.filter(
                layer_id=self.layer_id,
                access_through_id=self.access_through_id,
                access_id=self.access_id,
                standaard=True,
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            fouten["standaard"] = ["Deze kaartlaag heeft binnen deze scope al een standaardstijl."]
        if fouten:
            raise ValidationError(fouten)

    def clean(self):
        """Modelvalidatie inclusief de modulevelden en de scope (admin/formulieren)."""
        super().clean()
        self._valideer_modules()
        self._volg_laagscope()
        self._valideer_scope()

    def save(self, *args, **kwargs):
        """Sla op na validatie van de modulevelden en de scope.

        Ook ``update_or_create`` (de seed) komt hier langs. Hasura niet: die
        schrijft rechtstreeks in de database, dus de beheer-UI bewaakt de
        één-standaard-per-letter-regel zelf. De scoperegels (``vervangt``,
        ``standaard``, scope van laag en stijl, ook op projectniveau) dwingt de
        database voor Hasura af met constraints en de trigger
        ``spatial_layer_style_scope``.

        Parameters
        ----------
        *args, **kwargs
            Doorgegeven aan :meth:`django.db.models.Model.save`.
        """
        self._valideer_modules()
        self._volg_laagscope()
        self._valideer_scope()
        super().save(*args, **kwargs)

    @classmethod
    def get_permissions(cls):
        # Eigen scope (urbanworks#433): org_adm muteert alleen koppelrijen van de
        # actieve organisatie, ook op een applicatiebrede laag; staf alles. De
        # insert-check eist bovendien dat de laag applicatiebreed of van de eigen
        # organisatie is. Lezen (met SPATIAL_RESTRICT_READ): de rij én haar laag
        # zijn applicatiebreed of van de actieve organisatie.
        return scoped_table_permissions(
            ORG_SCOPE_FILTER,
            read_filter={"_and": [LEES_SCOPE_FILTER, {"layer": LEES_SCOPE_FILTER}]},
            org_adm_insert={"_and": [ORG_SCOPE_FILTER, {"layer": LEES_SCOPE_FILTER}]},
            tabel=cls._meta.db_table,
        )
