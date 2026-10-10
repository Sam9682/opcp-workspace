"""Unit tests for payment webhook handlers
Feature: OPCP-website
Validates Requirements 4.2
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch
import json
import stripe

from app.main import app
from app.models import User, Payment, PaymentMethod, PaymentStatus, UserRole
from app.database import get_db


def assert_membership_approximately_one_year_from_now(user: User, db_session) -> None:
    """Helper to assert membership is approximately 1 year from now
    
    Handles timezone-naive datetimes from SQLite.
    """
    db_session.refresh(user)
    assert user.membership_expires_at is not None
    
    # Handle timezone-naive datetime from SQLite
    if user.membership_expires_at.tzinfo is None:
        actual_expiry = user.membership_expires_at.replace(tzinfo=timezone.utc)
    else:
        actual_expiry = user.membership_expires_at
    
    expected_expiry = datetime.now(timezone.utc) + timedelta(days=365)
    time_diff = abs((actual_expiry - expected_expiry).total_seconds())
    assert time_diff < 60, f"Membership expiry {actual_expiry} not within 1 minute of expected {expected_expiry}"


def assert_membership_extended_by_one_year(user: User, original_expiry: datetime, db_session) -> None:
    """Helper to assert membership was extended by 1 year from original expiry
    
    Handles timezone-naive datetimes from SQLite.
    """
    db_session.refresh(user)
    assert user.membership_expires_at is not None
    
    # Handle timezone-naive datetime from SQLite
    if user.membership_expires_at.tzinfo is None:
        actual_expiry = user.membership_expires_at.replace(tzinfo=timezone.utc)
    else:
        actual_expiry = user.membership_expires_at
    
    # Make sure original expiry is timezone-aware
    if original_expiry.tzinfo is None:
        original_expiry = original_expiry.replace(tzinfo=timezone.utc)
    
    expected_expiry = original_expiry + timedelta(days=365)
    time_diff = abs((actual_expiry - expected_expiry).total_seconds())
    assert time_diff < 60, f"Membership expiry {actual_expiry} not within 1 minute of expected {expected_expiry}"


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True,
        membership_expires_at=None
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_payment(db_session, test_user):
    """Create a test payment"""
    payment = Payment(
        user_id=test_user.id,
        amount=Decimal("50.00"),
        currency="EUR",
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.PENDING,
        transaction_id="pi_test_123456"
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)
    return payment


class TestStripeWebhook:
    """Test Stripe webhook handler"""
    
    def test_stripe_webhook_missing_signature(self, client):
        """Test webhook rejects request without signature"""
        response = client.post(
            "/api/payments/stripe/webhook",
            json={"type": "payment_intent.succeeded"}
        )
        
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "MISSING_SIGNATURE"
    
    @patch('app.payments.router.stripe_service.verify_webhook_signature')
    def test_stripe_webhook_invalid_signature(self, mock_verify, client):
        """Test webhook rejects invalid signature"""
        mock_verify.side_effect = stripe.error.SignatureVerificationError(
            "Invalid signature", "sig_header"
        )
        
        response = client.post(
            "/api/payments/stripe/webhook",
            json={"type": "payment_intent.succeeded"},
            headers={"Stripe-Signature": "invalid_signature"}
        )
        
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "INVALID_SIGNATURE"
    
    @patch('app.payments.router.stripe_service.verify_webhook_signature')
    @patch('app.payments.router.stripe_service.handle_payment_intent_succeeded')
    def test_stripe_webhook_payment_succeeded(
        self,
        mock_handle_success,
        mock_verify,
        client,
        db_session,
        test_user,
        test_payment
    ):
        """Test successful payment webhook updates payment and membership"""
        # Mock webhook verification
        mock_event = Mock()
        mock_event.type = "payment_intent.succeeded"
        mock_event.data.object = {
            "id": "pi_test_123456",
            "amount": 5000,
            "currency": "eur"
        }
        mock_verify.return_value = mock_event
        
        # Mock payment intent handler
        mock_handle_success.return_value = {
            "transaction_id": "pi_test_123456",
            "amount": Decimal("50.00"),
            "currency": "EUR",
            "metadata": {}
        }
        
        # Send webhook
        response = client.post(
            "/api/payments/stripe/webhook",
            json={"type": "payment_intent.succeeded"},
            headers={"Stripe-Signature": "valid_signature"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # Verify payment status updated
        db_session.refresh(test_payment)
        assert test_payment.status == PaymentStatus.COMPLETED
        
        # Verify user membership updated (approximately 1 year from now)
        assert_membership_approximately_one_year_from_now(test_user, db_session)
    
    @patch('app.payments.router.stripe_service.verify_webhook_signature')
    @patch('app.payments.router.stripe_service.handle_payment_intent_succeeded')
    def test_stripe_webhook_extends_existing_membership(
        self,
        mock_handle_success,
        mock_verify,
        client,
        db_session,
        test_user,
        test_payment
    ):
        """Test webhook extends existing active membership"""
        # Set existing membership expiration (timezone-aware)
        existing_expiry = datetime.now(timezone.utc) + timedelta(days=100)
        test_user.membership_expires_at = existing_expiry
        db_session.commit()
        db_session.refresh(test_user)
        
        # Mock webhook verification
        mock_event = Mock()
        mock_event.type = "payment_intent.succeeded"
        mock_event.data.object = {"id": "pi_test_123456"}
        mock_verify.return_value = mock_event
        
        # Mock payment intent handler
        mock_handle_success.return_value = {
            "transaction_id": "pi_test_123456",
            "amount": Decimal("50.00"),
            "currency": "EUR",
            "metadata": {}
        }
        
        # Send webhook
        response = client.post(
            "/api/payments/stripe/webhook",
            json={"type": "payment_intent.succeeded"},
            headers={"Stripe-Signature": "valid_signature"}
        )
        
        assert response.status_code == 200
        
        # Verify membership extended from existing expiry
        assert_membership_extended_by_one_year(test_user, existing_expiry, db_session)
    
    @patch('app.payments.router.stripe_service.verify_webhook_signature')
    @patch('app.payments.router.stripe_service.handle_payment_intent_succeeded')
    def test_stripe_webhook_payment_not_found(
        self,
        mock_handle_success,
        mock_verify,
        client
    ):
        """Test webhook handles missing payment record gracefully"""
        # Mock webhook verification
        mock_event = Mock()
        mock_event.type = "payment_intent.succeeded"
        mock_event.data.object = {"id": "pi_nonexistent"}
        mock_verify.return_value = mock_event
        
        # Mock payment intent handler
        mock_handle_success.return_value = {
            "transaction_id": "pi_nonexistent",
            "amount": Decimal("50.00"),
            "currency": "EUR",
            "metadata": {}
        }
        
        # Send webhook
        response = client.post(
            "/api/payments/stripe/webhook",
            json={"type": "payment_intent.succeeded"},
            headers={"Stripe-Signature": "valid_signature"}
        )
        
        # Should still return 200 to acknowledge webhook
        assert response.status_code == 200
        assert response.json()["status"] == "payment_not_found"
    
    @patch('app.payments.router.stripe_service.verify_webhook_signature')
    @patch('app.payments.router.stripe_service.handle_payment_intent_failed')
    def test_stripe_webhook_payment_failed(
        self,
        mock_handle_failed,
        mock_verify,
        client,
        db_session,
        test_payment
    ):
        """Test failed payment webhook updates payment status"""
        # Mock webhook verification
        mock_event = Mock()
        mock_event.type = "payment_intent.payment_failed"
        mock_event.data.object = {"id": "pi_test_123456"}
        mock_verify.return_value = mock_event
        
        # Mock payment intent handler
        mock_handle_failed.return_value = {
            "transaction_id": "pi_test_123456",
            "error_message": "Card declined",
            "metadata": {}
        }
        
        # Send webhook
        response = client.post(
            "/api/payments/stripe/webhook",
            json={"type": "payment_intent.payment_failed"},
            headers={"Stripe-Signature": "valid_signature"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "failure_recorded"
        
        # Verify payment status updated to failed
        db_session.refresh(test_payment)
        assert test_payment.status == PaymentStatus.FAILED
    
    @patch('app.payments.router.stripe_service.verify_webhook_signature')
    def test_stripe_webhook_unhandled_event(self, mock_verify, client):
        """Test webhook ignores unhandled event types"""
        # Mock webhook verification
        mock_event = Mock()
        mock_event.type = "customer.created"
        mock_event.data.object = {}
        mock_verify.return_value = mock_event
        
        # Send webhook
        response = client.post(
            "/api/payments/stripe/webhook",
            json={"type": "customer.created"},
            headers={"Stripe-Signature": "valid_signature"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "event_ignored"


class TestPayPalWebhook:
    """Test PayPal webhook handler"""
    
    def test_paypal_webhook_payment_completed(
        self,
        client,
        db_session,
        test_user
    ):
        """Test PayPal payment completion webhook"""
        # Create PayPal payment
        payment = Payment(
            user_id=test_user.id,
            amount=Decimal("50.00"),
            currency="EUR",
            payment_method=PaymentMethod.PAYPAL,
            status=PaymentStatus.PENDING,
            transaction_id="PAYID-TEST123"
        )
        db_session.add(payment)
        db_session.commit()
        
        # Send webhook
        webhook_data = {
            "event_type": "PAYMENT.SALE.COMPLETED",
            "resource": {
                "parent_payment": "PAYID-TEST123",
                "amount": {
                    "total": "50.00",
                    "currency": "EUR"
                }
            }
        }
        
        response = client.post(
            "/api/payments/paypal/webhook",
            json=webhook_data
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # Verify payment status updated
        db_session.refresh(payment)
        assert payment.status == PaymentStatus.COMPLETED
        
        # Verify user membership updated (approximately 1 year from now)
        assert_membership_approximately_one_year_from_now(test_user, db_session)
    
    def test_paypal_webhook_extends_existing_membership(
        self,
        client,
        db_session,
        test_user
    ):
        """Test PayPal webhook extends existing active membership"""
        # Set existing membership expiration (timezone-aware)
        existing_expiry = datetime.now(timezone.utc) + timedelta(days=200)
        test_user.membership_expires_at = existing_expiry
        db_session.commit()
        db_session.refresh(test_user)
        
        # Create PayPal payment
        payment = Payment(
            user_id=test_user.id,
            amount=Decimal("50.00"),
            currency="EUR",
            payment_method=PaymentMethod.PAYPAL,
            status=PaymentStatus.PENDING,
            transaction_id="PAYID-TEST456"
        )
        db_session.add(payment)
        db_session.commit()
        
        # Send webhook
        webhook_data = {
            "event_type": "PAYMENT.SALE.COMPLETED",
            "resource": {
                "parent_payment": "PAYID-TEST456"
            }
        }
        
        response = client.post(
            "/api/payments/paypal/webhook",
            json=webhook_data
        )
        
        assert response.status_code == 200
        
        # Verify membership extended from existing expiry
        assert_membership_extended_by_one_year(test_user, existing_expiry, db_session)
    
    def test_paypal_webhook_payment_not_found(self, client):
        """Test PayPal webhook handles missing payment gracefully"""
        webhook_data = {
            "event_type": "PAYMENT.SALE.COMPLETED",
            "resource": {
                "parent_payment": "PAYID-NONEXISTENT"
            }
        }
        
        response = client.post(
            "/api/payments/paypal/webhook",
            json=webhook_data
        )
        
        # Should still return 200 to acknowledge webhook
        assert response.status_code == 200
        assert response.json()["status"] == "payment_not_found"
    
    def test_paypal_webhook_missing_payment_id(self, client):
        """Test PayPal webhook handles missing parent_payment"""
        webhook_data = {
            "event_type": "PAYMENT.SALE.COMPLETED",
            "resource": {}
        }
        
        response = client.post(
            "/api/payments/paypal/webhook",
            json=webhook_data
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "missing_payment_id"
    
    def test_paypal_webhook_payment_denied(
        self,
        client,
        db_session,
        test_user
    ):
        """Test PayPal payment denied webhook"""
        # Create PayPal payment
        payment = Payment(
            user_id=test_user.id,
            amount=Decimal("50.00"),
            currency="EUR",
            payment_method=PaymentMethod.PAYPAL,
            status=PaymentStatus.PENDING,
            transaction_id="PAYID-DENIED123"
        )
        db_session.add(payment)
        db_session.commit()
        
        # Send webhook
        webhook_data = {
            "event_type": "PAYMENT.SALE.DENIED",
            "resource": {
                "parent_payment": "PAYID-DENIED123"
            }
        }
        
        response = client.post(
            "/api/payments/paypal/webhook",
            json=webhook_data
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "failure_recorded"
        
        # Verify payment status updated to failed
        db_session.refresh(payment)
        assert payment.status == PaymentStatus.FAILED
    
    def test_paypal_webhook_payment_refunded(
        self,
        client,
        db_session,
        test_user
    ):
        """Test PayPal payment refunded webhook"""
        # Create completed PayPal payment
        payment = Payment(
            user_id=test_user.id,
            amount=Decimal("50.00"),
            currency="EUR",
            payment_method=PaymentMethod.PAYPAL,
            status=PaymentStatus.COMPLETED,
            transaction_id="PAYID-REFUND123"
        )
        db_session.add(payment)
        db_session.commit()
        
        # Send webhook
        webhook_data = {
            "event_type": "PAYMENT.SALE.REFUNDED",
            "resource": {
                "parent_payment": "PAYID-REFUND123"
            }
        }
        
        response = client.post(
            "/api/payments/paypal/webhook",
            json=webhook_data
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "refund_recorded"
        
        # Verify payment status updated to refunded
        db_session.refresh(payment)
        assert payment.status == PaymentStatus.REFUNDED
    
    def test_paypal_webhook_unhandled_event(self, client):
        """Test PayPal webhook ignores unhandled event types"""
        webhook_data = {
            "event_type": "CUSTOMER.CREATED",
            "resource": {}
        }
        
        response = client.post(
            "/api/payments/paypal/webhook",
            json=webhook_data
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "event_ignored"
    
    def test_paypal_webhook_with_signature_headers(self, client):
        """Test PayPal webhook with signature headers present"""
        webhook_data = {
            "event_type": "PAYMENT.SALE.COMPLETED",
            "resource": {
                "parent_payment": "PAYID-NONEXISTENT"
            }
        }
        
        headers = {
            "Paypal-Transmission-Id": "test-id",
            "Paypal-Transmission-Time": "2024-01-01T00:00:00Z",
            "Paypal-Cert-Url": "https://api.paypal.com/cert",
            "Paypal-Auth-Algo": "SHA256withRSA",
            "Paypal-Transmission-Sig": "test-signature"
        }
        
        response = client.post(
            "/api/payments/paypal/webhook",
            json=webhook_data,
            headers=headers
        )
        
        # Should process normally (signature verification not fully implemented)
        assert response.status_code == 200


class TestWebhookEdgeCases:
    """Test edge cases and error handling"""
    
    @patch('app.payments.router.stripe_service.verify_webhook_signature')
    def test_stripe_webhook_database_error(
        self,
        mock_verify,
        client,
        db_session,
        test_payment
    ):
        """Test webhook handles database errors gracefully"""
        # Mock webhook verification
        mock_event = Mock()
        mock_event.type = "payment_intent.succeeded"
        mock_event.data.object = {"id": "pi_test_123456"}
        mock_verify.return_value = mock_event
        
        # Close database session to simulate error
        db_session.close()
        
        # Send webhook - should return 500 for retry
        response = client.post(
            "/api/payments/stripe/webhook",
            json={"type": "payment_intent.succeeded"},
            headers={"Stripe-Signature": "valid_signature"}
        )
        
        assert response.status_code == 500
        assert response.json()["detail"]["code"] == "WEBHOOK_PROCESSING_FAILED"
    
    def test_paypal_webhook_invalid_json(self, client):
        """Test PayPal webhook handles invalid JSON"""
        response = client.post(
            "/api/payments/paypal/webhook",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        # PayPal webhook catches JSON errors and returns 500 for retry
        assert response.status_code == 500
        assert response.json()["detail"]["code"] == "WEBHOOK_PROCESSING_FAILED"
