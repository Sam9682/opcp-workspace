"""PayPal payment service for processing membership fees
Feature: OPCP-website
Validates Requirements 4.1, 4.2
"""
import paypalrestsdk
from decimal import Decimal
from typing import Dict, Any, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class PayPalService:
    """Service for handling PayPal payment processing
    
    This service provides methods for:
    - Creating payment orders for membership fees
    - Processing webhook events from PayPal
    - Handling payment confirmations and failures
    - Capturing authorized payments
    """
    
    def __init__(self):
        """Initialize PayPal service with API credentials"""
        paypalrestsdk.configure({
            "mode": settings.PAYPAL_MODE,  # sandbox or live
            "client_id": settings.PAYPAL_CLIENT_ID,
            "client_secret": settings.PAYPAL_CLIENT_SECRET
        })
        logger.info(f"PayPal service initialized in {settings.PAYPAL_MODE} mode")
    
    def create_payment(
        self,
        amount: Decimal,
        currency: str = "EUR",
        description: str = "Membership Fee",
        return_url: str = "",
        cancel_url: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a PayPal payment for membership fee
        
        Args:
            amount: Payment amount in decimal format
            currency: Three-letter ISO currency code (default: "EUR")
            description: Payment description
            return_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is cancelled
            metadata: Optional metadata to attach to the payment
        
        Returns:
            Dictionary containing payment details including:
            - id: Payment ID
            - approval_url: URL for user to approve payment
            - amount: Payment amount
            - currency: Payment currency
            - status: Payment status
        
        Raises:
            Exception: If payment creation fails
        """
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "redirect_urls": {
                    "return_url": return_url,
                    "cancel_url": cancel_url
                },
                "transactions": [{
                    "item_list": {
                        "items": [{
                            "name": description,
                            "sku": "membership",
                            "price": str(amount),
                            "currency": currency.upper(),
                            "quantity": 1
                        }]
                    },
                    "amount": {
                        "total": str(amount),
                        "currency": currency.upper()
                    },
                    "description": description,
                    "custom": str(metadata) if metadata else ""
                }]
            })
            
            if payment.create():
                # Find approval URL
                approval_url = None
                for link in payment.links:
                    if link.rel == "approval_url":
                        approval_url = link.href
                        break
                
                logger.info(
                    f"Created PayPal payment {payment.id} "
                    f"for amount {amount} {currency}"
                )
                
                return {
                    "id": payment.id,
                    "approval_url": approval_url,
                    "amount": amount,
                    "currency": currency.upper(),
                    "status": payment.state,
                }
            else:
                error_msg = f"PayPal payment creation failed: {payment.error}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"Error creating PayPal payment: {str(e)}")
            raise
    
    def execute_payment(
        self,
        payment_id: str,
        payer_id: str
    ) -> Dict[str, Any]:
        """Execute (capture) an approved PayPal payment
        
        Args:
            payment_id: PayPal payment ID
            payer_id: Payer ID from PayPal redirect
        
        Returns:
            Dictionary containing:
            - transaction_id: PayPal transaction ID
            - amount: Payment amount in decimal format
            - currency: Payment currency
            - status: Payment status
            - payer_email: Payer's email address
        
        Raises:
            Exception: If payment execution fails
        """
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            
            if payment.execute({"payer_id": payer_id}):
                # Extract transaction details
                transaction = payment.transactions[0]
                amount_decimal = Decimal(transaction.amount.total)
                
                # Get payer email
                payer_email = payment.payer.payer_info.email if hasattr(
                    payment.payer.payer_info, 'email'
                ) else None
                
                result = {
                    "transaction_id": payment.id,
                    "amount": amount_decimal,
                    "currency": transaction.amount.currency,
                    "status": payment.state,
                    "payer_email": payer_email,
                }
                
                logger.info(
                    f"PayPal payment executed: {payment.id} "
                    f"for amount {amount_decimal} {result['currency']}"
                )
                
                return result
            else:
                error_msg = f"PayPal payment execution failed: {payment.error}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"Error executing PayPal payment: {str(e)}")
            raise
    
    def get_payment_details(self, payment_id: str) -> Dict[str, Any]:
        """Retrieve payment details by ID
        
        Args:
            payment_id: PayPal payment ID
        
        Returns:
            Dictionary containing payment details
        
        Raises:
            Exception: If retrieval fails
        """
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            
            transaction = payment.transactions[0]
            amount_decimal = Decimal(transaction.amount.total)
            
            return {
                "id": payment.id,
                "amount": amount_decimal,
                "currency": transaction.amount.currency,
                "status": payment.state,
                "create_time": payment.create_time,
                "update_time": payment.update_time,
            }
            
        except Exception as e:
            logger.error(f"Error retrieving PayPal payment: {str(e)}")
            raise
    
    def create_refund(
        self,
        sale_id: str,
        amount: Optional[Decimal] = None,
        currency: str = "EUR"
    ) -> Dict[str, Any]:
        """Create a refund for a completed sale
        
        Args:
            sale_id: PayPal sale transaction ID
            amount: Optional partial refund amount (full refund if not specified)
            currency: Currency code for partial refunds
        
        Returns:
            Dictionary containing refund details
        
        Raises:
            Exception: If refund creation fails
        """
        try:
            sale = paypalrestsdk.Sale.find(sale_id)
            
            refund_params = {}
            if amount is not None:
                refund_params["amount"] = {
                    "total": str(amount),
                    "currency": currency.upper()
                }
            
            refund = sale.refund(refund_params)
            
            if refund.success():
                logger.info(
                    f"Created PayPal refund {refund.id} for sale {sale_id}"
                )
                
                refund_amount = Decimal(refund.amount.total) if hasattr(
                    refund, 'amount'
                ) else amount
                
                return {
                    "id": refund.id,
                    "amount": refund_amount,
                    "currency": currency.upper(),
                    "status": refund.state,
                }
            else:
                error_msg = f"PayPal refund failed: {refund.error}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"Error creating PayPal refund: {str(e)}")
            raise
    
    def verify_webhook_signature(
        self,
        transmission_id: str,
        transmission_time: str,
        cert_url: str,
        auth_algo: str,
        transmission_sig: str,
        webhook_id: str,
        webhook_event: Dict[str, Any]
    ) -> bool:
        """Verify PayPal webhook signature
        
        Args:
            transmission_id: PayPal transmission ID from headers
            transmission_time: Transmission timestamp from headers
            cert_url: Certificate URL from headers
            auth_algo: Authentication algorithm from headers
            transmission_sig: Transmission signature from headers
            webhook_id: Your webhook ID from PayPal dashboard
            webhook_event: The webhook event body
        
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            result = paypalrestsdk.WebhookEvent.verify(
                transmission_id=transmission_id,
                transmission_time=transmission_time,
                cert_url=cert_url,
                auth_algo=auth_algo,
                transmission_sig=transmission_sig,
                webhook_id=webhook_id,
                webhook_event=webhook_event
            )
            
            logger.info(f"Webhook signature verification result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False


# Global service instance
paypal_service = PayPalService()
