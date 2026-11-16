"""Rutas de la app inventario."""

from django.urls import path

from . import views

# Espacio de nombres: permite usar reverse("inventario:detalle_producto", ...)
# en las pruebas sin escribir las URL a mano.
app_name = "inventario"

urlpatterns = [
    # GET  /api/productos/1/
    path(
        "productos/<int:producto_id>/",
        views.detalle_producto,
        name="detalle_producto",
    ),
    # POST /api/productos/1/comprar/
    path(
        "productos/<int:producto_id>/comprar/",
        views.comprar_producto,
        name="comprar_producto",
    ),
]