"""
Modelos de la app inventario.
Producto es la entidad cuyo stock representa mercancía real: si el inventario
queda mal, se venden productos que no existen (dinero devuelto, clientes molestos).
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Producto(models.Model):
    """Producto disponible para la venta en la tienda."""

    # Nombre visible del producto.
    nombre = models.CharField("nombre", max_length=100)

    # Precio unitario en pesos. DecimalField guarda valores exactos (no float).
    # El validador impide precios negativos en formularios y en el admin.
    precio = models.DecimalField(
        "precio",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )

    # Unidades disponibles. PositiveIntegerField agrega además una restricción
    # en la base de datos (>= 0): una segunda red de seguridad debajo del código.
    stock = models.PositiveIntegerField("stock", default=0)

    class Meta:
        # Nombres legibles en el panel de administración.
        verbose_name = "producto"
        verbose_name_plural = "productos"
        # Orden por defecto en las consultas.
        ordering = ["nombre"]

    def __str__(self):
        """Representación legible (usada en el admin y en la consola)."""
        return f"{self.nombre} (stock: {self.stock})"

    def descontar_stock(self, cantidad):
        """Descuenta unidades del inventario y guarda el cambio.

        Parámetros:
            cantidad: número entero de unidades a descontar (mayor que cero).

        Retorna:
            int con el stock restante después de descontar.

        Lanza:
            ValueError: si la cantidad no es un entero positivo
                        o si no hay stock suficiente.
        """
        # Se rechazan tipos inválidos (ej. "2", 1.5, True). bool es subclase de int.
        if isinstance(cantidad, bool) or not isinstance(cantidad, int):
            raise ValueError("La cantidad debe ser un número entero.")

        # Comprar 0 o una cantidad negativa no tiene sentido (y un negativo SUMARÍA stock).
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor que cero.")

        # Regla central: no se puede vender más de lo que hay.
        if cantidad > self.stock:
            raise ValueError(
                f"Stock insuficiente para '{self.nombre}': "
                f"solicitado {cantidad}, disponible {self.stock}."
            )

        # Se actualiza el valor en memoria.
        self.stock -= cantidad

        # Se guarda SOLO el campo stock (más eficiente y no pisa otros campos).
        self.save(update_fields=["stock"])

        return self.stock