"""
Pruebas unitarias de las vistas JSON con django.test.TestCase y self.client.

self.client es un navegador simulado: hace peticiones GET/POST a las URL del
proyecto SIN levantar el servidor (no hace falta runserver) y devuelve la
respuesta para inspeccionar el código HTTP, las cabeceras y el JSON.

Ejecución:
    python manage.py test inventario.tests.test_views -v 2
"""

from decimal import Decimal

from django.test import TestCase

# reverse construye la URL a partir de su nombre ("app:nombre"): si la ruta
# cambia en urls.py, las pruebas siguen funcionando.
from django.urls import reverse

from inventario.models import Producto


class ProductosBaseTestCase(TestCase):
    """Clase base: datos y utilidades comunes para las pruebas de vistas.

    No contiene métodos test_*, así que por sí sola no ejecuta pruebas.
    """

    @classmethod
    def setUpTestData(cls):
        """Tres productos que cubren los escenarios de la demo."""
        # Stock suficiente: para compras exitosas.
        cls.teclado = Producto.objects.create(
            nombre="Teclado mecánico", precio=Decimal("85000.00"), stock=10
        )
        # Stock bajo: para verificar que un error no descuente inventario.
        cls.mouse = Producto.objects.create(
            nombre="Mouse inalámbrico", precio=Decimal("45000.00"), stock=3
        )
        # Sin stock: para el código 400.
        cls.monitor = Producto.objects.create(
            nombre="Monitor 24 pulgadas", precio=Decimal("650000.00"), stock=0
        )

    def url_detalle(self, producto_id):
        """URL de GET /api/productos/<id>/."""
        return reverse("inventario:detalle_producto", args=[producto_id])

    def url_comprar(self, producto_id):
        """URL de POST /api/productos/<id>/comprar/."""
        return reverse("inventario:comprar_producto", args=[producto_id])

    def comprar(self, producto_id, datos):
        """Envía un POST con cuerpo JSON (Django serializa el diccionario)."""
        return self.client.post(
            self.url_comprar(producto_id),
            data=datos,
            content_type="application/json",
        )


class DetalleProductoVistaTests(ProductosBaseTestCase):
    """Pruebas de GET /api/productos/<id>/."""

    def test_detalle_existente_responde_200_con_datos(self):
        """Un producto existente devuelve 200 y su información exacta."""
        respuesta = self.client.get(self.url_detalle(self.teclado.id))

        # Código HTTP.
        self.assertEqual(respuesta.status_code, 200)

        # Contenido: .json() convierte el cuerpo de la respuesta en diccionario.
        self.assertEqual(
            respuesta.json(),
            {
                "id": self.teclado.id,
                "nombre": "Teclado mecánico",
                "precio": "85000.00",
                "stock": 10,
            },
        )

    def test_detalle_inexistente_responde_404_json(self):
        """Un id que no existe devuelve 404 en JSON (no la página HTML de Django)."""
        respuesta = self.client.get(self.url_detalle(9999))

        self.assertEqual(respuesta.status_code, 404)
        # La API siempre debe responder JSON, incluso en los errores.
        self.assertEqual(respuesta["Content-Type"], "application/json")
        self.assertIn("no existe", respuesta.json()["error"])

    def test_detalle_rechaza_metodo_post(self):
        """@require_GET hace que un POST reciba 405 (método no permitido)."""
        respuesta = self.client.post(self.url_detalle(self.teclado.id))
        self.assertEqual(respuesta.status_code, 405)


class ComprarProductoVistaTests(ProductosBaseTestCase):
    """Pruebas de POST /api/productos/<id>/comprar/."""

    def test_compra_exitosa_responde_200_y_descuenta_stock(self):
        """2 teclados con DESC10: factura correcta y stock de 10 a 8."""
        respuesta = self.comprar(self.teclado.id, {"cantidad": 2, "cupon": "DESC10"})

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()

        # Factura: los montos viajan como texto para conservar la exactitud del Decimal.
        factura = datos["factura"]
        self.assertEqual(factura["subtotal"], "170000.00")
        self.assertEqual(factura["descuento"], "17000.00")
        self.assertEqual(factura["iva"], "29070.00")
        self.assertEqual(factura["total"], "182070.00")
        self.assertTrue(factura["envio_gratis"])

        # La respuesta informa el stock restante...
        self.assertEqual(datos["producto"]["stock"], 8)

        # ...y la BD realmente quedó actualizada.
        self.teclado.refresh_from_db()
        self.assertEqual(self.teclado.stock, 8)

    def test_compra_sin_cupon_calcula_factura_correcta(self):
        """1 mouse sin cupón: IVA $8.550, total $53.550, sin envío gratis."""
        respuesta = self.comprar(self.mouse.id, {"cantidad": 1})

        self.assertEqual(respuesta.status_code, 200)
        factura = respuesta.json()["factura"]
        self.assertEqual(factura["descuento"], "0.00")
        self.assertEqual(factura["iva"], "8550.00")
        self.assertEqual(factura["total"], "53550.00")
        self.assertFalse(factura["envio_gratis"])

    def test_stock_insuficiente_responde_400(self):
        """Comprar un producto sin stock devuelve 400 y el inventario sigue en 0."""
        respuesta = self.comprar(self.monitor.id, {"cantidad": 1})

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Stock insuficiente", respuesta.json()["error"])

        self.monitor.refresh_from_db()
        self.assertEqual(self.monitor.stock, 0)

    def test_cupon_invalido_responde_400_y_no_descuenta_stock(self):
        """Prueba de ATOMICIDAD: un cupón inválido no debe dejar stock descontado.

        En la vista, descontar_stock() se ejecuta ANTES de validar el cupón.
        Solo transaction.atomic() revierte ese descuento cuando el cupón falla.
        Si alguien elimina atomic(), esta prueba lo detecta en local.
        """
        respuesta = self.comprar(self.mouse.id, {"cantidad": 1, "cupon": "FALSO50"})

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("no es válido", respuesta.json()["error"])

        # El stock del mouse debe seguir en 3.
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.stock, 3)

    def test_producto_inexistente_responde_404(self):
        """Comprar un id inexistente devuelve 404 en JSON."""
        respuesta = self.comprar(9999, {"cantidad": 1})

        self.assertEqual(respuesta.status_code, 404)
        self.assertIn("no existe", respuesta.json()["error"])

    def test_json_mal_formado_responde_400(self):
        """Un cuerpo que no es JSON válido devuelve 400 (no un error 500)."""
        respuesta = self.client.post(
            self.url_comprar(self.teclado.id),
            data="{esto no es json",
            content_type="application/json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("JSON válido", respuesta.json()["error"])

    def test_cantidad_invalida_responde_400(self):
        """Cantidad 0 se rechaza con 400 y no modifica el stock."""
        respuesta = self.comprar(self.teclado.id, {"cantidad": 0})

        self.assertEqual(respuesta.status_code, 400)
        self.teclado.refresh_from_db()
        self.assertEqual(self.teclado.stock, 10)

    def test_comprar_rechaza_metodo_get(self):
        """@require_POST hace que un GET reciba 405 (comprar debe ser POST)."""
        respuesta = self.client.get(self.url_comprar(self.teclado.id))
        self.assertEqual(respuesta.status_code, 405)