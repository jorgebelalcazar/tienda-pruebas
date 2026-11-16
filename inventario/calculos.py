"""
Módulo: calculos.py
Lógica de negocio del carrito escrita en Python PURO: no importa nada de Django.

¿Por qué separarla del framework?
- Se puede probar en milisegundos, sin base de datos ni servidor.
- Es justo la parte donde un error de cálculo se convierte en dinero real
  perdido (o cobrado de más) en producción.

Decisión técnica: usamos Decimal y NO float. El tipo float no representa
exactamente valores como 0.1, y en dinero eso produce diferencias de centavos
que, multiplicadas por miles de ventas, se vuelven pérdidas reales.
"""

# Decimal: aritmética exacta para dinero.
# InvalidOperation: error que lanza Decimal cuando recibe algo que no es un número.
# ROUND_HALF_UP: redondeo "comercial" (0.5 sube), el que espera un cliente.
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# ---------------------------------------------------------------------------
# Constantes de negocio: centralizadas aquí para cambiarlas en un solo lugar.
# ---------------------------------------------------------------------------

# Tarifa general de IVA en Colombia (19 %), expresada como fracción.
TASA_IVA = Decimal("0.19")

# Las compras con total ESTRICTAMENTE MAYOR a este valor tienen envío gratis.
UMBRAL_ENVIO_GRATIS = Decimal("100000")

# Cupones válidos: código del cupón y porcentaje de descuento como fracción.
CUPONES = {
    "DESC10": Decimal("0.10"),  # 10 % de descuento
    "DESC20": Decimal("0.20"),  # 20 % de descuento
}

# Precisión con la que se redondean todos los montos (dos decimales).
DOS_DECIMALES = Decimal("0.01")


# ---------------------------------------------------------------------------
# Funciones auxiliares (privadas: el prefijo _ indica uso interno del módulo).
# ---------------------------------------------------------------------------

def _a_decimal(valor, nombre_campo):
    """Convierte un valor a Decimal y valida que sea un número finito y no negativo.

    Parámetros:
        valor: número recibido (int, float, str numérico o Decimal).
        nombre_campo: texto usado en el mensaje de error (ej. "El subtotal").

    Retorna:
        Decimal con el valor convertido.

    Lanza:
        ValueError: si no es un número válido o si es negativo.
    """
    # En Python, bool es subclase de int: True pasaría como 1. Lo bloqueamos.
    if isinstance(valor, bool):
        raise ValueError(f"{nombre_campo} debe ser un número, no un booleano.")

    try:
        # Se convierte primero a str para no arrastrar la imprecisión de un float.
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{nombre_campo} debe ser un número válido.")

    # Decimal acepta "NaN" e "Infinity"; en dinero no tienen sentido.
    if not numero.is_finite():
        raise ValueError(f"{nombre_campo} debe ser un número finito.")

    # Regla central del enunciado: ningún monto puede ser negativo.
    if numero < 0:
        raise ValueError(f"{nombre_campo} no puede ser negativo.")

    return numero


def _redondear(valor):
    """Redondea un Decimal a dos decimales con redondeo comercial."""
    return valor.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Funciones públicas: las que usan las vistas y las que vamos a probar.
# ---------------------------------------------------------------------------

def calcular_descuento(subtotal, cupon=None):
    """Calcula el VALOR del descuento según el cupón.

    Parámetros:
        subtotal: valor de la compra antes de descuentos.
        cupon: código del cupón (ej. "DESC10"). Puede ser None o vacío.

    Retorna:
        Decimal con el valor a descontar (0.00 si no hay cupón).

    Lanza:
        ValueError: si el subtotal es inválido/negativo o el cupón no existe.
    """
    # Se valida el subtotal ANTES de mirar el cupón, para no dejar pasar negativos.
    subtotal = _a_decimal(subtotal, "El subtotal")

    # Sin cupón (None o cadena vacía) no hay descuento.
    if not cupon:
        return Decimal("0.00")

    # Se normaliza el código: sin espacios y en mayúsculas ("  desc10 " -> "DESC10").
    codigo = str(cupon).strip().upper()

    # Un cupón inexistente es un error: no se ignora en silencio.
    if codigo not in CUPONES:
        raise ValueError(f"El cupón '{cupon}' no es válido.")

    # Valor del descuento = subtotal x porcentaje del cupón.
    return _redondear(subtotal * CUPONES[codigo])


def calcular_iva(base):
    """Calcula el IVA (19 %) sobre una base gravable.

    Lanza:
        ValueError: si la base es inválida o negativa.
    """
    base = _a_decimal(base, "La base del IVA")
    return _redondear(base * TASA_IVA)


def aplica_envio_gratis(total):
    """Indica si la compra tiene envío gratis (total MAYOR a $100.000).

    Ojo: exactamente $100.000 NO tiene envío gratis. Este valor límite
    es un caso clásico donde aparecen errores (> vs >=).

    Lanza:
        ValueError: si el total es inválido o negativo.
    """
    total = _a_decimal(total, "El total")
    return total > UMBRAL_ENVIO_GRATIS


def calcular_total(subtotal, cupon=None):
    """Integra todas las reglas y devuelve el desglose completo de la factura.

    Regla de negocio (documentada a propósito):
        1. Primero se aplica el descuento del cupón.
        2. El IVA se calcula sobre el valor YA descontado (base gravable).
        3. El envío gratis se evalúa sobre el total final a pagar (con IVA).

    Retorna:
        dict con subtotal, descuento, base_gravable, iva, total y envio_gratis.
    """
    # Se valida y redondea el subtotal de entrada.
    subtotal = _redondear(_a_decimal(subtotal, "El subtotal"))

    # Paso 1: descuento por cupón.
    descuento = calcular_descuento(subtotal, cupon)

    # Paso 2: base gravable e IVA sobre esa base.
    base_gravable = subtotal - descuento
    iva = calcular_iva(base_gravable)

    # Paso 3: total final y regla de envío.
    total = base_gravable + iva

    return {
        "subtotal": subtotal,
        "descuento": descuento,
        "base_gravable": base_gravable,
        "iva": iva,
        "total": total,
        "envio_gratis": aplica_envio_gratis(total),
    }