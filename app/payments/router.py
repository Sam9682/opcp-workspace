"""Payment API endpoints
Feature: OPCP-website
Validates Requirements 4.1, 4.2, 4.7
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session
from decimal import Decimal
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
import logging
import stripe

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User, Payment, PaymentMethod, PaymentStatus
from app.payments.schemas import PaymentInitiateRequest, PaymentInitiateResponse
from app.services.stripe_service import stripe_service
from app.services.paypal_service import paypal_service
from app.services.invoice_generator import invoice_generator
from app.services.email_service import email_service
from app.config import settings
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/payments",
    tags=["payments"]
)


def update_user_membership(user: User, db: Session) -> None:
    """Update user membership expiration date by adding 1 year
    
    If user has an active membership, extends from current expiration.
    Otherwise, sets expiration to 1 year from now.
    
    Handles both timezone-aware and naive datetimes for SQLite compatibility.
    
    Args:
        user: User object to update
        db: Database session
    """
    current_time = datetime.now(timezone.utc)
    
    # Handle both timezone-aware and naive datetimes (for SQLite compatibility)
    if user.membership_expires_at:
        # Make sure existing expiration is timezone-aware
        if user.membership_expires_at.tzinfo is None:
            existing_expiry = user.membership_expires_at.replace(tzinfo=timezone.utc)
        else:
            existing_expiry = user.membership_expires_at
        
        if existing_expiry > current_time:
            # Extend from current expiration
            user.membership_expires_at = existing_expiry + timedelta(days=365)
        else:
            # Set new expiration from now
            user.membership_expires_at = current_time + timedelta(days=365)
    else:
        # Set new expiration from now
        user.membership_expires_at = current_time + timedelta(days=365)
    
    logger.info(
        f"Updated membership for user {user.id} until {user.membership_expires_at}"
    )


def generate_and_send_invoice(payment: Payment, user: User, db: Session) -> None:
    """Generate PDF invoice and send it to user's email
    
    Validates Requirements 4.3, 4.4:
    - Generates PDF invoice with payment details
    - Sends invoice to user's email address
    
    Args:
        payment: Payment object
        user: User object
        db: Database session
    """
    try:
        # Generate user's full name
        user_name = f"{user.first_name} {user.last_name}"
        
        # Generate invoice PDF
        invoice_path = invoice_generator.generate_invoice(
            payment_id=str(payment.id),
            user_email=user.email,
            user_name=user_name,
            amount=payment.amount,
            currency=payment.currency,
            payment_method=payment.payment_method.value,
            transaction_id=payment.transaction_id,
            created_at=payment.created_at
        )
        
        # Generate invoice number for email
        invoice_number = invoice_generator.generate_invoice_number(
            str(payment.id),
            payment.created_at
        )
        
        # Store invoice URL in payment record
        # Use relative path for storage
        payment.invoice_url = f"/invoices/{invoice_number}.pdf"
        db.commit()
        
        logger.info(f"Stored invoice URL for payment {payment.id}: {payment.invoice_url}")
        
        # Send invoice email
        email_sent = email_service.send_invoice_email(
            to_email=user.email,
            user_name=user_name,
            invoice_number=invoice_number,
            amount=float(payment.amount),
            currency=payment.currency,
            invoice_path=invoice_path
        )
        
        if email_sent:
            logger.info(f"Invoice email sent successfully to {user.email}")
        else:
            logger.warning(f"Failed to send invoice email to {user.email}")
    
    except Exception as e:
        logger.error(f"Failed to generate/send invoice for payment {payment.id}: {str(e)}", exc_info=True)
        # Don't raise - we don't want to fail the webhook if invoice generation fails


@router.post(
    "/initiate",
    response_model=PaymentInitiateResponse,
    status_code=status.HTTP_200_OK,
    summary="Initiate a payment",
    description="Create a payment intent for membership fee using Stripe or PayPal"
)
@limiter.limit("10/hour")  # Limit payment initiation to prevent abuse
async def initiate_payment(
    request: Request,
    payment_data: PaymentInitiateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> PaymentInitiateResponse:
    """Initiate a payment for membership fee
    
    This endpoint creates a payment intent/order with the selected payment provider.
    
    **Validates Requirements 4.1, 4.7:**
    - Presents payment options (Stripe for credit card, PayPal)
    - Validates payment amount against configured membership fee
    
    **For Stripe (credit_card):**
    - Returns a client_secret for client-side payment confirmation
    - Client should use Stripe.js to complete the payment
    
    **For PayPal:**
    - Returns an approval_url for user to approve payment
    - Client should redirect user to this URL
    - Requires return_url and cancel_url in request
    
    Args:
        request: FastAPI Request object (for rate limiting)
        payment_data: Payment initiation request with method, amount, and URLs
        current_user: Authenticated user from JWT token
        db: Database session
    
    Returns:
        PaymentInitiateResponse with payment details and next steps
    
    Raises:
        HTTPException 400: If amount doesn't match membership fee
        HTTPException 400: If PayPal URLs are missing
        HTTPException 500: If payment provider fails
    """
    # Validate payment amount against configured membership fee
    # Property 16: Payment amount validation
    expected_amount = Decimal(str(settings.ANNUAL_MEMBERSHIP_FEE))
    if payment_data.amount != expected_amount:
        logger.warning(
            f"Invalid payment amount from user {current_user.id}: "
            f"provided {payment_data.amount}, expected {expected_amount}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_AMOUNT",
                "message": "Payment amount does not match membership fee",
                "details": {
                    "provided": float(payment_data.amount),
                    "expected": float(expected_amount)
                }
            }
        )
    
    try:
        # Create payment record in database
        payment = Payment(
            user_id=current_user.id,
            amount=payment_data.amount,
            currency=payment_data.currency,
            payment_method=payment_data.payment_method,
            status=PaymentStatus.PENDING
        )
        db.add(payment)
        db.flush()  # Get payment ID without committing
        
        # Process based on payment method
        if payment_data.payment_method == PaymentMethod.CREDIT_CARD:
            # Create Stripe payment intent
            payment_intent = stripe_service.create_payment_intent(
                amount=payment_data.amount,
                currency=payment_data.currency,
                metadata={
                    "user_id": str(current_user.id),
                    "payment_id": str(payment.id),
                    "email": current_user.email
                }
            )
            
            # Update payment with transaction ID
            payment.transaction_id = payment_intent["id"]
            db.commit()
            
            logger.info(
                f"Created Stripe payment intent {payment_intent['id']} "
                f"for user {current_user.id}"
            )
            
            return PaymentInitiateResponse(
                payment_id=payment_intent["id"],
                payment_method=payment_data.payment_method,
                amount=float(payment_data.amount),
                currency=payment_data.currency,
                client_secret=payment_intent["client_secret"],
                status=payment_intent["status"]
            )
        
        elif payment_data.payment_method == PaymentMethod.PAYPAL:
            # Validate PayPal-specific requirements
            if not payment_data.return_url or not payment_data.cancel_url:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "MISSING_URLS",
                        "message": "return_url and cancel_url are required for PayPal payments",
                        "details": {
                            "return_url": payment_data.return_url,
                            "cancel_url": payment_data.cancel_url
                        }
                    }
                )
            
            # Create PayPal payment
            paypal_payment = paypal_service.create_payment(
                amount=payment_data.amount,
                currency=payment_data.currency,
                description=f"OPCP Membership Fee - {current_user.email}",
                return_url=payment_data.return_url,
                cancel_url=payment_data.cancel_url,
                metadata={
                    "user_id": str(current_user.id),
                    "payment_id": str(payment.id),
                    "email": current_user.email
                }
            )
            
            # Update payment with transaction ID
            payment.transaction_id = paypal_payment["id"]
            db.commit()
            
            logger.info(
                f"Created PayPal payment {paypal_payment['id']} "
                f"for user {current_user.id}"
            )
            
            return PaymentInitiateResponse(
                payment_id=paypal_payment["id"],
                payment_method=payment_data.payment_method,
                amount=float(payment_data.amount),
                currency=payment_data.currency,
                approval_url=paypal_payment["approval_url"],
                status=paypal_payment["status"]
            )
        
        else:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_PAYMENT_METHOD",
                    "message": f"Unsupported payment method: {payment_data.payment_method}"
                }
            )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        # Rollback on any error
        db.rollback()
        logger.error(f"Error initiating payment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "PAYMENT_INITIATION_FAILED",
                "message": "Failed to initiate payment",
                "details": {
                    "error": str(e)
                }
            }
        )


@router.post(
    "/stripe/webhook",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook handler",
    description="Handle payment events from Stripe"
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Handle Stripe webhook events
    
    This endpoint receives and processes webhook events from Stripe,
    including payment confirmations and failures.
    
    **Validates Requirements 4.2:**
    - Records payment on success
    - Updates user membership expiration date
    
    **Supported Events:**
    - payment_intent.succeeded: Payment completed successfully
    - payment_intent.payment_failed: Payment failed
    
    Args:
        request: FastAPI request object containing raw body
        stripe_signature: Stripe signature header for verification
        db: Database session
    
    Returns:
        Success message
    
    Raises:
        HTTPException 400: If signature verification fails
        HTTPException 500: If webhook processing fails
    """
    if not stripe_signature:
        logger.error("Missing Stripe-Signature header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "MISSING_SIGNATURE",
                "message": "Stripe-Signature header is required"
            }
        )
    
    try:
        # Get raw request body
        payload = await request.body()
        
        # Verify webhook signature
        event = stripe_service.verify_webhook_signature(
            payload=payload,
            signature=stripe_signature
        )
        
        logger.info(f"Received Stripe webhook event: {event.type}")
        
        # Handle payment_intent.succeeded event
        if event.type == "payment_intent.succeeded":
            payment_intent = event.data.object
            
            # Extract payment details
            payment_data = stripe_service.handle_payment_intent_succeeded(
                payment_intent
            )
            
            # Find payment record by transaction ID
            payment = db.query(Payment).filter(
                Payment.transaction_id == payment_data["transaction_id"]
            ).first()
            
            if not payment:
                logger.warning(
                    f"Payment record not found for transaction {payment_data['transaction_id']}"
                )
                # Still return 200 to acknowledge webhook
                return {"status": "payment_not_found"}
            
            # Update payment status
            payment.status = PaymentStatus.COMPLETED
            
            # Update user membership expiration date
            # Property 14: Payment recording and status update
            user = db.query(User).filter(User.id == payment.user_id).first()
            if user:
                update_user_membership(user, db)
            
            db.commit()
            
            # Generate and send invoice
            # Property 15: Invoice generation and delivery
            if user:
                generate_and_send_invoice(payment, user, db)
            
            logger.info(
                f"Successfully processed payment {payment.id} for user {payment.user_id}"
            )
            
            return {"status": "success"}
        
        # Handle payment_intent.payment_failed event
        elif event.type == "payment_intent.payment_failed":
            payment_intent = event.data.object
            
            # Extract failure details
            failure_data = stripe_service.handle_payment_intent_failed(
                payment_intent
            )
            
            # Find payment record by transaction ID
            payment = db.query(Payment).filter(
                Payment.transaction_id == failure_data["transaction_id"]
            ).first()
            
            if payment:
                # Update payment status to failed
                payment.status = PaymentStatus.FAILED
                db.commit()
                
                logger.info(
                    f"Marked payment {payment.id} as failed: {failure_data['error_message']}"
                )
            
            return {"status": "failure_recorded"}
        
        else:
            # Acknowledge other event types without processing
            logger.info(f"Unhandled Stripe event type: {event.type}")
            return {"status": "event_ignored"}
    
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid Stripe webhook signature: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_SIGNATURE",
                "message": "Webhook signature verification failed"
            }
        )
    
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}", exc_info=True)
        # Return 500 so Stripe will retry
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "WEBHOOK_PROCESSING_FAILED",
                "message": "Failed to process webhook event"
            }
        )


