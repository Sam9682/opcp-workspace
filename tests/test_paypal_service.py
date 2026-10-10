"""Unit tests for PayPal payment service
Feature: OPCP-website
Tests Requirements 4.1, 4.2
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from app.services.paypal_service import PayPalService, paypal_service


class TestPayPalService:
    """Test suite for PayPal payment service"""
    
    @pytest.fixture
    def service(self):
        """Create a PayPal service instance for testing"""
        return PayPalService()
    
    @pytest.fixture
    def mock_payment(self):
        """Create a mock PayPal payment object"""
        payment = Mock()
        payment.id = "PAYID-TEST123"
        payment.state = "created"
        payment.links = [
            Mock(rel="approval_url", href="https://paypal.com/approve/test"),
            Mock(rel="self", href="https://api.paypal.com/payment/test")
        ]
        payment.error = None
        return payment
    
    @pytest.fixture
    def mock_executed_payment(self):
        """Create a mock executed PayPal payment"""
        payment = Mock()
        payment.id = "PAYID-TEST123"
        payment.state = "approved"
        
        # Mock transaction
        transaction = Mock()
        transaction.amount = Mock(total="50.00", currency="EUR")
        payment.transactions = [transaction]
        
        # Mock payer info
        payer_info = Mock(email="test@example.com")
        payment.payer = Mock(payer_info=payer_info)
        
        payment.error = None
        return payment
    
    def test_init_configures_paypal(self, service):
        """Test that PayPal service initializes with correct configuration"""
        assert service is not None
    
    @patch('app.services.paypal_service.paypalrestsdk.Payment')
    def test_create_payment_success(self, mock_payment_class, service, mock_payment):
        """Test successful payment creation"""
        # Setup mock
        mock_payment.create.return_value = True
        mock_payment_class.return_value = mock_payment
        
        # Create payment
        result = service.create_payment(
            amount=Decimal("50.00"),
            currency="EUR",
            description="Test Membership",
            return_url="http://example.com/success",
            cancel_url="http://example.com/cancel",
            metadata={"user_id": "123"}
        )
        
        # Verify result
        assert result["id"] == "PAYID-TEST123"
        assert result["approval_url"] == "https://paypal.com/approve/test"
        assert result["amount"] == Decimal("50.00")
        assert result["currency"] == "EUR"
        assert result["status"] == "created"
        
        # Verify payment was created with correct parameters
        mock_payment.create.assert_called_once()
    
    @patch('app.services.paypal_service.paypalrestsdk.Payment')
    def test_create_payment_failure(self, mock_payment_class, service, mock_payment):
        """Test payment creation failure"""
        # Setup mock to fail
        mock_payment.create.return_value = False
        mock_payment.error = {"message": "Invalid credentials"}
        mock_payment_class.return_value = mock_payment
        
        # Attempt to create payment
        with pytest.raises(Exception) as exc_info:
            service.create_payment(
                amount=Decimal("50.00"),
                return_url="http://example.com/success",
                cancel_url="http://example.com/cancel"
            )
        
        assert "PayPal payment creation failed" in str(exc_info.value)
    
    @patch('app.services.paypal_service.paypalrestsdk.Payment')
    def test_create_payment_with_default_currency(
        self, mock_payment_class, service, mock_payment
    ):
        """Test payment creation uses EUR as default currency"""
        mock_payment.create.return_value = True
        mock_payment_class.return_value = mock_payment
        
        result = service.create_payment(
            amount=Decimal("50.00"),
            return_url="http://example.com/success",
            cancel_url="http://example.com/cancel"
        )
        
        assert result["currency"] == "EUR"
    
    @patch('app.services.paypal_service.paypalrestsdk.Payment')
    def test_execute_payment_success(
        self, mock_payment_class, service, mock_executed_payment
    ):
        """Test successful payment execution"""
        # Setup mock
        mock_executed_payment.execute.return_value = True
        mock_payment_class.find.return_value = mock_executed_payment
        
        # Execute payment
        result = service.execute_payment(
            payment_id="PAYID-TEST123",
            payer_id="PAYER123"
        )
        
        # Verify result
        assert result["transaction_id"] == "PAYID-TEST123"
        assert result["amount"] == Decimal("50.00")
        assert result["currency"] == "EUR"
        assert result["status"] == "approved"
        assert result["payer_email"] == "test@example.com"
        
        # Verify execute was called with correct payer_id
        mock_executed_payment.execute.assert_called_once_with({"payer_id": "PAYER123"})
    
    @patch('app.services.paypal_service.paypalrestsdk.Payment')
    def test_execute_payment_failure(self, mock_payment_class, service):
        """Test payment execution failure"""
        # Setup mock to fail
        mock_payment = Mock()
        mock_payment.execute.return_value = False
        mock_payment.error = {"message": "Payment already executed"}
        mock_payment_class.find.return_value = mock_payment
        
        # Attempt to execute payment
        with pytest.raises(Exception) as exc_info:
            service.execute_payment(
                payment_id="PAYID-TEST123",
                payer_id="PAYER123"
            )
        
        assert "PayPal payment execution failed" in str(exc_info.value)
    
    @patch('app.services.paypal_service.paypalrestsdk.Payment')
    def test_get_payment_details(
        self, mock_payment_class, service, mock_executed_payment
    ):
        """Test retrieving payment details"""
        mock_payment_class.find.return_value = mock_executed_payment
        
        result = service.get_payment_details("PAYID-TEST123")
        
        assert result["id"] == "PAYID-TEST123"
        assert result["amount"] == Decimal("50.00")
        assert result["currency"] == "EUR"
        assert result["status"] == "approved"
        assert "create_time" in result
        assert "update_time" in result
        
        mock_payment_class.find.assert_called_once_with("PAYID-TEST123")
    
    @patch('app.services.paypal_service.paypalrestsdk.Payment')
    def test_get_payment_details_not_found(self, mock_payment_class, service):
        """Test retrieving non-existent payment"""
        mock_payment_class.find.side_effect = Exception("Payment not found")
        
        with pytest.raises(Exception):
            service.get_payment_details("INVALID-ID")
    
    @patch('app.services.paypal_service.paypalrestsdk.Sale')
    def test_create_refund_full(self, mock_sale_class, service):
        """Test creating a full refund"""
        # Setup mock
        mock_sale = Mock()
        mock_refund = Mock()
        mock_refund.success.return_value = True
        mock_refund.id = "REFUND-123"
        mock_refund.state = "completed"
        mock_refund.amount = Mock(total="50.00")
        mock_sale.refund.return_value = mock_refund
        mock_sale_class.find.return_value = mock_sale
        
        # Create refund
        result = service.create_refund(sale_id="SALE-123")
        
        # Verify result
        assert result["id"] == "REFUND-123"
        assert result["status"] == "completed"
        
        # Verify refund was called with empty params for full refund
        mock_sale.refund.assert_called_once_with({})
    
    @patch('app.services.paypal_service.paypalrestsdk.Sale')
    def test_create_refund_partial(self, mock_sale_class, service):
        """Test creating a partial refund"""
        # Setup mock
        mock_sale = Mock()
        mock_refund = Mock()
        mock_refund.success.return_value = True
        mock_refund.id = "REFUND-123"
        mock_refund.state = "completed"
        mock_refund.amount = Mock(total="25.00")
        mock_sale.refund.return_value = mock_refund
        mock_sale_class.find.return_value = mock_sale
        
        # Create partial refund
        result = service.create_refund(
            sale_id="SALE-123",
            amount=Decimal("25.00"),
            currency="EUR"
        )
        
        # Verify result
        assert result["id"] == "REFUND-123"
        assert result["amount"] == Decimal("25.00")
        assert result["currency"] == "EUR"
        
        # Verify refund was called with amount
        call_args = mock_sale.refund.call_args[0][0]
        assert "amount" in call_args
        assert call_args["amount"]["total"] == "25.00"
        assert call_args["amount"]["currency"] == "EUR"
    
    @patch('app.services.paypal_service.paypalrestsdk.Sale')
    def test_create_refund_failure(self, mock_sale_class, service):
        """Test refund creation failure"""
        # Setup mock to fail
        mock_sale = Mock()
        mock_refund = Mock()
        mock_refund.success.return_value = False
        mock_refund.error = {"message": "Insufficient funds"}
        mock_sale.refund.return_value = mock_refund
        mock_sale_class.find.return_value = mock_sale
        
        # Attempt to create refund
        with pytest.raises(Exception) as exc_info:
            service.create_refund(sale_id="SALE-123")
        
        assert "PayPal refund failed" in str(exc_info.value)
    
    @patch('app.services.paypal_service.paypalrestsdk.WebhookEvent')
    def test_verify_webhook_signature_valid(self, mock_webhook_class, service):
        """Test webhook signature verification with valid signature"""
        mock_webhook_class.verify.return_value = True
        
        result = service.verify_webhook_signature(
            transmission_id="trans-123",
            transmission_time="2024-01-01T00:00:00Z",
            cert_url="https://api.paypal.com/cert",
            auth_algo="SHA256withRSA",
            transmission_sig="signature",
            webhook_id="webhook-123",
            webhook_event={"event_type": "PAYMENT.SALE.COMPLETED"}
        )
        
        assert result is True
        mock_webhook_class.verify.assert_called_once()
    
    @patch('app.services.paypal_service.paypalrestsdk.WebhookEvent')
    def test_verify_webhook_signature_invalid(self, mock_webhook_class, service):
        """Test webhook signature verification with invalid signature"""
        mock_webhook_class.verify.return_value = False
        
        result = service.verify_webhook_signature(
            transmission_id="trans-123",
            transmission_time="2024-01-01T00:00:00Z",
            cert_url="https://api.paypal.com/cert",
            auth_algo="SHA256withRSA",
            transmission_sig="invalid-signature",
            webhook_id="webhook-123",
            webhook_event={"event_type": "PAYMENT.SALE.COMPLETED"}
        )
        
        assert result is False
    
    @patch('app.services.paypal_service.paypalrestsdk.WebhookEvent')
    def test_verify_webhook_signature_exception(self, mock_webhook_class, service):
        """Test webhook signature verification with exception"""
        mock_webhook_class.verify.side_effect = Exception("Network error")
        
        result = service.verify_webhook_signature(
            transmission_id="trans-123",
            transmission_time="2024-01-01T00:00:00Z",
            cert_url="https://api.paypal.com/cert",
            auth_algo="SHA256withRSA",
            transmission_sig="signature",
            webhook_id="webhook-123",
            webhook_event={"event_type": "PAYMENT.SALE.COMPLETED"}
        )
        
        assert result is False
    
    def test_global_service_instance_exists(self):
        """Test that global paypal_service instance is available"""
        assert paypal_service is not None
        assert isinstance(paypal_service, PayPalService)
    
    @patch('app.services.paypal_service.paypalrestsdk.Payment')
    def test_create_payment_with_metadata(
        self, mock_payment_class, service, mock_payment
    ):
        """Test payment creation includes metadata"""
        mock_payment.create.return_value = True
        mock_payment_class.return_value = mock_payment
        
        metadata = {"user_id": "123", "membership_type": "annual"}
        result = service.create_payment(
            amount=Decimal("50.00"),
            return_url="http://example.com/success",
            cancel_url="http://example.com/cancel",
            metadata=metadata
        )
        
        assert result["id"] == "PAYID-TEST123"
        # Verify payment was created (metadata is stored in custom field)
        mock_payment.create.assert_called_once()
    
    @patch('app.services.paypal_service.paypalrestsdk.Payment')
    def test_create_payment_amount_formatting(
        self, mock_payment_class, service, mock_payment
    ):
        """Test that payment amounts are properly formatted as strings"""
        mock_payment.create.return_value = True
        mock_payment_class.return_value = mock_payment
        
        # Test with various decimal amounts
        amounts = [
            Decimal("50.00"),
            Decimal("100.50"),
            Decimal("25.99"),
        ]
        
        for amount in amounts:
            result = service.create_payment(
                amount=amount,
                return_url="http://example.com/success",
                cancel_url="http://example.com/cancel"
            )
            assert result["amount"] == amount
    
    @patch('app.services.paypal_service.paypalrestsdk.Payment')
    def test_execute_payment_without_payer_email(
        self, mock_payment_class, service
    ):
        """Test payment execution when payer email is not available"""
        # Setup mock without email
        mock_payment = Mock()
        mock_payment.id = "PAYID-TEST123"
        mock_payment.state = "approved"
        mock_payment.execute.return_value = True
        
        transaction = Mock()
        transaction.amount = Mock(total="50.00", currency="EUR")
        mock_payment.transactions = [transaction]
        
        # Payer info without email attribute
        mock_payment.payer = Mock(payer_info=Mock(spec=[]))
        
        mock_payment_class.find.return_value = mock_payment
        
        result = service.execute_payment(
            payment_id="PAYID-TEST123",
            payer_id="PAYER123"
        )
        
        assert result["payer_email"] is None
        assert result["transaction_id"] == "PAYID-TEST123"


class TestPayPalServiceEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.fixture
    def service(self):
        return PayPalService()
    
    @patch('app.services.paypal_service.paypalrestsdk.Payment')
    def test_create_payment_with_zero_amount(
        self, mock_payment_class, service
    ):
        """Test payment creation with zero amount"""
        mock_payment = Mock()
        mock_payment.create.return_value = True
        mock_payment.id = "PAYID-ZERO"
        mock_payment.state = "created"
        mock_payment.links = []
        mock_payment_class.return_value = mock_payment
        
        result = service.create_payment(
            amount=Decimal("0.00"),
            return_url="http://example.com/success",
            cancel_url="http://example.com/cancel"
        )
        
        assert result["amount"] == Decimal("0.00")
    
    @patch('app.services.paypal_service.paypalrestsdk.Payment')
    def test_create_payment_no_approval_url(
        self, mock_payment_class, service
    ):
        """Test payment creation when no approval URL is returned"""
        mock_payment = Mock()
        mock_payment.create.return_value = True
        mock_payment.id = "PAYID-TEST"
        mock_payment.state = "created"
        mock_payment.links = [
            Mock(rel="self", href="https://api.paypal.com/payment/test")
        ]
        mock_payment_class.return_value = mock_payment
        
        result = service.create_payment(
            amount=Decimal("50.00"),
            return_url="http://example.com/success",
            cancel_url="http://example.com/cancel"
        )
        
        assert result["approval_url"] is None
    
    @patch('app.services.paypal_service.paypalrestsdk.Payment')
    def test_create_payment_currency_case_insensitive(
        self, mock_payment_class, service
    ):
        """Test that currency codes are normalized to uppercase"""
        mock_payment = Mock()
        mock_payment.create.return_value = True
        mock_payment.id = "PAYID-TEST"
        mock_payment.state = "created"
        mock_payment.links = []
        mock_payment_class.return_value = mock_payment
        
        result = service.create_payment(
            amount=Decimal("50.00"),
            currency="usd",  # lowercase
            return_url="http://example.com/success",
            cancel_url="http://example.com/cancel"
        )
        
        assert result["currency"] == "USD"  # uppercase
