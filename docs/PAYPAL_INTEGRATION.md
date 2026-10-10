# PayPal Integration Guide

## Overview

The OPCP website uses PayPal for processing membership fee payments as an alternative to credit card payments. This document explains how the PayPal integration is configured and how to use it.

## Configuration

### Environment Variables

The following environment variables must be set in your `.env` file:

```env
# PayPal API Credentials
PAYPAL_CLIENT_ID=your_paypal_client_id              # Client ID from PayPal Developer Dashboard
PAYPAL_CLIENT_SECRET=your_paypal_client_secret      # Client Secret from PayPal Developer Dashboard
PAYPAL_MODE=sandbox                                  # Use "sandbox" for testing, "live" for production

# Membership Fee
ANNUAL_MEMBERSHIP_FEE=50.00                         # Annual membership fee in EUR
```

### Getting PayPal API Credentials

1. **Sandbox Credentials** (for development):
   - Go to [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/)
   - Navigate to "Apps & Credentials"
   - Select "Sandbox" tab
   - Create a new app or use existing app
   - Copy the "Client ID" and "Secret"
   - Use these credentials for testing without processing real payments

2. **Production Credentials** (for live payments):
   - Go to [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/)
   - Navigate to "Apps & Credentials"
   - Select "Live" tab
   - Create a new app or use existing app
   - Copy the "Client ID" and "Secret"
   - **Keep these credentials secure and never commit them to version control**

3. **Webhook Configuration**:
   - In your app settings, add webhook URL: `https://yourdomain.com/api/payments/paypal/webhook`
   - Select events to listen for: `PAYMENT.SALE.COMPLETED`, `PAYMENT.SALE.DENIED`
   - Copy the "Webhook ID" for signature verification

## PayPalService API

### Initialization

The `PayPalService` is automatically initialized with your API credentials:

```python
from app.services import paypal_service
```

### Creating a Payment

To initiate a PayPal payment:

```python
from decimal import Decimal
from app.services import paypal_service

# Create payment for membership fee
result = paypal_service.create_payment(
    amount=Decimal("50.00"),
    currency="EUR",
    description="Annual Membership Fee",
    return_url="https://yourdomain.com/payment/success",
    cancel_url="https://yourdomain.com/payment/cancel",
    metadata={
        "user_id": "123",
        "membership_year": "2024"
    }
)

# Redirect user to approval URL
approval_url = result["approval_url"]
payment_id = result["id"]
```

### Executing a Payment

After user approves payment on PayPal, execute it to capture funds:

```python
from app.services import paypal_service

# User returns from PayPal with payment_id and payer_id in URL params
result = paypal_service.execute_payment(
    payment_id="PAYID-123456",
    payer_id="PAYER123"
)

# Payment is now completed
transaction_id = result["transaction_id"]
amount = result["amount"]
payer_email = result["payer_email"]

# Update database with successful payment
# - Record payment in payments table
# - Update user's membership_expires_at
# - Generate and send invoice
```

### Handling Webhook Events

When PayPal sends webhook events to your server:

```python
from fastapi import Request, HTTPException
from app.services import paypal_service

@app.post("/api/payments/paypal/webhook")
async def paypal_webhook(request: Request):
    # Get webhook headers
    transmission_id = request.headers.get("paypal-transmission-id")
    transmission_time = request.headers.get("paypal-transmission-time")
    cert_url = request.headers.get("paypal-cert-url")
    auth_algo = request.headers.get("paypal-auth-algo")
    transmission_sig = request.headers.get("paypal-transmission-sig")
    
    # Get webhook body
    webhook_event = await request.json()
    
    # Verify webhook signature
    is_valid = paypal_service.verify_webhook_signature(
        transmission_id=transmission_id,
        transmission_time=transmission_time,
        cert_url=cert_url,
        auth_algo=auth_algo,
        transmission_sig=transmission_sig,
        webhook_id="YOUR_WEBHOOK_ID",  # From PayPal dashboard
        webhook_event=webhook_event
    )
    
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle different event types
    event_type = webhook_event.get("event_type")
    
    if event_type == "PAYMENT.SALE.COMPLETED":
        # Payment successful
        sale = webhook_event["resource"]
        # Update database with successful payment
        
    elif event_type == "PAYMENT.SALE.DENIED":
        # Payment failed
        sale = webhook_event["resource"]
        # Handle failed payment
    
    return {"status": "success"}
```

### Retrieving Payment Details

To check the status of a payment:

```python
payment_details = paypal_service.get_payment_details("PAYID-123456")
print(f"Status: {payment_details['status']}")
print(f"Amount: {payment_details['amount']} {payment_details['currency']}")
```

### Creating Refunds

To refund a payment:

```python
# Full refund (sale_id is from the completed payment transaction)
refund = paypal_service.create_refund(sale_id="SALE-123456")

# Partial refund
refund = paypal_service.create_refund(
    sale_id="SALE-123456",
    amount=Decimal("25.00"),
    currency="EUR"
)
```

## Payment Flow

### Frontend Flow

