"""
Pruebas unitarias de calculos.py con unittest PURO (biblioteca estándar de Python).

Puntos clave para la exposición:
- Las clases heredan de unittest.TestCase, NO de django.test.TestCase.
- No se necesita base de datos, servidor ni configuración de Django.
- Se ejecutan en milisegundos: son la primera y más barata red de seguridad.

Todas las pruebas siguen el patrón AAA:
    Preparar (Arrange) -> Ejecutar (Act) -> Verificar (Assert)

Ejecución solo con Python:
    python -m unittest inventario.tests.test_calculos -v
Ejecución con el ejecutor de Django:
    python manage.py test inventario.tests.test_calculos -v 2
"""

# unittest: framework de pruebas incluido en Python (no requiere instalación).
import unittest

# Decimal: los resultados del módulo son Decimal, así que se comparan con Decimal.
from decimal import Decimal

# Funciones a probar. Import absoluto para que funcione con python -m unittest.
from inventario.calculos import (
    aplica_envio_gratis,
    calcular_descuento,
    calcular_iva,
    calcular_total,
)


class CalcularDescuentoTests(unittest.TestCase):
    """Pruebas de calcular_descuento(): cupones válidos, inválidos y entradas erróneas."""

    def test_sin_cupon_no_hay_descuento(self):
        """Sin cupón (None o cadena vacía) el descuento debe ser 0."""
        # subTest ejecuta la misma verificación con varios datos y, si una
        # variante falla, indica cuál fue sin detener las demás.
        for cupon in (None, ""):
            with self.subTest(cupon=cupon):
                self.assertEqual(calcular_descuento(100000, cupon), Decimal("0.00"))

    def test_cupon_desc10_descuenta_10_por_ciento(self):
        """DESC10 sobre $100.000 debe descontar $10.000."""
        # Preparar: datos de entrada.
        subtotal = 100000
        # Ejecutar: se llama la función bajo prueba.
        descuento = calcular_descuento(subtotal, "DESC10")
        # Verificar: el resultado debe ser exactamente el esperado.
        self.assertEqual(descuento, Decimal("10000.00"))

    def test_cupon_desc20_descuenta_20_por_ciento(self):
        """DESC20 sobre $100.000 debe descontar $20.000."""
        self.assertEqual(calcular_descuento(100000, "DESC20"), Decimal("20000.00"))

    def test_cupon_ignora_mayusculas_y_espacios(self):
        """El cupón se normaliza: '  desc10 ' equivale a 'DESC10'."""
        self.assertEqual(calcular_descuento(100000, "  desc10 "), Decimal("10000.00"))

    def test_cupon_inexistente_lanza_value_error(self):
        """Un cupón que no existe debe rechazarse, no ignorarse en silencio."""
        # assertRaises como gestor de contexto: la prueba PASA solo si el
        # bloque lanza ValueError. Si no se lanza nada, la prueba FALLA.
        with self.assertRaises(ValueError) as contexto:
            calcular_descuento(100000, "FALSO50")
        # Además del tipo de error, se verifica que el mensaje sea útil.
        self.assertIn("no es válido", str(contexto.exception))

    def test_subtotal_negativo_lanza_value_error(self):
        """Un subtotal negativo nunca es válido en una compra."""
        with self.assertRaises(ValueError):
            calcular_descuento(-5000, "DESC10")

    def test_valores_no_numericos_lanzan_value_error(self):
        """Texto, None, booleanos y NaN deben rechazarse como subtotal."""
        # True es subclase de int en Python: sin validación pasaría como 1.
        for valor in ("abc", None, True, float("nan")):
            with self.subTest(valor=valor):
                with self.assertRaises(ValueError):
                    calcular_descuento(valor)


