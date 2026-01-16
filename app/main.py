# app/main.py

import os
import uuid
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import stripe

from app.data import PRODUCTS


# -------------------------
# App
# -------------------------
app = FastAPI(
    title="Retail Checkout API",
    version="1.0.0",
    description="Retail Checkout API for GPT Actions",
    servers=[{"url": "https://retail-gpt-plugin.onrender.com"}],
)

# -------------------------
# CORS (FOR WEB UX)
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Stripe (optional)
# -------------------------
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_dummy")

# -------------------------
# In-memory storage (MVP)
# -------------------------
CARTS: Dict[str, Dict[str, Any]] = {}
ORDERS: Dict[str, Dict[str, Any]] = {}

# -------------------------
# Models
# -------------------------
class AddItemRequest(BaseModel):
    cart_id: str
    sku: str
    qty: int = Field(..., ge=1)


class RemoveItemRequest(BaseModel):
    cart_id: str
    sku: str


class UpdateQtyRequest(BaseModel):
    cart_id: str
    sku: str
    qty: int = Field(..., ge=0)


class PlaceOrderRequest(BaseModel):
    cart_id: str


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
        it["line_total"] = round(float(it["unit_price"]) * int(it["qty"]), 2)
        total += it["line_total"]
    cart["total"] = round(total, 2)


def get_cart_or_404(cart_id: str) -> Dict[str, Any]:
    cart = CARTS.get(cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


# -------------------------
# Root
# -------------------------
@app.get("/")
def root():
    return {"status": "ok"}


# -------------------------
# Products
# -------------------------
@app.get("/products")
def list_products():
    return {"items": PRODUCTS}


@app.get("/products/search")
def search_products(q: str):
    q = q.lower().strip()
    return {
        "items": [
            p for p in PRODUCTS
            if q in p["name"].lower() or q in (p.get("brand", "").lower())
        ]
    }


# -------------------------
# Cart
# -------------------------
@app.post("/cart/create")
def create_cart():
    cart_id = f"c_{uuid.uuid4().hex[:8]}"
    CARTS[cart_id] = {
        "cart_id": cart_id,
        "currency": "AED",
        "items": [],
        "total": 0.0,
    }
    return CARTS[cart_id]


@app.get("/cart/{cart_id}")
def get_cart(cart_id: str):
    return get_cart_or_404(cart_id)


@app.post("/cart/items/add")
def add_item(req: AddItemRequest):
    cart = get_cart_or_404(req.cart_id)
    product = find_product(req.sku)

    for it in cart["items"]:
        if it["sku"] == req.sku:
            it["qty"] += req.qty
            recalc_cart(cart)
            return cart

    cart["items"].append({
        "sku": product["sku"],
        "name": product["name"],
        "brand": product.get("brand"),
        "qty": req.qty,
        "unit_price": float(product["price"]),
        "currency": product.get("currency", "AED"),
        "line_total": round(float(product["price"]) * req.qty, 2),
    })

    recalc_cart(cart)
    return cart


@app.post("/cart/items/update")
def update_item_qty(req: UpdateQtyRequest):
    cart = get_cart_or_404(req.cart_id)

    updated_items: List[Dict[str, Any]] = []
    found = False

    for it in cart["items"]:
        if it["sku"] == req.sku:
            found = True
            if req.qty == 0:
                continue
            it["qty"] = req.qty
        updated_items.append(it)

    if not found:
        raise HTTPException(status_code=404, detail="Item not found in cart")

    cart["items"] = updated_items
    recalc_cart(cart)
    return cart


@app.post("/cart/items/remove")
def remove_item(req: RemoveItemRequest):
    cart = get_cart_or_404(req.cart_id)
    before = len(cart["items"])
    cart["items"] = [it for it in cart["items"] if it["sku"] != req.sku]

    if len(cart["items"]) == before:
        raise HTTPException(status_code=404, detail="Item not found in cart")

    recalc_cart(cart)
    return cart


@app.post("/cart/clear/{cart_id}")
def clear_cart(cart_id: str):
    cart = get_cart_or_404(cart_id)
    cart["items"] = []
    cart["total"] = 0.0
    return cart


# -------------------------
# Checkout
# -------------------------
@app.post("/checkout/place-order")
def place_order(req: PlaceOrderRequest):
    cart = get_cart_or_404(req.cart_id)
    if not cart["items"]:
        raise HTTPException(status_code=400, detail="Cart is empty")

    order_id = f"o_{uuid.uuid4().hex[:10]}"
    order = {
        "order_id": order_id,
        "status": "PLACED",
        "items": cart["items"],
        "total": cart["total"],
        "currency": cart["currency"],
    }

    ORDERS[order_id] = order
    CARTS.pop(req.cart_id, None)

    return order


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    order = ORDERS.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
