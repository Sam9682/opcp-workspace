"""Unit tests for payment initiation endpoint
Feature: OPCP-website
Validates Requirements 4.1, 4.7
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from fastapi import status
from app.models import User, UserRole, Payment, PaymentMethod, PaymentStatus
from app.config import settings


class TestPaymentInitiation:
    """Test suite for POST /api/payments/initiate endpoint"""
    
    def test_initiate_stripe_payment_success(self, client, auth_headers, db_session):
        """Test successful Stripe payment initiation with valid amount"""
        # Mock Stripe service
        with patch('app.payments.router.stripe_service') as mock_stripe:
            mock_stripe.create_payment_intent.return_value = {
                "id": "pi_test123",
                "client_secret": "pi_test123_secret_abc",
                "amount": Decimal("50.00"),
                "currency": "EUR",
                "status": "requires_payment_method"
            }
            
            # Make request
            response = client.post(
                "/api/payments/initiate",
                json={
                    "payment_method": "credit_card",
                    "amount": 50.00,
                    "currency": "EUR"
                },
                headers=auth_headers
            )
            
            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["payment_id"] == "pi_test123"
            assert data["payment_method"] == "credit_card"
            assert data["amount"] == 50.00
            assert data["currency"] == "EUR"
            assert data["client_secret"] == "pi_test123_secret_abc"
            assert data["status"] == "requires_payment_method"
            assert data["approval_url"] is None
            
            # Verify Stripe service was called correctly
            mock_stripe.create_payment_intent.assert_called_once()
            call_args = mock_stripe.create_payment_intent.call_args
            assert call_args[1]["amount"] == Decimal("50.00")
            assert call_args[1]["currency"] == "EUR"
            assert "user_id" in call_args[1]["metadata"]
            assert "payment_id" in call_args[1]["metadata"]
            
            # Verify payment record was created
            payment = db_session.query(Payment).filter(
                Payment.transaction_id == "pi_test123"
            ).first()
            assert payment is not None
            assert payment.amount == Decimal("50.00")
            assert payment.currency == "EUR"
            assert payment.payment_method == PaymentMethod.CREDIT_CARD
            assert payment.status == PaymentStatus.PENDING
    
    def test_initiate_paypal_payment_success(self, client, auth_headers, db_session):
        """Test successful PayPal payment initiation with valid amount and URLs"""
        # Mock PayPal service
        with patch('app.payments.router.paypal_service') as mock_paypal:
            mock_paypal.create_payment.return_value = {
                "id": "PAYID-test123",
                "approval_url": "https://www.paypal.com/checkoutnow?token=test",
                "amount": Decimal("50.00"),
                "currency": "EUR",
                "status": "created"
            }
            
            # Make request
            response = client.post(
                "/api/payments/initiate",
                json={
                    "payment_method": "paypal",
                    "amount": 50.00,
                    "currency": "EUR",
                    "return_url": "https://example.com/success",
                    "cancel_url": "https://example.com/cancel"
                },
                headers=auth_headers
            )
            
            # Assertions
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["payment_id"] == "PAYID-test123"
            assert data["payment_method"] == "paypal"
            assert data["amount"] == 50.00
            assert data["currency"] == "EUR"
            assert data["approval_url"] == "https://www.paypal.com/checkoutnow?token=test"
            assert data["status"] == "created"
            assert data["client_secret"] is None
            
            # Verify PayPal service was called correctly
            mock_paypal.create_payment.assert_called_once()
            call_args = mock_paypal.create_payment.call_args
            assert call_args[1]["amount"] == Decimal("50.00")
            assert call_args[1]["currency"] == "EUR"
            assert call_args[1]["return_url"] == "https://example.com/success"
            assert call_args[1]["cancel_url"] == "https://example.com/cancel"
            
            # Verify payment record was created
            payment = db_session.query(Payment).filter(
                Payment.transaction_id == "PAYID-test123"
            ).first()
            assert payment is not None
            assert payment.amount == Decimal("50.00")
            assert payment.payment_method == PaymentMethod.PAYPAL
            assert payment.status == PaymentStatus.PENDING
    
    def test_initiate_payment_invalid_amount(self, client, auth_headers, db_session):
        """Test payment initiation fails with invalid amount (Property 16)"""
        # Try to pay wrong amount
        response = client.post(
            "/api/payments/initiate",
            json={
                "payment_method": "credit_card",
                "amount": 30.00,  # Wrong amount
                "currency": "EUR"
            },
            headers=auth_headers
        )
        
        # Assertions
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "INVALID_AMOUNT"
        assert "does not match membership fee" in data["detail"]["message"]
        assert data["detail"]["details"]["provided"] == 30.00
        assert data["detail"]["details"]["expected"] == 50.00
        
        # Verify no payment record was created
        payments = db_session.query(Payment).all()
        assert len(payments) == 0
    
    def test_initiate_payment_zero_amount(self, client, auth_headers):
        """Test payment initiation fails with zero amount"""
        response = client.post(
            "/api/payments/initiate",
            json={
                "payment_method": "credit_card",
                "amount": 0.00,
                "currency": "EUR"
            },
            headers=auth_headers
        )
        
        # Should fail validation (amount must be > 0)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_initiate_payment_negative_amount(self, client, auth_headers):
        """Test payment initiation fails with negative amount"""
        response = client.post(
            "/api/payments/initiate",
            json={
                "payment_method": "credit_card",
                "amount": -10.00,
                "currency": "EUR"
            },
            headers=auth_headers
        )
        
        # Should fail validation (amount must be > 0)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_initiate_paypal_payment_missing_return_url(self, client, auth_headers):
        """Test PayPal payment fails without return_url"""
        response = client.post(
            "/api/payments/initiate",
            json={
                "payment_method": "paypal",
                "amount": 50.00,
                "currency": "EUR",
                "cancel_url": "https://example.com/cancel"
                # Missing return_url
            },
            headers=auth_headers
        )
        
        # Assertions
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "MISSING_URLS"
        assert "return_url and cancel_url are required" in data["detail"]["message"]
    
    def test_initiate_paypal_payment_missing_cancel_url(self, client, auth_headers):
        """Test PayPal payment fails without cancel_url"""
        response = client.post(
            "/api/payments/initiate",
            json={
                "payment_method": "paypal",
                "amount": 50.00,
                "currency": "EUR",
                "return_url": "https://example.com/success"
                # Missing cancel_url
            },
            headers=auth_headers
        )
        
        # Assertions
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "MISSING_URLS"
    
    def test_initiate_payment_unauthenticated(self, client):
        """Test payment initiation requires authentication"""
        response = client.post(
            "/api/payments/initiate",
            json={
                "payment_method": "credit_card",
                "amount": 50.00,
                "currency": "EUR"
            }
        )
        
        # HTTPBearer returns 403 when no credentials provided
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_initiate_payment_invalid_currency_format(self, client, auth_headers):
        """Test payment initiation fails with invalid currency format"""
        response = client.post(
            "/api/payments/initiate",
            json={
                "payment_method": "credit_card",
                "amount": 50.00,
                "currency": "EURO"  # Should be 3 letters
            },
            headers=auth_headers
        )
        
        # Should fail validation
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_initiate_payment_currency_case_insensitive(self, client, auth_headers):
        """Test currency code is normalized to uppercase"""
        with patch('app.payments.router.stripe_service') as mock_stripe:
            mock_stripe.create_payment_intent.return_value = {
                "id": "pi_test123",
                "client_secret": "pi_test123_secret_abc",
                "amount": Decimal("50.00"),
                "currency": "EUR",
                "status": "requires_payment_method"
            }
            
            # Send lowercase currency
            response = client.post(
                "/api/payments/initiate",
                json={
                    "payment_method": "credit_card",
                    "amount": 50.00,
                    "currency": "eur"  # lowercase
                },
                headers=auth_headers
            )
            
            # Should succeed and normalize to uppercase
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["currency"] == "EUR"
    
    def test_initiate_stripe_payment_service_failure(self, client, auth_headers, db_session):
        """Test handling of Stripe service failure"""
        with patch('app.payments.router.stripe_service') as mock_stripe:
            mock_stripe.create_payment_intent.side_effect = Exception("Stripe API error")
            
            response = client.post(
                "/api/payments/initiate",
                json={
                    "payment_method": "credit_card",
                    "amount": 50.00,
                    "currency": "EUR"
                },
                headers=auth_headers
            )
            
            # Should return 500 error
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert data["detail"]["code"] == "PAYMENT_INITIATION_FAILED"
            
            # Verify payment record was rolled back
            payments = db_session.query(Payment).all()
            assert len(payments) == 0
    
    def test_initiate_paypal_payment_service_failure(self, client, auth_headers, db_session):
        """Test handling of PayPal service failure"""
        with patch('app.payments.router.paypal_service') as mock_paypal:
            mock_paypal.create_payment.side_effect = Exception("PayPal API error")
            
            response = client.post(
                "/api/payments/initiate",
                json={
                    "payment_method": "paypal",
                    "amount": 50.00,
                    "currency": "EUR",
                    "return_url": "https://example.com/success",
                    "cancel_url": "https://example.com/cancel"
                },
                headers=auth_headers
            )
            
            # Should return 500 error
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert data["detail"]["code"] == "PAYMENT_INITIATION_FAILED"
            
            # Verify payment record was rolled back
            payments = db_session.query(Payment).all()
            assert len(payments) == 0
    
    def test_initiate_payment_missing_payment_method(self, client, auth_headers):
        """Test payment initiation fails without payment method"""
        response = client.post(
            "/api/payments/initiate",
            json={
                "amount": 50.00,
                "currency": "EUR"
            },
            headers=auth_headers
        )
        
        # Should fail validation
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_initiate_payment_invalid_payment_method(self, client, auth_headers):
        """Test payment initiation fails with invalid payment method"""
        response = client.post(
            "/api/payments/initiate",
            json={
                "payment_method": "bitcoin",  # Not supported
                "amount": 50.00,
                "currency": "EUR"
            },
            headers=auth_headers
        )
        
        # Should fail validation
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_initiate_payment_stores_user_metadata(self, client, auth_headers, db_session, test_user):
        """Test that payment stores correct user metadata"""
        with patch('app.payments.router.stripe_service') as mock_stripe:
            mock_stripe.create_payment_intent.return_value = {
                "id": "pi_test123",
                "client_secret": "pi_test123_secret_abc",
                "amount": Decimal("50.00"),
                "currency": "EUR",
                "status": "requires_payment_method"
            }
            
            response = client.post(
                "/api/payments/initiate",
                json={
                    "payment_method": "credit_card",
                    "amount": 50.00,
                    "currency": "EUR"
                },
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            
            # Verify metadata passed to Stripe
            call_args = mock_stripe.create_payment_intent.call_args
            metadata = call_args[1]["metadata"]
            assert metadata["email"] == test_user.email
            assert "user_id" in metadata
            assert "payment_id" in metadata
    
    def test_initiate_payment_different_currencies(self, client, auth_headers):
        """Test payment initiation with different currency codes"""
        currencies = ["EUR", "USD", "GBP"]
        
        for currency in currencies:
            with patch('app.payments.router.stripe_service') as mock_stripe:
                mock_stripe.create_payment_intent.return_value = {
                    "id": f"pi_test_{currency}",
                    "client_secret": f"pi_test_{currency}_secret",
                    "amount": Decimal("50.00"),
                    "currency": currency,
                    "status": "requires_payment_method"
                }
                
                response = client.post(
                    "/api/payments/initiate",
                    json={
                        "payment_method": "credit_card",
                        "amount": 50.00,
                        "currency": currency
                    },
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["currency"] == currency
