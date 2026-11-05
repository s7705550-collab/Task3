"""Pydantic v2 request and response validation schemas for Task 3 API."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, field_validator


class BasketRecommendationRequest(BaseModel):
    dataset: str = Field(default="full", pattern="^(full|dev)$")
    basket: list[int] = Field(..., min_length=1, max_length=50)
    min_confidence: float = Field(default=0.6, gt=0.0, le=1.0)
    top_k: int = Field(default=15, ge=1, le=50)

    @field_validator("basket")
    @classmethod
    def validate_basket_items(cls, v: list[int]) -> list[int]:
        cleaned = sorted({int(x) for x in v if int(x) > 0})
        if not cleaned:
            raise ValueError("Basket must contain at least one positive integer item ID.")
        return cleaned


class CustomMineRequest(BaseModel):
    source_type: str = Field(default="preset", pattern="^(preset|custom)$")
    dataset: str = Field(default="dev", pattern="^(dev|full)$")
    max_transactions: int = Field(default=10000, ge=100, le=500000)
    custom_transactions_text: str | None = Field(default=None)
    min_support: float = Field(default=0.005, gt=0.0, le=1.0)
    min_confidence: float = Field(default=0.6, gt=0.0, le=1.0)
    top_limit: int = Field(default=100, ge=10, le=500)

    @field_validator("min_support")
    @classmethod
    def check_support_bounds(cls, v: float) -> float:
        if v < 0.001 or v > 1.0:
            raise ValueError("min_support must be between 0.001 and 1.0 for interactive mining.")
        return v