class CalcularIvaTests(unittest.TestCase):
    """Pruebas de calcular_iva(): tarifa del 19 %, redondeo y errores."""

    def test_iva_19_por_ciento(self):
        """El IVA de $100.000 debe ser $19.000."""
        # El tercer argumento (msg) se muestra en la terminal si la prueba falla.
        self.assertEqual(
            calcular_iva(100000),
            Decimal("19000.00"),
            "El IVA en Colombia es del 19 %",
        )

    def test_iva_de_cero_es_cero(self):
        """Base 0 produce IVA 0 (caso límite inferior)."""
        self.assertEqual(calcular_iva(0), Decimal("0.00"))

    def test_iva_redondea_a_dos_decimales(self):
        """10.05 x 0.19 = 1.9095, que con redondeo comercial queda en 1.91."""
        self.assertEqual(calcular_iva("10.05"), Decimal("1.91"))

    def test_base_negativa_lanza_value_error(self):
        """No existe IVA sobre una base negativa."""
        with self.assertRaises(ValueError):
            calcular_iva(-1)


class EnvioGratisTests(unittest.TestCase):
    """Pruebas de aplica_envio_gratis(): regla 'total MAYOR a $100.000'."""

    def test_total_mayor_al_umbral_tiene_envio_gratis(self):
        """$100.001 supera el umbral: envío gratis."""
        self.assertTrue(aplica_envio_gratis(100001))

    def test_total_igual_al_umbral_no_tiene_envio_gratis(self):
        """Valor límite: exactamente $100.000 NO tiene envío gratis.

        Esta es la prueba que detecta el clásico error de escribir >= en lugar de >.
        """
        self.assertFalse(
            aplica_envio_gratis(100000),
            "Con exactamente $100.000 NO debe haber envío gratis",
        )

    def test_total_menor_al_umbral_no_tiene_envio_gratis(self):
        """$99.999 está por debajo del umbral: se cobra envío."""
        self.assertFalse(aplica_envio_gratis(99999))

    def test_total_negativo_lanza_value_error(self):
        """Un total negativo es un dato corrupto y debe rechazarse."""
        with self.assertRaises(ValueError):
            aplica_envio_gratis(-100)


class CalcularTotalTests(unittest.TestCase):
    """Pruebas de calcular_total(): integración de todas las reglas de la factura."""

    def test_total_con_cupon_desc10(self):
        """$100.000 con DESC10 -> base $90.000, IVA $17.100, total $107.100."""
        resultado = calcular_total(100000, "DESC10")

        # Se verifica cada línea del desglose: un error en cualquiera es dinero real.
        self.assertEqual(resultado["subtotal"], Decimal("100000.00"))
        self.assertEqual(resultado["descuento"], Decimal("10000.00"))
        self.assertEqual(resultado["base_gravable"], Decimal("90000.00"))
        self.assertEqual(resultado["iva"], Decimal("17100.00"))
        self.assertEqual(resultado["total"], Decimal("107100.00"))
        self.assertTrue(resultado["envio_gratis"])

    def test_total_sin_cupon_por_debajo_del_umbral(self):
        """$50.000 sin cupón -> IVA $9.500, total $59.500, sin envío gratis."""
        resultado = calcular_total(50000)

        self.assertEqual(resultado["descuento"], Decimal("0.00"))
        self.assertEqual(resultado["iva"], Decimal("9500.00"))
        self.assertEqual(resultado["total"], Decimal("59500.00"))
        self.assertFalse(resultado["envio_gratis"])

    def test_descuento_puede_quitar_el_envio_gratis(self):
        """Regla de negocio: el envío se evalúa DESPUÉS del descuento.

        $90.000 sin cupón  -> total $107.100 -> con envío gratis.
        $90.000 con DESC20 -> total $85.680  -> sin envío gratis.
        """
        sin_cupon = calcular_total(90000)
        con_cupon = calcular_total(90000, "DESC20")

        self.assertEqual(sin_cupon["total"], Decimal("107100.00"))
        self.assertTrue(sin_cupon["envio_gratis"])

        self.assertEqual(con_cupon["total"], Decimal("85680.00"))
        self.assertFalse(con_cupon["envio_gratis"])

    def test_float_impreciso_se_redondea_correctamente(self):
        """Demuestra por qué el dinero no se maneja con float.

        En float, 0.1 + 0.2 da 0.30000000000000004; el módulo debe dejarlo en 0.30.
        """
        # Comportamiento conocido de float (no es un error del módulo).
        self.assertNotEqual(0.1 + 0.2, 0.3)
        # El módulo convierte a Decimal y redondea a dos decimales.
        resultado = calcular_total(0.1 + 0.2)
        self.assertEqual(resultado["subtotal"], Decimal("0.30"))