# Stripe Integration Guide

## Overview

The OPCP website uses Stripe for processing membership fee payments via credit card. This document explains how the Stripe integration is configured and how to use it.

## Configuration

### Environment Variables

The following environment variables must be set in your `.env` file:

```env
# Stripe API Keys
STRIPE_API_KEY=sk_test_your_stripe_key          # Use sk_test_ for testing, sk_live_ for production
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret  # Webhook signing secret from Stripe dashboard

# Membership Fee
ANNUAL_MEMBERSHIP_FEE=50.00                      # Annual membership fee in EUR
```

### Getting Stripe API Keys

1. **Test Mode Keys** (for development):
   - Go to [Stripe Dashboard](https://dashboard.stripe.com/test/apikeys)
   - Copy the "Secret key" (starts with `sk_test_`)
   - Use these keys for testing without processing real payments

2. **Production Keys** (for live payments):
   - Go to [Stripe Dashboard](https://dashboard.stripe.com/apikeys)
   - Copy the "Secret key" (starts with `sk_live_`)
   - **Keep these keys secure and never commit them to version control**

3. **Webhook Secret**:
   - Go to [Stripe Webhooks](https://dashboard.stripe.com/webhooks)
   - Create a new webhook endpoint pointing to your server: `https://yourdomain.com/api/payments/stripe/webhook`
   - Select events to listen for: `payment_intent.succeeded`, `payment_intent.payment_failed`
   - Copy the "Signing secret" (starts with `whsec_`)

## StripeService API

### Initialization

The `StripeService` is automatically initialized with your API keys:

```python
from app.services import stripe_service
```

### Creating a Payment Intent

To initiate a payment:

```python
from decimal import Decimal
from app.services import stripe_service

# Create payment intent for membership fee
result = stripe_service.create_payment_intent(
    amount=Decimal("50.00"),
    currency="eur",
    metadata={
        "user_id": "123",
        "membership_year": "2026"
    }
)

# Send client_secret to frontend for payment confirmation
client_secret = result["client_secret"]
payment_intent_id = result["id"]
```

### Handling Webhook Events

When Stripe sends webhook events to your server:

```python
from fastapi import Request, HTTPException
from app.services import stripe_service

@app.post("/api/payments/stripe/webhook")
async def stripe_webhook(request: Request):
    # Get raw body and signature
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    
    try:
        # Verify webhook signature
        event = stripe_service.verify_webhook_signature(payload, signature)
        
        # Handle different event types
        if event.type == "payment_intent.succeeded":
            payment_intent = event.data.object
            result = stripe_service.handle_payment_intent_succeeded(payment_intent)
            
            # Update database with successful payment
            # - Record payment in payments table
            # - Update user's membership_expires_at
            # - Generate and send invoice
            
        elif event.type == "payment_intent.payment_failed":
            payment_intent = event.data.object
            result = stripe_service.handle_payment_intent_failed(payment_intent)
            
            # Handle failed payment
            # - Record failed payment attempt
            # - Notify user of failure
        
        return {"status": "success"}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### Retrieving Payment Intent

To check the status of a payment:

```python
payment_details = stripe_service.retrieve_payment_intent("pi_123456")
print(f"Status: {payment_details['status']}")
print(f"Amount: {payment_details['amount']} {payment_details['currency']}")
```

### Creating Refunds

To refund a payment:

```python
# Full refund
refund = stripe_service.create_refund("pi_123456")

# Partial refund with reason
refund = stripe_service.create_refund(
    payment_intent_id="pi_123456",
    amount=Decimal("25.00"),
    reason="requested_by_customer"
)
```

## Payment Flow

### Frontend Flow

1. User clicks "Pay Membership Fee"
2. Frontend calls `POST /api/payments/initiate` to create payment intent
3. Backend returns `client_secret`
4. Frontend uses Stripe.js to collect payment details and confirm payment
5. Stripe processes payment and sends webhook to backend
6. Backend updates user's membership status and sends invoice

### Backend Flow

1. **Payment Initiation**:
   - Validate user is authenticated
   - Validate payment amount matches membership fee
   - Create Stripe payment intent
   - Return client_secret to frontend

2. **Webhook Processing**:
   - Verify webhook signature
   - Handle `payment_intent.succeeded`:
     - Create Payment record with status=COMPLETED
     - Update user's membership_expires_at (current date + 1 year)
     - Generate PDF invoice
     - Send invoice email to user
   - Handle `payment_intent.payment_failed`:
     - Create Payment record with status=FAILED
     - Log error details
     - Optionally notify user

## Testing

### Test Cards

Use these test card numbers in test mode:

- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- **Insufficient funds**: `4000 0000 0000 9995`
- **Expired card**: `4000 0000 0000 0069`

Use any future expiration date, any 3-digit CVC, and any postal code.

### Testing Webhooks Locally

Use Stripe CLI to forward webhooks to your local server:

```bash
# Install Stripe CLI
# https://stripe.com/docs/stripe-cli

# Login to Stripe
stripe login

# Forward webhooks to local server
stripe listen --forward-to ai-OPCP:8000/api/payments/stripe/webhook

# Trigger test events
stripe trigger payment_intent.succeeded
stripe trigger payment_intent.payment_failed
```

## Security Best Practices

1. **Never expose API keys**: Keep `STRIPE_API_KEY` secret and never commit to version control
2. **Always verify webhook signatures**: Use `verify_webhook_signature()` to prevent fake webhooks
3. **Use HTTPS in production**: Stripe requires HTTPS for webhook endpoints
4. **Implement idempotency**: Handle duplicate webhook events gracefully
5. **Log all transactions**: Keep audit trail of all payment attempts
6. **Monitor for fraud**: Review Stripe Radar alerts regularly

## Error Handling

The StripeService raises `stripe.error.StripeError` exceptions for API errors:

```python
import stripe

try:
    result = stripe_service.create_payment_intent(amount=Decimal("50.00"))
except stripe.error.CardError as e:
    # Card was declined
    print(f"Card error: {e.user_message}")
except stripe.error.InvalidRequestError as e:
    # Invalid parameters
    print(f"Invalid request: {str(e)}")
except stripe.error.AuthenticationError as e:
    # Invalid API key
    print(f"Authentication error: {str(e)}")
except stripe.error.APIConnectionError as e:
    # Network error
    print(f"Network error: {str(e)}")
except stripe.error.StripeError as e:
    # Generic Stripe error
    print(f"Stripe error: {str(e)}")
```

## Resources

- [Stripe API Documentation](https://stripe.com/docs/api)
- [Stripe Payment Intents Guide](https://stripe.com/docs/payments/payment-intents)
- [Stripe Webhooks Guide](https://stripe.com/docs/webhooks)
- [Stripe Testing Guide](https://stripe.com/docs/testing)
- [Stripe Security Best Practices](https://stripe.com/docs/security/guide)
