"""Stripe payment service for processing membership fees
Feature: OPCP-website
Validates Requirements 4.1, 4.2
"""
import stripe
from decimal import Decimal
from typing import Dict, Any, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class StripeService:
    """Service for handling Stripe payment processing
    
    This service provides methods for:
    - Creating payment intents for membership fees
    - Processing webhook events from Stripe
    - Handling payment confirmations and failures
    """
    
    def __init__(self):
        """Initialize Stripe service with API key"""
        stripe.api_key = settings.STRIPE_API_KEY
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    
    def create_payment_intent(
        self,
        amount: Decimal,
        currency: str = "eur",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a Stripe payment intent for membership fee
        
        Args:
            amount: Payment amount in the currency's smallest unit (e.g., cents for EUR)
            currency: Three-letter ISO currency code (default: "eur")
            metadata: Optional metadata to attach to the payment intent
        
        Returns:
            Dictionary containing payment intent details including:
            - id: Payment intent ID
            - client_secret: Secret for client-side confirmation
            - amount: Payment amount
            - currency: Payment currency
            - status: Payment intent status
        
        Raises:
            stripe.error.StripeError: If payment intent creation fails
        """
        try:
            # Convert Decimal to integer cents
            amount_cents = int(amount * 100)
            
            # Create payment intent
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata or {},
                automatic_payment_methods={
                    "enabled": True,
                },
            )
            
            logger.info(
                f"Created payment intent {payment_intent.id} "
                f"for amount {amount} {currency}"
            )
            
            return {
                "id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "amount": amount,
                "currency": currency,
                "status": payment_intent.status,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {str(e)}")
            raise
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str
    ) -> stripe.Event:
        """Verify Stripe webhook signature and construct event
        
        Args:
            payload: Raw request body bytes
            signature: Stripe-Signature header value
        
        Returns:
            Verified Stripe Event object
        
        Raises:
            stripe.error.SignatureVerificationError: If signature is invalid
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            logger.info(f"Verified webhook event: {event.type}")
            return event
            
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {str(e)}")
            raise
    
    def handle_payment_intent_succeeded(
        self,
        payment_intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle successful payment intent
        
        Args:
            payment_intent: Payment intent object from webhook
        
        Returns:
            Dictionary containing:
            - transaction_id: Stripe payment intent ID
            - amount: Payment amount in decimal format
            - currency: Payment currency
            - metadata: Custom metadata attached to payment
        """
        amount_decimal = Decimal(payment_intent["amount"]) / 100
        
        result = {
            "transaction_id": payment_intent["id"],
            "amount": amount_decimal,
            "currency": payment_intent["currency"].upper(),
            "metadata": payment_intent.get("metadata", {}),
        }
        
        logger.info(
            f"Payment intent succeeded: {payment_intent['id']} "
            f"for amount {amount_decimal} {result['currency']}"
        )
        
        return result
    
    def handle_payment_intent_failed(
        self,
        payment_intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle failed payment intent
        
        Args:
            payment_intent: Payment intent object from webhook
        
        Returns:
            Dictionary containing:
            - transaction_id: Stripe payment intent ID
            - error_message: Failure reason
            - metadata: Custom metadata attached to payment
        """
        error_message = payment_intent.get(
            "last_payment_error", {}
        ).get("message", "Unknown error")
        
        result = {
            "transaction_id": payment_intent["id"],
            "error_message": error_message,
            "metadata": payment_intent.get("metadata", {}),
        }
        
        logger.warning(
            f"Payment intent failed: {payment_intent['id']} "
            f"with error: {error_message}"
        )
        
        return result
    
    def retrieve_payment_intent(self, payment_intent_id: str) -> Dict[str, Any]:
        """Retrieve a payment intent by ID
        
        Args:
            payment_intent_id: Stripe payment intent ID
        
        Returns:
            Payment intent details
        
        Raises:
            stripe.error.StripeError: If retrieval fails
        """
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            return {
                "id": payment_intent.id,
                "amount": Decimal(payment_intent.amount) / 100,
                "currency": payment_intent.currency.upper(),
                "status": payment_intent.status,
                "metadata": payment_intent.metadata,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving payment intent: {str(e)}")
            raise
    
    def create_refund(
        self,
        payment_intent_id: str,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a refund for a payment intent
        
        Args:
            payment_intent_id: Stripe payment intent ID to refund
            amount: Optional partial refund amount (full refund if not specified)
            reason: Optional refund reason
        
        Returns:
            Dictionary containing refund details
        
        Raises:
            stripe.error.StripeError: If refund creation fails
        """
        try:
            refund_params = {
                "payment_intent": payment_intent_id,
            }
            
            if amount is not None:
                refund_params["amount"] = int(amount * 100)
            
            if reason:
                refund_params["reason"] = reason
            
            refund = stripe.Refund.create(**refund_params)
            
            logger.info(
                f"Created refund {refund.id} for payment intent {payment_intent_id}"
            )
            
            return {
                "id": refund.id,
                "amount": Decimal(refund.amount) / 100,
                "currency": refund.currency.upper(),
                "status": refund.status,
                "reason": refund.reason,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error creating refund: {str(e)}")
            raise


# Global service instance
stripe_service = StripeService()
