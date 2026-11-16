"""
Pruebas unitarias del modelo Producto con django.test.TestCase.

Diferencias frente a unittest.TestCase puro:
- Django crea una base de datos TEMPORAL solo para las pruebas (en memoria con SQLite).
- Esa BD empieza VACÍA: no ve db.sqlite3 ni los productos del fixture.
- Cada prueba se ejecuta dentro de una transacción que se revierte al terminar,
  así que ninguna prueba afecta a otra.

Ejecución:
    python manage.py test inventario.tests.test_models -v 2
"""

from decimal import Decimal

# ValidationError: error que lanza full_clean() cuando un validador falla.
from django.core.exceptions import ValidationError

# IntegrityError: error que lanza la BD cuando se viola una restricción.
# transaction: necesario para aislar un error de BD dentro de la prueba.
from django.db import IntegrityError, transaction

# TestCase de Django: hereda de unittest.TestCase y agrega BD temporal y self.client.
from django.test import TestCase

from inventario.models import Producto


class ProductoModeloTests(TestCase):
    """Pruebas del modelo Producto y de su método descontar_stock()."""

    @classmethod
    def setUpTestData(cls):
        """Crea los datos UNA sola vez para toda la clase (más rápido que setUp).

        Django restaura estos datos antes de cada prueba, así que si una prueba
        descuenta stock, la siguiente vuelve a ver stock = 10.
        """
        cls.producto = Producto.objects.create(
            nombre="Teclado mecánico",
            precio=Decimal("85000.00"),
            stock=10,
        )

    def test_crear_producto_guarda_en_bd(self):
        """El producto creado en setUpTestData existe en la BD temporal."""
        # La BD de pruebas solo contiene lo que creamos aquí: exactamente 1 producto.
        self.assertEqual(Producto.objects.count(), 1)

        # Se lee de nuevo desde la BD para confirmar que se guardó bien.
        guardado = Producto.objects.get(pk=self.producto.pk)
        self.assertEqual(guardado.nombre, "Teclado mecánico")
        self.assertEqual(guardado.precio, Decimal("85000.00"))
        self.assertEqual(guardado.stock, 10)

    def test_str_muestra_nombre_y_stock(self):
        """__str__ debe mostrar el nombre y el stock (se usa en el admin)."""
        self.assertEqual(str(self.producto), "Teclado mecánico (stock: 10)")

    def test_descontar_stock_actualiza_y_persiste(self):
        """Descontar 3 de 10 deja 7, en memoria Y en la base de datos."""
        restante = self.producto.descontar_stock(3)

        # 1) El método retorna el stock restante.
        self.assertEqual(restante, 7)

        # 2) refresh_from_db() vuelve a leer desde la BD: confirma que se GUARDÓ,
        #    no solo que cambió la variable en memoria.
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 7)

    def test_descontar_todo_el_stock_deja_cero(self):
        """Caso límite: comprar exactamente todo el stock es válido y deja 0."""
        self.assertEqual(self.producto.descontar_stock(10), 0)

    def test_stock_insuficiente_lanza_value_error_sin_modificar(self):
        """Pedir más de lo disponible lanza ValueError y NO toca el inventario."""
        # assertRaisesRegex verifica el tipo de error Y que el mensaje coincida.
        with self.assertRaisesRegex(ValueError, "Stock insuficiente"):
            self.producto.descontar_stock(11)

        # El stock en la BD debe seguir intacto.
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 10)

    def test_cantidad_cero_o_negativa_lanza_value_error(self):
        """Cantidades 0 o negativas se rechazan.

        Sin esta validación, descontar_stock(-5) SUMARÍA 5 unidades
        fantasma al inventario: mercancía que no existe.
        """
        for cantidad in (0, -1, -5):
            with self.subTest(cantidad=cantidad):
                with self.assertRaises(ValueError):
                    self.producto.descontar_stock(cantidad)

        # Ninguna de las variantes modificó el stock.
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 10)

    def test_cantidad_no_entera_lanza_value_error(self):
        """Texto, decimales, booleanos y None no son cantidades válidas."""
        for cantidad in ("2", 1.5, True, None):
            with self.subTest(cantidad=cantidad):
                with self.assertRaises(ValueError):
                    self.producto.descontar_stock(cantidad)

    def test_precio_negativo_falla_validacion(self):
        """El validador MinValueValidator rechaza precios negativos.

        Nota: los validadores de campo NO se ejecutan con save();
        se ejecutan con full_clean() (lo que hacen el admin y los formularios).
        """
        producto = Producto(nombre="Producto erróneo", precio=Decimal("-1.00"), stock=1)

        with self.assertRaises(ValidationError) as contexto:
            producto.full_clean()

        # El error debe estar asociado específicamente al campo precio.
        self.assertIn("precio", contexto.exception.message_dict)

    def test_stock_negativo_rechazado_por_base_de_datos(self):
        """PositiveIntegerField crea una restricción CHECK (stock >= 0) en la BD.

        Es una segunda red de seguridad: aunque el código Python fallara,
        la base de datos impide guardar inventario negativo.
        """
        with self.assertRaises(IntegrityError):
            # atomic() aísla el error: sin él, la transacción de la prueba
            # quedaría rota y las consultas siguientes fallarían.
            with transaction.atomic():
                Producto.objects.create(
                    nombre="Stock negativo",
                    precio=Decimal("1000.00"),
                    stock=-1,
                )