# app/main.py

import os
import uuid
from typing import List, Dict, Any, Optional

import stripe
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .data import PRODUCTS

app = FastAPI(title="Retail Checkout API", version="1.0.0")

# -------------------------
# Stripe init
# -------------------------
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
if not stripe.api_key:
    raise RuntimeError("STRIPE_SECRET_KEY is missing. Add it to your .env file.")

# -------------------------
# In-memory storage (MVP)
# -------------------------
CARTS: Dict[str, Dict[str, Any]] = {}
ORDERS: Dict[str, Dict[str, Any]] = {}

# -------------------------
# Models
# -------------------------

class Product(BaseModel):
    sku: str
    name: str
    brand: Optional[str] = None
    price: float
    currency: str


class Cart(BaseModel):
    cart_id: str
    currency: str = "AED"
    items: List[Dict[str, Any]] = []
    total: float = 0.0


class AddItemRequest(BaseModel):
    cart_id: str
    sku: str
    qty: int


class PaymentIntentRequest(BaseModel):
    cart_id: str


class ConfirmRequest(BaseModel):
    cart_id: str
    payment_intent_id: str


# -------------------------
# Helpers
# -------------------------

def find_product(sku: str) -> Dict[str, Any]:
    for p in PRODUCTS:
        if p["sku"] == sku:
            return p
    raise HTTPException(status_code=404, detail="Product not found")


def recalc_cart(cart: Dict[str, Any]) -> None:
    total = 0.0
    for it in cart["items"]:
        total += float(it["unit_price"]) * int(it["qty"])
    cart["total"] = round(total, 2)


# -------------------------
# Catalog
# -------------------------

@app.get("/products/search")
def search_products(q: str):
    q_lower = q.lower().strip()
    items = [
        p for p in PRODUCTS
        if q_lower in p["name"].lower() or q_lower in (p.get("brand", "").lower())
    ]
    return {"items": items}


# -------------------------
# Cart
# -------------------------

@app.post("/cart/create")
def create_cart():
    cart_id = f"c_{uuid.uuid4().hex[:10]}"
    CARTS[cart_id] = {"cart_id": cart_id, "currency": "AED", "items": [], "total": 0.0}
    return CARTS[cart_id]


@app.post("/cart/items/add")
def add_item(req: AddItemRequest):
    if req.qty < 1:
        raise HTTPException(status_code=400, detail="qty must be >= 1")

    cart = CARTS.get(req.cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    product = find_product(req.sku)

    # If item exists, increment qty
    for it in cart["items"]:
        if it["sku"] == req.sku:
            it["qty"] += req.qty
            recalc_cart(cart)
            return cart

    cart["items"].append({
        "sku": product["sku"],
        "name": product["name"],
        "qty": req.qty,
        "unit_price": product["price"],
        "currency": product["currency"],
    })
    recalc_cart(cart)
    return cart


@app.get("/cart/{cart_id}")
def get_cart(cart_id: str):
    cart = CARTS.get(cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


# -------------------------
# Checkout (NO redirect)
# -------------------------

@app.post("/checkout/create-payment-intent")
def create_payment_intent(req: PaymentIntentRequest):
    cart = CARTS.get(req.cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    if len(cart["items"]) == 0:
        raise HTTPException(status_code=400, detail="Cart is empty")

    amount = int(cart["total"] * 100)  # cents

    # Force USD for now to avoid Stripe AED configuration issues during testing
    currency = "usd"

    try:
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            automatic_payment_methods={"enabled": True},
            metadata={"cart_id": req.cart_id},
        )
    except Exception as e:
        # Show Stripe error clearly in Swagger
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "payment_intent_id": intent.id,
        "client_secret": intent.client_secret,
        "amount": cart["total"],
        "currency": currency.upper(),
    }


@app.post("/checkout/confirm")
def confirm_order(req: ConfirmRequest):
    cart = CARTS.get(req.cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    intent = stripe.PaymentIntent.retrieve(req.payment_intent_id)

    if intent.status != "succeeded":
        raise HTTPException(
            status_code=400,
            detail=f"Payment not completed. Status: {intent.status}"
        )

    order_id = f"o_{uuid.uuid4().hex[:10]}"
    ORDERS[order_id] = {
        "order_id": order_id,
        "status": "CONFIRMED",
        "items": cart["items"],
        "total": cart["total"],
        "payment_intent_id": req.payment_intent_id,
    }

    # Clear cart after success
    CARTS.pop(req.cart_id, None)

    return {"order_id": order_id, "status": "CONFIRMED"}


# -------------------------
# Orders
# -------------------------

@app.get("/orders/{order_id}")
def get_order(order_id: str):
    order = ORDERS.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
