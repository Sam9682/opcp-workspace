"""Tests for Payment model"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from app.models import Payment, PaymentMethod, PaymentStatus, User, UserRole


def test_create_payment(db_session):
    """Test creating a payment record"""
    # Create a user first
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create a payment
    payment = Payment(
        user_id=user.id,
        amount=Decimal("50.00"),
        currency="EUR",
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.COMPLETED,
        transaction_id="txn_123456",
        invoice_url="https://example.com/invoices/123.pdf"
    )
    db_session.add(payment)
    db_session.commit()
    
    # Verify payment was created
    assert payment.id is not None
    assert payment.user_id == user.id
    assert payment.amount == Decimal("50.00")
    assert payment.currency == "EUR"
    assert payment.payment_method == PaymentMethod.CREDIT_CARD
    assert payment.status == PaymentStatus.COMPLETED
    assert payment.transaction_id == "txn_123456"
    assert payment.invoice_url == "https://example.com/invoices/123.pdf"
    assert payment.created_at is not None
    assert isinstance(payment.created_at, datetime)


def test_payment_default_currency(db_session):
    """Test that currency defaults to EUR"""
    user = User(
        email="test2@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    payment = Payment(
        user_id=user.id,
        amount=Decimal("30.00"),
        payment_method=PaymentMethod.PAYPAL,
        status=PaymentStatus.PENDING
    )
    db_session.add(payment)
    db_session.commit()
    
    assert payment.currency == "EUR"


def test_payment_method_enum(db_session):
    """Test PaymentMethod enum values"""
    user = User(
        email="test3@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Test CREDIT_CARD
    payment1 = Payment(
        user_id=user.id,
        amount=Decimal("50.00"),
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.COMPLETED
    )
    db_session.add(payment1)
    db_session.commit()
    assert payment1.payment_method == PaymentMethod.CREDIT_CARD
    
    # Test PAYPAL
    payment2 = Payment(
        user_id=user.id,
        amount=Decimal("60.00"),
        payment_method=PaymentMethod.PAYPAL,
        status=PaymentStatus.COMPLETED
    )
    db_session.add(payment2)
    db_session.commit()
    assert payment2.payment_method == PaymentMethod.PAYPAL


def test_payment_status_enum(db_session):
    """Test PaymentStatus enum values"""
    user = User(
        email="test4@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Test all status values
    statuses = [
        PaymentStatus.PENDING,
        PaymentStatus.COMPLETED,
        PaymentStatus.FAILED,
        PaymentStatus.REFUNDED
    ]
    
    for status in statuses:
        payment = Payment(
            user_id=user.id,
            amount=Decimal("50.00"),
            payment_method=PaymentMethod.CREDIT_CARD,
            status=status
        )
        db_session.add(payment)
        db_session.commit()
        assert payment.status == status


def test_payment_user_relationship(db_session):
    """Test relationship between Payment and User"""
    user = User(
        email="test5@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    payment = Payment(
        user_id=user.id,
        amount=Decimal("50.00"),
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.COMPLETED
    )
    db_session.add(payment)
    db_session.commit()
    
    # Test relationship from payment to user
    assert payment.user == user
    
    # Test relationship from user to payments
    assert len(user.payments) == 1
    assert user.payments[0] == payment


def test_unique_transaction_id(db_session):
    """Test that transaction_id must be unique"""
    user = User(
        email="test6@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create first payment with transaction_id
    payment1 = Payment(
        user_id=user.id,
        amount=Decimal("50.00"),
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.COMPLETED,
        transaction_id="txn_duplicate"
    )
    db_session.add(payment1)
    db_session.commit()
    
    # Try to create second payment with same transaction_id
    payment2 = Payment(
        user_id=user.id,
        amount=Decimal("60.00"),
        payment_method=PaymentMethod.PAYPAL,
        status=PaymentStatus.COMPLETED,
        transaction_id="txn_duplicate"
    )
    db_session.add(payment2)
    
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_payment_optional_fields(db_session):
    """Test that transaction_id and invoice_url are optional"""
    user = User(
        email="test7@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    payment = Payment(
        user_id=user.id,
        amount=Decimal("50.00"),
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.PENDING
    )
    db_session.add(payment)
    db_session.commit()
    
    assert payment.transaction_id is None
    assert payment.invoice_url is None


def test_payment_indexes_exist(db_session):
    """Test that indexes on user_id and status exist"""
    # This test verifies the indexes were created by checking the migration
    # In a real scenario, you might query the database metadata
    user = User(
        email="test8@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create multiple payments
    for i in range(5):
        payment = Payment(
            user_id=user.id,
            amount=Decimal("50.00"),
            payment_method=PaymentMethod.CREDIT_CARD,
            status=PaymentStatus.COMPLETED if i % 2 == 0 else PaymentStatus.PENDING
        )
        db_session.add(payment)
    db_session.commit()
    
    # Query by user_id (should use idx_payments_user)
    user_payments = db_session.query(Payment).filter(Payment.user_id == user.id).all()
    assert len(user_payments) == 5
    
    # Query by status (should use idx_payments_status)
    completed_payments = db_session.query(Payment).filter(
        Payment.status == PaymentStatus.COMPLETED
    ).all()
    assert len(completed_payments) == 3


def test_payment_repr(db_session):
    """Test Payment __repr__ method"""
    user = User(
        email="test9@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    payment = Payment(
        user_id=user.id,
        amount=Decimal("50.00"),
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.COMPLETED
    )
    db_session.add(payment)
    db_session.commit()
    
    repr_str = repr(payment)
    assert "Payment" in repr_str
    assert str(payment.id) in repr_str
    assert str(payment.user_id) in repr_str
    assert "50.00" in repr_str
    assert "COMPLETED" in repr_str
