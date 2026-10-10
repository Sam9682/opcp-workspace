"""Pydantic schemas for payment endpoints
Feature: OPCP-website
Validates Requirements 4.1, 4.7
"""
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from typing import Optional
from app.models import PaymentMethod


class PaymentInitiateRequest(BaseModel):
    """Request schema for initiating a payment"""
    payment_method: PaymentMethod = Field(
        ...,
        description="Payment method to use (credit_card or paypal)"
    )
    amount: Decimal = Field(
        ...,
        gt=0,
        description="Payment amount (must be positive)"
    )
    currency: str = Field(
        default="EUR",
        description="Three-letter ISO currency code"
    )
    return_url: Optional[str] = Field(
        default=None,
        description="URL to redirect after successful payment (required for PayPal)"
    )
    cancel_url: Optional[str] = Field(
        default=None,
        description="URL to redirect if payment is cancelled (required for PayPal)"
    )
    
    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate currency code format"""
        if len(v) != 3:
            raise ValueError("Currency must be a 3-letter ISO code")
        return v.upper()
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "payment_method": "credit_card",
                    "amount": 50.00,
                    "currency": "EUR"
                },
                {
                    "payment_method": "paypal",
                    "amount": 50.00,
                    "currency": "EUR",
                    "return_url": "https://example.com/payment/success",
                    "cancel_url": "https://example.com/payment/cancel"
                }
            ]
        }
    }


class PaymentInitiateResponse(BaseModel):
    """Response schema for payment initiation"""
    payment_id: str = Field(
        ...,
        description="Payment ID for tracking"
    )
    payment_method: PaymentMethod = Field(
        ...,
        description="Payment method used"
    )
    amount: float = Field(
        ...,
        description="Payment amount"
    )
    currency: str = Field(
        ...,
        description="Payment currency"
    )
    client_secret: Optional[str] = Field(
        default=None,
        description="Client secret for Stripe payment (credit card only)"
    )
    approval_url: Optional[str] = Field(
        default=None,
        description="Approval URL for PayPal payment (PayPal only)"
    )
    status: str = Field(
        ...,
        description="Payment status"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "payment_id": "pi_1234567890",
                    "payment_method": "credit_card",
                    "amount": 50.00,
                    "currency": "EUR",
                    "client_secret": "pi_1234567890_secret_abcdef",
                    "status": "pending"
                },
                {
                    "payment_id": "PAYID-1234567890",
                    "payment_method": "paypal",
                    "amount": 50.00,
                    "currency": "EUR",
                    "approval_url": "https://www.paypal.com/checkoutnow?token=...",
                    "status": "created"
                }
            ]
        }
    }


class ErrorResponse(BaseModel):
    """Error response schema"""
    error: dict = Field(
        ...,
        description="Error details"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "error": {
                    "code": "INVALID_AMOUNT",
                    "message": "Payment amount does not match membership fee",
                    "details": {
                        "provided": 30.00,
                        "expected": 50.00
                    }
                }
            }
        }
    }
