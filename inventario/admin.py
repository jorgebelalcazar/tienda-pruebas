"""Registro del modelo en el panel de administración de Django."""

from django.contrib import admin

from .models import Producto


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    """Configuración del listado de productos en el admin."""

    # Columnas visibles en la tabla.
    list_display = ("id", "nombre", "precio", "stock")

    # Caja de búsqueda por nombre.
    search_fields = ("nombre",)

    # Permite editar el stock directamente desde el listado (útil en la demo).
    list_editable = ("stock",)