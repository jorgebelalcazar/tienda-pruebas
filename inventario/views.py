"""
Vistas de la API del carrito.
Devuelven JSON con códigos HTTP claros:
    200 -> operación exitosa
    400 -> petición inválida (stock insuficiente, cupón inválido, JSON mal formado)
    404 -> el producto no existe
"""

import json
from decimal import Decimal

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

# Lógica de negocio pura (la misma que se prueba sin Django).
from .calculos import calcular_total
from .models import Producto


# ---------------------------------------------------------------------------
# Funciones auxiliares (privadas: el prefijo _ indica uso interno del módulo).
# ---------------------------------------------------------------------------

def _respuesta_json(datos, status=200):
    """Crea una respuesta JSON que conserva tildes y eñes.

    Por defecto JsonResponse usa ensure_ascii=True y convierte "ó" en "\\u00f3".
    Con ensure_ascii=False el texto viaja tal cual (en UTF-8), más legible
    para clientes como PowerShell, curl o los registros del servidor.

    Parámetros:
        datos: diccionario que se enviará como JSON.
        status: código de estado HTTP (por defecto 200).
    """
    return JsonResponse(
        datos,
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )


def _producto_a_dict(producto):
    """Convierte un Producto en un diccionario serializable a JSON.

    El precio se envía como texto para no perder exactitud del Decimal.
    """
    return {
        "id": producto.id,
        "nombre": producto.nombre,
        "precio": str(producto.precio),
        "stock": producto.stock,
    }


def _respuesta_no_encontrado(producto_id):
    """Respuesta JSON estándar para un producto inexistente (404).

    No se usa get_object_or_404 porque devuelve una página HTML,
    y esta API siempre debe responder JSON.
    """
    return _respuesta_json(
        {"error": f"El producto con id {producto_id} no existe."},
        status=404,
    )


# ---------------------------------------------------------------------------
# Vistas públicas (conectadas en inventario/urls.py).
# ---------------------------------------------------------------------------

@require_GET  # Solo acepta GET; cualquier otro método recibe 405 automáticamente.
def detalle_producto(request, producto_id):
    """GET /api/productos/<id>/  ->  detalle del producto."""
    try:
        # Busca el producto por su llave primaria.
        producto = Producto.objects.get(pk=producto_id)
    except Producto.DoesNotExist:
        # Si no existe, se responde 404 en formato JSON.
        return _respuesta_no_encontrado(producto_id)

    # Producto encontrado: se responde 200 con sus datos.
    return _respuesta_json(_producto_a_dict(producto), status=200)


# csrf_exempt: permite probar la API con curl/PowerShell en la demo.
# En una API real se protegería con autenticación por token (ej. Django REST Framework).
@csrf_exempt
@require_POST  # Comprar modifica datos: solo se acepta POST.
def comprar_producto(request, producto_id):
    """POST /api/productos/<id>/comprar/

    Cuerpo JSON esperado:
        {"cantidad": 2, "cupon": "DESC10"}   (cupon es opcional; cantidad por defecto 1)
    """
    # 1. Leer y validar el cuerpo de la petición.
    try:
        # Si el cuerpo viene vacío se toma como un objeto JSON vacío.
        datos = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _respuesta_json(
            {"error": "El cuerpo de la petición debe ser JSON válido."},
            status=400,
        )

    # El JSON debe ser un objeto ({...}), no una lista ni un número.
    if not isinstance(datos, dict):
        return _respuesta_json(
            {"error": "El cuerpo debe ser un objeto JSON."},
            status=400,
        )

    # Valores enviados por el cliente (con valores por defecto).
    cantidad = datos.get("cantidad", 1)
    cupon = datos.get("cupon")

    # 2. Ejecutar la compra dentro de una transacción atómica:
    #    o se guarda TODO, o no se guarda NADA.
    try:
        with transaction.atomic():
            try:
                # select_for_update bloquea la fila mientras dura la compra,
                # evitando que dos clientes compren la última unidad a la vez.
                # (En SQLite se ignora sin error; en PostgreSQL sí bloquea.)
                producto = Producto.objects.select_for_update().get(pk=producto_id)
            except Producto.DoesNotExist:
                return _respuesta_no_encontrado(producto_id)

            # Valida la cantidad y descuenta stock (puede lanzar ValueError).
            producto.descontar_stock(cantidad)

            # Calcula la factura. Si el cupón es inválido lanza ValueError y,
            # gracias a atomic(), el descuento de stock anterior se REVIERTE.
            factura = calcular_total(producto.precio * cantidad, cupon)

    except ValueError as error:
        # Stock insuficiente, cantidad inválida o cupón inválido -> 400.
        return _respuesta_json({"error": str(error)}, status=400)

    # 3. Respuesta exitosa. Los Decimal se convierten a texto para el JSON.
    factura_json = {
        clave: str(valor) if isinstance(valor, Decimal) else valor
        for clave, valor in factura.items()
    }

    return _respuesta_json(
        {
            "mensaje": "Compra realizada con éxito.",
            "producto": _producto_a_dict(producto),
            "cantidad": cantidad,
            "factura": factura_json,
        },
        status=200,
    )