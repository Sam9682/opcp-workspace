"""Tests for Document model"""
import pytest
from datetime import datetime, timezone
from app.models import Document, DocumentCategory, AccessLevel, User, UserRole
from app.database import Base, engine


@pytest.fixture(scope="function")
def setup_database():
    """Setup test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_document_model_creation(db_session, test_user):
    """Test creating a Document model instance
    
    Validates Requirements 5.1, 5.2, 5.4:
    - Document model stores all required fields
    - Document has category and access level
    - Document tracks uploader and download count
    """
    # Create a document
    document = Document(
        filename="test_file_123.pdf",
        original_name="Test Document.pdf",
        mime_type="application/pdf",
        size=1024000,
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.MEMBERS,
        uploaded_by=test_user.id,
        download_count=0
    )
    
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    # Verify document was created
    assert document.id is not None
    assert document.filename == "test_file_123.pdf"
    assert document.original_name == "Test Document.pdf"
    assert document.mime_type == "application/pdf"
    assert document.size == 1024000
    assert document.category == DocumentCategory.DOCUMENTS
    assert document.access_level == AccessLevel.MEMBERS
    assert document.uploaded_by == test_user.id
    assert document.download_count == 0
    assert document.created_at is not None
    assert document.updated_at is not None
    assert isinstance(document.created_at, datetime)
    assert isinstance(document.updated_at, datetime)


def test_document_categories(db_session, test_user):
    """Test all document categories
    
    Validates Requirement 1.1:
    - Documents can be categorized as documents, scripts, or links
    """
    categories = [
        DocumentCategory.DOCUMENTS,
        DocumentCategory.SCRIPTS,
        DocumentCategory.LINKS,
    ]
    
    for category in categories:
        document = Document(
            filename=f"test_{category.value}.pdf",
            original_name=f"Test {category.value}.pdf",
            mime_type="application/pdf",
            size=1024,
            category=category,
            access_level=AccessLevel.MEMBERS,
            uploaded_by=test_user.id,
            download_count=0
        )
        db_session.add(document)
    
    db_session.commit()
    
    # Verify all categories were created
    documents = db_session.query(Document).all()
    assert len(documents) == 3
    assert set(doc.category for doc in documents) == set(categories)


def test_document_access_levels(db_session, test_user):
    """Test all access levels
    
    Validates Requirement 5.1:
    - Documents have access levels (public, members, administrators)
    """
    access_levels = [
        AccessLevel.PUBLIC,
        AccessLevel.MEMBERS,
        AccessLevel.ADMINISTRATORS
    ]
    
    for access_level in access_levels:
        document = Document(
            filename=f"test_{access_level.value}.pdf",
            original_name=f"Test {access_level.value}.pdf",
            mime_type="application/pdf",
            size=1024,
            category=DocumentCategory.DOCUMENTS,
            access_level=access_level,
            uploaded_by=test_user.id,
            download_count=0
        )
        db_session.add(document)
    
    db_session.commit()
    
    # Verify all access levels were created
    documents = db_session.query(Document).all()
    assert len(documents) == 3
    assert set(doc.access_level for doc in documents) == set(access_levels)


def test_document_uploader_relationship(db_session, test_user):
    """Test relationship between Document and User
    
    Validates Requirement 5.2:
    - Document tracks who uploaded it
    """
    document = Document(
        filename="test.pdf",
        original_name="Test.pdf",
        mime_type="application/pdf",
        size=1024,
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.MEMBERS,
        uploaded_by=test_user.id,
        download_count=0
    )
    
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    # Verify relationship
    assert document.uploader is not None
    assert document.uploader.id == test_user.id
    assert document.uploader.email == test_user.email


def test_document_download_count_increment(db_session, test_user):
    """Test incrementing download count
    
    Validates Requirement 5.3:
    - Document tracks download count
    """
    document = Document(
        filename="test.pdf",
        original_name="Test.pdf",
        mime_type="application/pdf",
        size=1024,
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.MEMBERS,
        uploaded_by=test_user.id,
        download_count=0
    )
    
    db_session.add(document)
    db_session.commit()
    
    # Increment download count
    document.download_count += 1
    db_session.commit()
    db_session.refresh(document)
    
    assert document.download_count == 1
    
    # Increment again
    document.download_count += 1
    db_session.commit()
    db_session.refresh(document)
    
    assert document.download_count == 2


def test_document_query_by_category(db_session, test_user):
    """Test querying documents by category
    
    Validates Requirement 5.4:
    - Documents can be filtered by category
    """
    # Create documents with different categories
    doc1 = Document(
        filename="handbook.pdf",
        original_name="Handbook.pdf",
        mime_type="application/pdf",
        size=1024,
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.MEMBERS,
        uploaded_by=test_user.id,
        download_count=0
    )
    doc2 = Document(
        filename="deploy.sh",
        original_name="Deploy.sh",
        mime_type="application/x-sh",
        size=1024,
        category=DocumentCategory.SCRIPTS,
        access_level=AccessLevel.MEMBERS,
        uploaded_by=test_user.id,
        download_count=0
    )
    
    db_session.add_all([doc1, doc2])
    db_session.commit()
    
    # Query by category
    documents = db_session.query(Document).filter(
        Document.category == DocumentCategory.DOCUMENTS
    ).all()
    
    assert len(documents) == 1
    assert documents[0].filename == "handbook.pdf"


def test_document_query_by_access_level(db_session, test_user):
    """Test querying documents by access level
    
    Validates Requirement 5.1:
    - Documents can be filtered by access level
    """
    # Create documents with different access levels
    doc1 = Document(
        filename="public.pdf",
        original_name="Public.pdf",
        mime_type="application/pdf",
        size=1024,
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.PUBLIC,
        uploaded_by=test_user.id,
        download_count=0
    )
    doc2 = Document(
        filename="members.pdf",
        original_name="Members.pdf",
        mime_type="application/pdf",
        size=1024,
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.MEMBERS,
        uploaded_by=test_user.id,
        download_count=0
    )
    doc3 = Document(
        filename="admin.pdf",
        original_name="Admin.pdf",
        mime_type="application/pdf",
        size=1024,
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.ADMINISTRATORS,
        uploaded_by=test_user.id,
        download_count=0
    )
    
    db_session.add_all([doc1, doc2, doc3])
    db_session.commit()
    
    # Query by access level
    public_docs = db_session.query(Document).filter(
        Document.access_level == AccessLevel.PUBLIC
    ).all()
    
    assert len(public_docs) == 1
    assert public_docs[0].filename == "public.pdf"
    
    # Query for member-accessible documents (public + members)
    member_accessible = db_session.query(Document).filter(
        Document.access_level.in_([AccessLevel.PUBLIC, AccessLevel.MEMBERS])
    ).all()
    
    assert len(member_accessible) == 2