1. User clicks "Pay with PayPal"
2. Frontend calls `POST /api/payments/initiate` with `payment_method=paypal`
3. Backend creates PayPal payment and returns `approval_url`
4. Frontend redirects user to PayPal approval URL
5. User logs into PayPal and approves payment
6. PayPal redirects user back to `return_url` with `payment_id` and `payer_id`
7. Frontend calls backend to execute payment
8. Backend captures payment and updates membership status

### Backend Flow

1. **Payment Initiation**:
   - Validate user is authenticated
   - Validate payment amount matches membership fee
   - Create PayPal payment with return/cancel URLs
   - Return approval_url to frontend

2. **Payment Execution**:
   - Receive payment_id and payer_id from frontend
   - Execute payment to capture funds
   - Create Payment record with status=COMPLETED
   - Update user's membership_expires_at (current date + 1 year)
   - Generate PDF invoice
   - Send invoice email to user

3. **Webhook Processing** (optional, for additional verification):
   - Verify webhook signature
   - Handle `PAYMENT.SALE.COMPLETED` event
   - Handle `PAYMENT.SALE.DENIED` event

## Testing

### Sandbox Test Accounts

In sandbox mode, use PayPal test accounts:

1. Go to [PayPal Sandbox Accounts](https://developer.paypal.com/dashboard/accounts)
2. Create or use existing test accounts:
   - **Personal Account**: For testing as a buyer
   - **Business Account**: For receiving payments (your app uses this)
3. Use test account credentials to log in during payment approval

### Testing Payment Flow

1. Create a payment using sandbox credentials
2. Redirect to approval_url
3. Log in with sandbox personal account
4. Approve the payment
5. Verify redirect to return_url with payment_id and payer_id
6. Execute the payment
7. Verify payment is completed

### Testing Webhooks Locally

Use ngrok or similar tool to expose your local server:

```bash
# Install ngrok
# https://ngrok.com/download

# Start your local server on port 8000
uvicorn app.main:app --reload

# In another terminal, expose it
ngrok http 8000

# Use the ngrok URL in PayPal webhook configuration
# Example: https://abc123.ngrok.io/api/payments/paypal/webhook
```

## Security Best Practices

1. **Never expose API credentials**: Keep `PAYPAL_CLIENT_SECRET` secret and never commit to version control
2. **Always verify webhook signatures**: Use `verify_webhook_signature()` to prevent fake webhooks
3. **Use HTTPS in production**: PayPal requires HTTPS for webhook endpoints and return URLs
4. **Validate payment amounts**: Always verify the payment amount matches expected membership fee
5. **Implement idempotency**: Handle duplicate webhook events and payment executions gracefully
6. **Log all transactions**: Keep audit trail of all payment attempts
7. **Use sandbox mode for testing**: Never test with live credentials or real money

## Error Handling

The PayPalService raises exceptions for API errors:

```python
try:
    result = paypal_service.create_payment(
        amount=Decimal("50.00"),
        return_url="https://example.com/success",
        cancel_url="https://example.com/cancel"
    )
except Exception as e:
    # Handle PayPal API errors
    print(f"PayPal error: {str(e)}")
    # Log error and show user-friendly message
```

Common error scenarios:

- **Invalid credentials**: Check `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET`
- **Payment creation failed**: Check amount, currency, and URLs are valid
- **Payment execution failed**: Payment may have expired or already been executed
- **Webhook signature invalid**: Check webhook ID and headers are correct

## Differences from Stripe

| Feature | Stripe | PayPal |
|---------|--------|--------|
| Payment Flow | Client-side confirmation | Redirect to PayPal |
| User Experience | Stay on site | Leave site temporarily |
| Payment Capture | Automatic with Payment Intent | Manual execution required |
| Webhook Verification | Signature in header | Multiple headers required |
| Refunds | Use payment_intent_id | Use sale_id from transaction |

## Resources

- [PayPal REST API Documentation](https://developer.paypal.com/docs/api/overview/)
- [PayPal Payments Guide](https://developer.paypal.com/docs/checkout/)
- [PayPal Webhooks Guide](https://developer.paypal.com/docs/api-basics/notifications/webhooks/)
- [PayPal Testing Guide](https://developer.paypal.com/docs/api-basics/sandbox/)
- [PayPal Security Best Practices](https://developer.paypal.com/docs/api-basics/security/)

## Troubleshooting

### Payment creation fails
- Verify API credentials are correct
- Check `PAYPAL_MODE` matches your credentials (sandbox vs live)
- Ensure amount is positive and properly formatted
- Verify return_url and cancel_url are valid HTTPS URLs (in production)

### Payment execution fails
- Check payment hasn't already been executed
- Verify payment_id and payer_id are correct
- Ensure payment hasn't expired (payments expire after 3 hours)

### Webhooks not received
- Verify webhook URL is accessible from internet (use ngrok for local testing)
- Check webhook is configured in PayPal app settings
- Ensure webhook URL uses HTTPS in production
- Verify firewall allows PayPal webhook IPs

### Signature verification fails
- Check all webhook headers are being passed correctly
- Verify webhook_id matches the one in PayPal dashboard
- Ensure webhook event body is passed as-is (not modified)