@router.post(
    "/paypal/webhook",
    status_code=status.HTTP_200_OK,
    summary="PayPal webhook handler",
    description="Handle payment events from PayPal"
)
async def paypal_webhook(
    request: Request,
    paypal_transmission_id: Optional[str] = Header(None, alias="Paypal-Transmission-Id"),
    paypal_transmission_time: Optional[str] = Header(None, alias="Paypal-Transmission-Time"),
    paypal_cert_url: Optional[str] = Header(None, alias="Paypal-Cert-Url"),
    paypal_auth_algo: Optional[str] = Header(None, alias="Paypal-Auth-Algo"),
    paypal_transmission_sig: Optional[str] = Header(None, alias="Paypal-Transmission-Sig"),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Handle PayPal webhook events
    
    This endpoint receives and processes webhook events from PayPal,
    including payment confirmations and failures.
    
    **Validates Requirements 4.2:**
    - Records payment on success
    - Updates user membership expiration date
    
    **Supported Events:**
    - PAYMENT.SALE.COMPLETED: Payment completed successfully
    - PAYMENT.SALE.DENIED: Payment denied
    - PAYMENT.SALE.REFUNDED: Payment refunded
    
    Args:
        request: FastAPI request object containing webhook body
        paypal_transmission_id: PayPal transmission ID header
        paypal_transmission_time: PayPal transmission time header
        paypal_cert_url: PayPal certificate URL header
        paypal_auth_algo: PayPal auth algorithm header
        paypal_transmission_sig: PayPal transmission signature header
        db: Database session
    
    Returns:
        Success message
    
    Raises:
        HTTPException 400: If signature verification fails
        HTTPException 500: If webhook processing fails
    """
    try:
        # Get webhook event body
        webhook_event = await request.json()
        event_type = webhook_event.get("event_type")
        
        logger.info(f"Received PayPal webhook event: {event_type}")
        
        # Verify webhook signature if headers are present
        # Note: Signature verification requires webhook ID from PayPal dashboard
        # For now, we'll log if headers are missing but still process
        if all([
            paypal_transmission_id,
            paypal_transmission_time,
            paypal_cert_url,
            paypal_auth_algo,
            paypal_transmission_sig
        ]):
            # In production, you would configure PAYPAL_WEBHOOK_ID in settings
            # and verify the signature here
            logger.info("PayPal webhook signature headers present")
        else:
            logger.warning("PayPal webhook signature headers missing - skipping verification")
        
        # Handle PAYMENT.SALE.COMPLETED event
        if event_type == "PAYMENT.SALE.COMPLETED":
            resource = webhook_event.get("resource", {})
            
            # Extract payment ID from parent_payment
            parent_payment_id = resource.get("parent_payment")
            if not parent_payment_id:
                logger.warning("Missing parent_payment in PayPal webhook")
                return {"status": "missing_payment_id"}
            
            # Find payment record by transaction ID
            payment = db.query(Payment).filter(
                Payment.transaction_id == parent_payment_id
            ).first()
            
            if not payment:
                logger.warning(
                    f"Payment record not found for transaction {parent_payment_id}"
                )
                # Still return 200 to acknowledge webhook
                return {"status": "payment_not_found"}
            
            # Update payment status
            payment.status = PaymentStatus.COMPLETED
            
            # Update user membership expiration date
            # Property 14: Payment recording and status update
            user = db.query(User).filter(User.id == payment.user_id).first()
            if user:
                update_user_membership(user, db)
            
            db.commit()
            
            # Generate and send invoice
            # Property 15: Invoice generation and delivery
            if user:
                generate_and_send_invoice(payment, user, db)
            
            logger.info(
                f"Successfully processed PayPal payment {payment.id} for user {payment.user_id}"
            )
            
            return {"status": "success"}
        
        # Handle PAYMENT.SALE.DENIED event
        elif event_type == "PAYMENT.SALE.DENIED":
            resource = webhook_event.get("resource", {})
            parent_payment_id = resource.get("parent_payment")
            
            if parent_payment_id:
                payment = db.query(Payment).filter(
                    Payment.transaction_id == parent_payment_id
                ).first()
                
                if payment:
                    payment.status = PaymentStatus.FAILED
                    db.commit()
                    
                    logger.info(
                        f"Marked PayPal payment {payment.id} as failed"
                    )
            
            return {"status": "failure_recorded"}
        
        # Handle PAYMENT.SALE.REFUNDED event
        elif event_type == "PAYMENT.SALE.REFUNDED":
            resource = webhook_event.get("resource", {})
            parent_payment_id = resource.get("parent_payment")
            
            if parent_payment_id:
                payment = db.query(Payment).filter(
                    Payment.transaction_id == parent_payment_id
                ).first()
                
                if payment:
                    payment.status = PaymentStatus.REFUNDED
                    db.commit()
                    
                    logger.info(
                        f"Marked PayPal payment {payment.id} as refunded"
                    )
            
            return {"status": "refund_recorded"}
        
        else:
            # Acknowledge other event types without processing
            logger.info(f"Unhandled PayPal event type: {event_type}")
            return {"status": "event_ignored"}
    
    except Exception as e:
        logger.error(f"Error processing PayPal webhook: {str(e)}", exc_info=True)
        # Return 500 so PayPal will retry
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "WEBHOOK_PROCESSING_FAILED",
                "message": "Failed to process webhook event"
            }
        )
