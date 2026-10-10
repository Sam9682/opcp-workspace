"""Tests for Stripe payment service
Feature: OPCP-website
Validates Requirements 4.1, 4.2
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
import stripe
from app.services.stripe_service import StripeService, stripe_service


class TestStripeServiceInitialization:
    """Test Stripe service initialization and configuration"""
    
    def test_stripe_service_instance_exists(self):
        """Test that global stripe_service instance is created"""
        assert stripe_service is not None
        assert isinstance(stripe_service, StripeService)
    
    def test_stripe_api_key_configured(self):
        """Test that Stripe API key is configured from settings"""
        # The API key should be set during initialization
        assert stripe.api_key is not None
    
    def test_webhook_secret_configured(self):
        """Test that webhook secret is configured"""
        assert stripe_service.webhook_secret is not None


class TestCreatePaymentIntent:
    """Test payment intent creation"""
    
    @patch('stripe.PaymentIntent.create')
    def test_create_payment_intent_success(self, mock_create):
        """Test successful payment intent creation"""
        # Arrange
        mock_payment_intent = Mock()
        mock_payment_intent.id = "pi_test123"
        mock_payment_intent.client_secret = "pi_test123_secret"
        mock_payment_intent.status = "requires_payment_method"
        mock_create.return_value = mock_payment_intent
        
        service = StripeService()
        amount = Decimal("50.00")
        
        # Act
        result = service.create_payment_intent(amount, currency="eur")
        
        # Assert
        assert result["id"] == "pi_test123"
        assert result["client_secret"] == "pi_test123_secret"
        assert result["amount"] == amount
        assert result["currency"] == "eur"
        assert result["status"] == "requires_payment_method"
        
        # Verify Stripe API was called correctly
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["amount"] == 5000  # 50.00 EUR in cents
        assert call_kwargs["currency"] == "eur"
    
    @patch('stripe.PaymentIntent.create')
    def test_create_payment_intent_with_metadata(self, mock_create):
        """Test payment intent creation with metadata"""
        # Arrange
        mock_payment_intent = Mock()
        mock_payment_intent.id = "pi_test456"
        mock_payment_intent.client_secret = "pi_test456_secret"
        mock_payment_intent.status = "requires_payment_method"
        mock_create.return_value = mock_payment_intent
        
        service = StripeService()
        metadata = {"user_id": "123", "membership_year": "2024"}
        
        # Act
        result = service.create_payment_intent(
            Decimal("50.00"),
            currency="eur",
            metadata=metadata
        )
        
        # Assert
        assert result["id"] == "pi_test456"
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["metadata"] == metadata
    
    @patch('stripe.PaymentIntent.create')
    def test_create_payment_intent_stripe_error(self, mock_create):
        """Test payment intent creation with Stripe error"""
        # Arrange
        mock_create.side_effect = stripe.error.StripeError("API error")
        service = StripeService()
        
        # Act & Assert
        with pytest.raises(stripe.error.StripeError):
            service.create_payment_intent(Decimal("50.00"))


class TestWebhookVerification:
    """Test webhook signature verification"""
    
    @patch('stripe.Webhook.construct_event')
    def test_verify_webhook_signature_success(self, mock_construct):
        """Test successful webhook signature verification"""
        # Arrange
        mock_event = Mock()
        mock_event.type = "payment_intent.succeeded"
        mock_construct.return_value = mock_event
        
        service = StripeService()
        payload = b'{"test": "data"}'
        signature = "test_signature"
        
        # Act
        event = service.verify_webhook_signature(payload, signature)
        
        # Assert
        assert event == mock_event
        mock_construct.assert_called_once_with(
            payload, signature, service.webhook_secret
        )
    
    @patch('stripe.Webhook.construct_event')
    def test_verify_webhook_signature_invalid(self, mock_construct):
        """Test webhook signature verification with invalid signature"""
        # Arrange
        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            "Invalid signature", "sig_header"
        )
        service = StripeService()
        
        # Act & Assert
        with pytest.raises(stripe.error.SignatureVerificationError):
            service.verify_webhook_signature(b'{"test": "data"}', "bad_signature")


class TestPaymentIntentHandlers:
    """Test payment intent event handlers"""
    
    def test_handle_payment_intent_succeeded(self):
        """Test handling successful payment intent"""
        # Arrange
        service = StripeService()
        payment_intent = {
            "id": "pi_success123",
            "amount": 5000,  # 50.00 EUR in cents
            "currency": "eur",
            "metadata": {"user_id": "123"}
        }
        
        # Act
        result = service.handle_payment_intent_succeeded(payment_intent)
        
        # Assert
        assert result["transaction_id"] == "pi_success123"
        assert result["amount"] == Decimal("50.00")
        assert result["currency"] == "EUR"
        assert result["metadata"]["user_id"] == "123"
    
    def test_handle_payment_intent_failed(self):
        """Test handling failed payment intent"""
        # Arrange
        service = StripeService()
        payment_intent = {
            "id": "pi_failed123",
            "last_payment_error": {
                "message": "Card declined"
            },
            "metadata": {"user_id": "123"}
        }
        
        # Act
        result = service.handle_payment_intent_failed(payment_intent)
        
        # Assert
        assert result["transaction_id"] == "pi_failed123"
        assert result["error_message"] == "Card declined"
        assert result["metadata"]["user_id"] == "123"
    
    def test_handle_payment_intent_failed_no_error_message(self):
        """Test handling failed payment intent without error message"""
        # Arrange
        service = StripeService()
        payment_intent = {
            "id": "pi_failed456",
            "metadata": {}
        }
        
        # Act
        result = service.handle_payment_intent_failed(payment_intent)
        
        # Assert
        assert result["transaction_id"] == "pi_failed456"
        assert result["error_message"] == "Unknown error"


class TestRetrievePaymentIntent:
    """Test payment intent retrieval"""
    
    @patch('stripe.PaymentIntent.retrieve')
    def test_retrieve_payment_intent_success(self, mock_retrieve):
        """Test successful payment intent retrieval"""
        # Arrange
        mock_payment_intent = Mock()
        mock_payment_intent.id = "pi_retrieve123"
        mock_payment_intent.amount = 5000
        mock_payment_intent.currency = "eur"
        mock_payment_intent.status = "succeeded"
        mock_payment_intent.metadata = {"user_id": "123"}
        mock_retrieve.return_value = mock_payment_intent
        
        service = StripeService()
        
        # Act
        result = service.retrieve_payment_intent("pi_retrieve123")
        
        # Assert
        assert result["id"] == "pi_retrieve123"
        assert result["amount"] == Decimal("50.00")
        assert result["currency"] == "EUR"
        assert result["status"] == "succeeded"
        mock_retrieve.assert_called_once_with("pi_retrieve123")
    
    @patch('stripe.PaymentIntent.retrieve')
    def test_retrieve_payment_intent_error(self, mock_retrieve):
        """Test payment intent retrieval with error"""
        # Arrange
        mock_retrieve.side_effect = stripe.error.StripeError("Not found")
        service = StripeService()
        
        # Act & Assert
        with pytest.raises(stripe.error.StripeError):
            service.retrieve_payment_intent("pi_notfound")


class TestCreateRefund:
    """Test refund creation"""
    
    @patch('stripe.Refund.create')
    def test_create_full_refund(self, mock_create):
        """Test creating a full refund"""
        # Arrange
        mock_refund = Mock()
        mock_refund.id = "re_test123"
        mock_refund.amount = 5000
        mock_refund.currency = "eur"
        mock_refund.status = "succeeded"
        mock_refund.reason = None
        mock_create.return_value = mock_refund
        
        service = StripeService()
        
        # Act
        result = service.create_refund("pi_test123")
        
        # Assert
        assert result["id"] == "re_test123"
        assert result["amount"] == Decimal("50.00")
        assert result["currency"] == "EUR"
        assert result["status"] == "succeeded"
        mock_create.assert_called_once_with(payment_intent="pi_test123")
    
    @patch('stripe.Refund.create')
    def test_create_partial_refund_with_reason(self, mock_create):
        """Test creating a partial refund with reason"""
        # Arrange
        mock_refund = Mock()
        mock_refund.id = "re_test456"
        mock_refund.amount = 2500
        mock_refund.currency = "eur"
        mock_refund.status = "succeeded"
        mock_refund.reason = "requested_by_customer"
        mock_create.return_value = mock_refund
        
        service = StripeService()
        
        # Act
        result = service.create_refund(
            "pi_test123",
            amount=Decimal("25.00"),
            reason="requested_by_customer"
        )
        
        # Assert
        assert result["id"] == "re_test456"
        assert result["amount"] == Decimal("25.00")
        assert result["reason"] == "requested_by_customer"
        
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["payment_intent"] == "pi_test123"
        assert call_kwargs["amount"] == 2500
        assert call_kwargs["reason"] == "requested_by_customer"
    
    @patch('stripe.Refund.create')
    def test_create_refund_error(self, mock_create):
        """Test refund creation with error"""
        # Arrange
        mock_create.side_effect = stripe.error.StripeError("Refund failed")
        service = StripeService()
        
        # Act & Assert
        with pytest.raises(stripe.error.StripeError):
            service.create_refund("pi_test123")
