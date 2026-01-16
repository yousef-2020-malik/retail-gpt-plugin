# app/store.py
from typing import Dict, Any
from app.data import PRODUCTS

PRODUCTS_BY_SKU = {p["sku"]: p for p in PRODUCTS}

# In-memory carts store (for demo)
CARTS: Dict[str, Dict[str, Any]] = {}

def get_or_create_cart(cart_id: str, currency: str = "AED") -> Dict[str, Any]:
    if cart_id not in CARTS:
        CARTS[cart_id] = {"cart_id": cart_id, "currency": currency, "items": [], "total": 0.0}
    return CARTS[cart_id]

def recalc_total(cart: Dict[str, Any]) -> None:
    total = 0.0
    for it in cart["items"]:
        total += float(it["unit_price"]) * int(it["qty"])
    cart["total"] = round(total, 2)

def add_item_to_cart(cart_id: str, sku: str, qty: int) -> Dict[str, Any]:
    if qty <= 0:
        raise ValueError("qty must be >= 1")

    product = PRODUCTS_BY_SKU.get(sku)
    if not product:
        raise KeyError(f"SKU not found: {sku}")

    cart = get_or_create_cart(cart_id, currency=product.get("currency", "AED"))

    # If sku already exists in cart -> increase qty
    for it in cart["items"]:
        if it["sku"] == sku:
            it["qty"] += qty
            recalc_total(cart)
            return cart

    # Else add new line item
    cart["items"].append({
        "sku": product["sku"],
        "name": product["name"],
        "brand": product["brand"],
        "qty": qty,
        "unit_price": product["price"],
        "currency": product["currency"],
        "line_total": round(float(product["price"]) * int(qty), 2),
    })
    recalc_total(cart)
    return cart

def get_cart(cart_id: str) -> Dict[str, Any]:
    return get_or_create_cart(cart_id)
