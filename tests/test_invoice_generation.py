"""Unit tests for invoice generation
Feature: OPCP-website
Validates Requirements 4.3, 4.4
"""
import os
import pytest
import tempfile
import shutil
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.services.invoice_generator import InvoiceGenerator, invoice_generator
from app.services.email_service import EmailService, email_service


class TestInvoiceGenerator:
    """Test invoice generation functionality"""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory for tests"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def generator(self, temp_storage_dir):
        """Create invoice generator with temporary storage"""
        return InvoiceGenerator(storage_dir=temp_storage_dir)
    
    def test_generate_invoice_number(self, generator):
        """Test invoice number generation format"""
        payment_id = "12345678-1234-1234-1234-123456789abc"
        created_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        
        invoice_number = generator.generate_invoice_number(payment_id, created_at)
        
        # Should be in format INV-YYYY-XXXXXXXX
        assert invoice_number.startswith("INV-2024-")
        assert len(invoice_number) == 17  # INV-YYYY-XXXXXXXX
        assert invoice_number[9:] == "12345678"  # First 8 chars of payment ID (no dashes)
    
    def test_generate_invoice_creates_pdf(self, generator, temp_storage_dir):
        """Test that invoice generation creates a PDF file"""
        payment_id = "12345678-1234-1234-1234-123456789abc"
        created_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        
        filepath = generator.generate_invoice(
            payment_id=payment_id,
            user_email="test@example.com",
            user_name="John Doe",
            amount=Decimal("50.00"),
            currency="EUR",
            payment_method="credit_card",
            transaction_id="pi_test123",
            created_at=created_at
        )
        
        # Check file was created
        assert os.path.exists(filepath)
        assert filepath.endswith(".pdf")
        
        # Check file is in correct directory
        assert filepath.startswith(temp_storage_dir)
        
        # Check file has content
        assert os.path.getsize(filepath) > 0
    
    def test_generate_invoice_with_different_currencies(self, generator):
        """Test invoice generation with different currencies"""
        payment_id = "12345678-1234-1234-1234-123456789abc"
        created_at = datetime.now(timezone.utc)
        
        for currency in ["EUR", "USD", "GBP"]:
            filepath = generator.generate_invoice(
                payment_id=payment_id,
                user_email="test@example.com",
                user_name="John Doe",
                amount=Decimal("50.00"),
                currency=currency,
                payment_method="credit_card",
                transaction_id="pi_test123",
                created_at=created_at
            )
            
            assert os.path.exists(filepath)
            assert os.path.getsize(filepath) > 0
    
    def test_generate_invoice_with_different_payment_methods(self, generator):
        """Test invoice generation with different payment methods"""
        payment_id = "12345678-1234-1234-1234-123456789abc"
        created_at = datetime.now(timezone.utc)
        
        for payment_method in ["credit_card", "paypal"]:
            filepath = generator.generate_invoice(
                payment_id=payment_id,
                user_email="test@example.com",
                user_name="John Doe",
                amount=Decimal("50.00"),
                currency="EUR",
                payment_method=payment_method,
                transaction_id="test_transaction_123",
                created_at=created_at
            )
            
            assert os.path.exists(filepath)
            assert os.path.getsize(filepath) > 0
    
    def test_generate_invoice_with_large_amount(self, generator):
        """Test invoice generation with large payment amount"""
        payment_id = "12345678-1234-1234-1234-123456789abc"
        created_at = datetime.now(timezone.utc)
        
        filepath = generator.generate_invoice(
            payment_id=payment_id,
            user_email="test@example.com",
            user_name="John Doe",
            amount=Decimal("9999.99"),
            currency="EUR",
            payment_method="credit_card",
            transaction_id="pi_test123",
            created_at=created_at
        )
        
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 0
    
    def test_generate_invoice_with_special_characters_in_name(self, generator):
        """Test invoice generation with special characters in user name"""
        payment_id = "12345678-1234-1234-1234-123456789abc"
        created_at = datetime.now(timezone.utc)
        
        filepath = generator.generate_invoice(
            payment_id=payment_id,
            user_email="test@example.com",
            user_name="Jean-François Müller",
            amount=Decimal("50.00"),
            currency="EUR",
            payment_method="credit_card",
            transaction_id="pi_test123",
            created_at=created_at
        )
        
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 0
    
    def test_generate_invoice_creates_storage_directory(self):
        """Test that invoice generator creates storage directory if it doesn't exist"""
        temp_dir = tempfile.mkdtemp()
        storage_dir = os.path.join(temp_dir, "invoices", "nested")
        
        try:
            generator = InvoiceGenerator(storage_dir=storage_dir)
            
            # Directory should be created
            assert os.path.exists(storage_dir)
            assert os.path.isdir(storage_dir)
        finally:
            shutil.rmtree(temp_dir)
    
    def test_invoice_number_uniqueness_by_year(self, generator):
        """Test that invoice numbers include year for uniqueness"""
        payment_id = "12345678-1234-1234-1234-123456789abc"
        
        created_2023 = datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        created_2024 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        
        invoice_2023 = generator.generate_invoice_number(payment_id, created_2023)
        invoice_2024 = generator.generate_invoice_number(payment_id, created_2024)
        
        assert "2023" in invoice_2023
        assert "2024" in invoice_2024
        assert invoice_2023 != invoice_2024


