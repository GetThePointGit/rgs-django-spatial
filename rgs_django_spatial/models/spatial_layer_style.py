import re
from collections.abc import Iterable

from django.core.exceptions import ValidationError
from rgs_django_utils.database import dj_extended_models as models

from ._sections import section_maps

_MASKER = re.compile(r"[A-Z]+")


def normaliseer_masker(waarde: str | None) -> str | None:
    """Maak een modulemasker schoon: witruimte weg, leeg wordt ``None``.

    Parameters
    ----------
    waarde : str or None
        Ruwe invoer (uit een formulier, Hasura of de seed).

    Returns:
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

    Returns:
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
            fouten[veld] = ["Alleen hoofdletters A-Z, zonder spaties."]
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
            permissions=models.FPerm("---", auth="isu"),
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

    class Meta:
        db_table = "spatial_layer_style"
        verbose_name = "kaartlaag stijl"
        verbose_name_plural = "kaartlaag stijlen"
        ordering = ["layer", "order"]

        constraints = [
            models.UniqueConstraint(
                fields=["layer", "style"],
                name="unique_layer_style",
            )
        ]

    class TableDescription:
        section = section_maps
        order = 6
        modules = "*"

    def _andere_standaard_in(self) -> list[str | None]:
        """Geef ``standaard_in`` van de andere koppelingen op dezelfde laag.

        Returns:
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

        Raises:
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

    def clean(self):
        """Modelvalidatie inclusief de modulevelden (admin/formulieren)."""
        super().clean()
        self._valideer_modules()

    def save(self, *args, **kwargs):
        """Sla op na validatie van de modulevelden.

        Ook ``update_or_create`` (de seed) komt hier langs. Hasura niet: die
        schrijft rechtstreeks in de database, dus de beheer-UI bewaakt de
        één-standaard-per-letter-regel zelf.

        Parameters
        ----------
        *args, **kwargs
            Doorgegeven aan :meth:`django.db.models.Model.save`.
        """
        self._valideer_modules()
        super().save(*args, **kwargs)

    @classmethod
    def get_permissions(cls):
        # Mutaties zijn beheer: alleen org_adm (en staf hoger in de rolketen
        # sys_adm/dev/dev_man) mag laag-stijl-koppelingen
        # aanmaken/wijzigen/verwijderen. `auth` behoudt select.
        # Zie GetThePointGit/rgs-django-spatial#1.
        no_filt = {}

        return models.TPerm(
            public=None,
            auth={
                "select": no_filt,
            },
            org_adm={
                "insert": no_filt,
                "update": no_filt,
                "delete": no_filt,
            },
        )
