# app/main.py

import os
import uuid
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import stripe

from app.data import PRODUCTS


# -------------------------
# App (NO custom_openapi)
# -------------------------
app = FastAPI(
    title="Retail Checkout API",
    version="1.0.0",
    description="Retail Checkout API for GPT Actions",
    servers=[
        {"url": "https://retail-gpt-plugin.onrender.com"}
    ],
)

# -------------------------
# Stripe
# -------------------------
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_dummy")

# -------------------------
# Storage
# -------------------------
CARTS: Dict[str, Dict[str, Any]] = {}

# -------------------------
# Models
# -------------------------
class AddItemRequest(BaseModel):
    cart_id: str
    sku: str
    qty: int


# -------------------------
# Helpers
# -------------------------
def find_product(sku: str):
    for p in PRODUCTS:
        if p["sku"] == sku:
            return p
    raise HTTPException(status_code=404, detail="Product not found")


# -------------------------
# Routes (Swagger MUST see these)
# -------------------------
@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/products")
def list_products():
    return {"items": PRODUCTS}


@app.get("/products/search")
def search_products(q: str):
    q = q.lower()
    return {
        "items": [
            p for p in PRODUCTS
            if q in p["name"].lower() or q in (p.get("brand", "").lower())
        ]
    }


@app.post("/cart/create")
def create_cart():
    cart_id = f"c_{uuid.uuid4().hex[:8]}"
    CARTS[cart_id] = {"cart_id": cart_id, "items": [], "total": 0.0}
    return CARTS[cart_id]


@app.post("/cart/items/add")
def add_item(req: AddItemRequest):
    cart = CARTS.get(req.cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    product = find_product(req.sku)

    cart["items"].append({
        "sku": product["sku"],
        "name": product["name"],
        "qty": req.qty,
        "price": product["price"],
    })

    cart["total"] += product["price"] * req.qty
    return cart