class TestEmailService:
    """Test email service functionality"""
    
    @pytest.fixture
    def mock_smtp(self):
        """Mock SMTP server"""
        with patch('app.services.email_service.smtplib.SMTP') as mock:
            smtp_instance = MagicMock()
            mock.return_value.__enter__.return_value = smtp_instance
            yield smtp_instance
    
    def test_send_email_basic(self, mock_smtp):
        """Test basic email sending"""
        service = EmailService()
        
        result = service.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            body_text="Test body"
        )
        
        assert result is True
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once()
        mock_smtp.send_message.assert_called_once()
    
    def test_send_email_with_html(self, mock_smtp):
        """Test email sending with HTML body"""
        service = EmailService()
        
        result = service.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            body_text="Test body",
            body_html="<html><body>Test body</body></html>"
        )
        
        assert result is True
        mock_smtp.send_message.assert_called_once()
    
    def test_send_email_with_attachment(self, mock_smtp):
        """Test email sending with attachment"""
        service = EmailService()
        
        # Create temporary PDF file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
            f.write("Test PDF content")
            temp_file = f.name
        
        try:
            result = service.send_email(
                to_email="test@example.com",
                subject="Test Subject",
                body_text="Test body",
                attachments=[temp_file]
            )
            
            assert result is True
            mock_smtp.send_message.assert_called_once()
        finally:
            os.unlink(temp_file)
    
    def test_send_email_with_missing_attachment(self, mock_smtp):
        """Test email sending with missing attachment file"""
        service = EmailService()
        
        result = service.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            body_text="Test body",
            attachments=["/nonexistent/file.pdf"]
        )
        
        # Should still succeed but log warning
        assert result is True
        mock_smtp.send_message.assert_called_once()
    
    def test_send_email_smtp_failure(self):
        """Test email sending when SMTP fails"""
        with patch('app.services.email_service.smtplib.SMTP') as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP connection failed")
            
            service = EmailService()
            result = service.send_email(
                to_email="test@example.com",
                subject="Test Subject",
                body_text="Test body"
            )
            
            assert result is False
    
    def test_send_invoice_email(self, mock_smtp):
        """Test sending invoice email with all details"""
        service = EmailService()
        
        # Create temporary PDF file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
            f.write("Test invoice PDF")
            temp_file = f.name
        
        try:
            result = service.send_invoice_email(
                to_email="test@example.com",
                user_name="John Doe",
                invoice_number="INV-2024-12345678",
                amount=50.00,
                currency="EUR",
                invoice_path=temp_file
            )
            
            assert result is True
            mock_smtp.send_message.assert_called_once()
            
            # Verify email was sent with correct details
            call_args = mock_smtp.send_message.call_args
            message = call_args[0][0]
            
            assert message['To'] == "test@example.com"
            assert "INV-2024-12345678" in message['Subject']
        finally:
            os.unlink(temp_file)
    
    def test_send_invoice_email_contains_required_info(self, mock_smtp):
        """Test that invoice email contains all required information"""
        service = EmailService()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
            f.write("Test invoice PDF")
            temp_file = f.name
        
        try:
            result = service.send_invoice_email(
                to_email="test@example.com",
                user_name="John Doe",
                invoice_number="INV-2024-12345678",
                amount=50.00,
                currency="EUR",
                invoice_path=temp_file
            )
            
            assert result is True
            
            # Get the message that was sent
            call_args = mock_smtp.send_message.call_args
            message = call_args[0][0]
            
            # Check subject contains invoice number
            assert "INV-2024-12345678" in message['Subject']
            assert message['To'] == "test@example.com"
            
            # Verify message has both text and HTML parts
            assert message.is_multipart()
        finally:
            os.unlink(temp_file)


