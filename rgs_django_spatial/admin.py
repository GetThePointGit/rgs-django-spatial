from django.contrib import admin

from rgs_django_spatial import models


class SpatialMapLayerInline(admin.TabularInline):
    model = models.SpatialMapLayer
    extra = 1
    fields = ("layer", "order", "visible", "default_opacity")
    readonly_fields = ()
    ordering = ("order",)


@admin.register(models.SpatialMap)
class SpatialMapAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "access_through", "access_id", "order")
    list_filter = ("access_through",)
    list_editable = ("order",)
    search_fields = ("name", "description")
    inlines = [SpatialMapLayerInline]
    ordering = ("order",)
    readonly_fields = (
        "default_extent",
        "warnings",
    )


class SpatialLayerStyleInline(admin.TabularInline):
    model = models.SpatialLayerStyle
    extra = 1
    fields = ("style", "order")
    readonly_fields = ()
    ordering = ("order",)


@admin.register(models.SpatialLayer)
class SpatialLayerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "access_through", "access_id")
    list_filter = ("access_through",)
    search_fields = ("name", "description")
    inlines = [SpatialLayerStyleInline]


@admin.register(models.SpatialSource)
class SpatialSourceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "source_type",
    )
    list_filter = ("source_type",)
    search_fields = ("name", "description")


@admin.register(models.SpatialStyle)
class SpatialStyleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
    )
    search_fields = ("name",)


@admin.register(models.SpatialTheme)
class SpatialThemeAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    search_fields = ("name",)
