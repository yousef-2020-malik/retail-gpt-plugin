# app/main.py

import os
import uuid
from typing import List, Dict, Any, Optional

import stripe
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .data import PRODUCTS

# -------------------------
# FastAPI app (IMPORTANT: servers added for GPT Actions)
# -------------------------
app = FastAPI(
    title="Retail Checkout API",
    version="1.0.0",
    servers=[{"url": "https://retail-gpt-plugin.onrender.com"}],
)

# -------------------------
# Stripe init
# ----------------------
