"""Rutas principales del proyecto."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Panel de administración de Django.
    path("admin/", admin.site.urls),
    # Todas las rutas de la API de inventario quedan bajo el prefijo /api/.
    path("api/", include("inventario.urls")),
]