class TestInvoiceIntegration:
    """Integration tests for invoice generation and email sending"""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory for tests"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_smtp(self):
        """Mock SMTP server"""
        with patch('app.services.email_service.smtplib.SMTP') as mock:
            smtp_instance = MagicMock()
            mock.return_value.__enter__.return_value = smtp_instance
            yield smtp_instance
    
    def test_generate_invoice_and_send_email(self, temp_storage_dir, mock_smtp):
        """Test complete flow: generate invoice and send email"""
        # Generate invoice
        generator = InvoiceGenerator(storage_dir=temp_storage_dir)
        payment_id = "12345678-1234-1234-1234-123456789abc"
        created_at = datetime.now(timezone.utc)
        
        invoice_path = generator.generate_invoice(
            payment_id=payment_id,
            user_email="test@example.com",
            user_name="John Doe",
            amount=Decimal("50.00"),
            currency="EUR",
            payment_method="credit_card",
            transaction_id="pi_test123",
            created_at=created_at
        )
        
        # Verify invoice was created
        assert os.path.exists(invoice_path)
        
        # Send email with invoice
        service = EmailService()
        invoice_number = generator.generate_invoice_number(payment_id, created_at)
        
        result = service.send_invoice_email(
            to_email="test@example.com",
            user_name="John Doe",
            invoice_number=invoice_number,
            amount=50.00,
            currency="EUR",
            invoice_path=invoice_path
        )
        
        # Verify email was sent
        assert result is True
        mock_smtp.send_message.assert_called_once()
    
    def test_multiple_invoices_different_payments(self, temp_storage_dir):
        """Test generating multiple invoices for different payments"""
        generator = InvoiceGenerator(storage_dir=temp_storage_dir)
        
        payment_ids = [
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "33333333-3333-3333-3333-333333333333"
        ]
        
        created_at = datetime.now(timezone.utc)
        invoice_paths = []
        
        for payment_id in payment_ids:
            invoice_path = generator.generate_invoice(
                payment_id=payment_id,
                user_email="test@example.com",
                user_name="John Doe",
                amount=Decimal("50.00"),
                currency="EUR",
                payment_method="credit_card",
                transaction_id=f"pi_test_{payment_id[:8]}",
                created_at=created_at
            )
            invoice_paths.append(invoice_path)
        
        # Verify all invoices were created
        for invoice_path in invoice_paths:
            assert os.path.exists(invoice_path)
        
        # Verify all invoices have different filenames
        filenames = [os.path.basename(path) for path in invoice_paths]
        assert len(filenames) == len(set(filenames))  # All unique
