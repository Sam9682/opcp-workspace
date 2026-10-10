"""Document management API endpoints
Feature: OPCP-website
Validates Requirements 5.1, 5.2, 5.3, 5.4, 5.7
"""
import logging
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Document, UserRole, AuditLog
from app.models.document import DocumentCategory, AccessLevel, classify_extension
from app.forum.dependencies import get_administrator
from app.auth.dependencies import get_current_user_optional
from app.documents.schemas import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentListResponse,
    DocumentDeleteResponse
)
from app.services.storage_service import storage_service
from app.auth.schemas import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _read_link_target(filename: str) -> Optional[str]:
    """Read the target URL from a stored ``.links`` file.

    Resolves ``filename`` to its on-disk path via
    ``storage_service.get_file_path`` and returns the first non-empty, stripped
    line of the file. Returns ``None`` when the file is missing, unreadable, or
    empty. This helper MUST NOT raise: any failure results in ``None`` so the
    document is still returned by the list endpoint, just without a
    ``target_url`` (the frontend then falls back to the download flow).

    Args:
        filename: Stored filename of the ``.links`` document.

    Returns:
        The first non-empty stripped line, or ``None`` on any failure/empty file.
    """
    try:
        file_path = storage_service.get_file_path(filename)
        if not file_path:
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    return stripped
        return None
    except Exception as e:
        logger.warning(f"Failed to read link target for {filename}: {str(e)}")
        return None


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document (admin only)",
    description="""
    Upload a document to the system.
    
    Validates Requirements 5.2, 5.6:
    - Stores document and creates metadata record
    - Validates file size (max 10MB) and mime types
    - Assigns category and access permissions
    
    Only administrators can upload documents.
    """
)
async def upload_document(
    file: Annotated[UploadFile, File(description="Document file to upload")],
    access_level: Annotated[AccessLevel, Form(description="Access level for document")],
    current_user: User = Depends(get_administrator),
    db: Session = Depends(get_db)
) -> DocumentUploadResponse:
    """Upload a document (admin only)

    Validates Requirements 2.4, 3.4, 3.5, 4.3, 5.2:
    - Administrator uploads document (category is server-assigned)
    - System derives the category from the file extension
    - System stores file and creates metadata
    - Assigns access permissions

    Args:
        file: Uploaded file
        access_level: Access level for document
        current_user: Authenticated administrator
        db: Database session

    Returns:
        DocumentUploadResponse with document details

    Raises:
        HTTPException 400: If the extension is unknown or file validation fails
        HTTPException 403: If user is not administrator
    """
    logger.info(
        f"Document upload initiated by user {current_user.id}: "
        f"filename={file.filename}, access_level={access_level}"
    )

    # Read file content
    try:
        file_content = await file.read()
        file_size = len(file_content)
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="FILE_READ_ERROR",
                message="Failed to read uploaded file",
                details={"error": str(e)}
            )
        )

    # Classify the category from the file extension (server is the sole
    # authority on category). Reject unmapped extensions without persisting
    # anything (Requirement 2.4).
    category = classify_extension(file.filename or "")
    if category is None:
        logger.warning(
            f"Rejected upload with unmapped extension: {file.filename}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_FILE_TYPE",
                message="File extension is not a supported category",
                details={"filename": file.filename}
            )
        )

    # Validate file (size + extension allow-list, Requirement 4.3)
    is_valid, error_message = storage_service.validate_file(
        file_size=file_size,
        filename=file.filename or ""
    )

    if not is_valid:
        logger.warning(
            f"File validation failed for {file.filename}: {error_message}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_FILE",
                message=error_message,
                details={
                    "filename": file.filename,
                    "size": file_size,
                    "mime_type": file.content_type
                }
            )
        )
    
    # Save file to storage
    try:
        unique_filename, file_path = storage_service.save_file(
            file_content=file_content,
            original_filename=file.filename
        )
    except Exception as e:
        logger.error(f"Failed to save file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="FILE_SAVE_ERROR",
                message="Failed to save file to storage",
                details={"error": str(e)}
            )
        )
    
    # Create document record in database
    try:
        document = Document(
            filename=unique_filename,
            original_name=file.filename,
            mime_type=file.content_type or "application/octet-stream",
            size=file_size,
            category=category,
            access_level=access_level,
            uploaded_by=current_user.id,
            download_count=0
        )
        
        db.add(document)
        db.commit()
        db.refresh(document)
        
        logger.info(
            f"Document created successfully: id={document.id}, "
            f"filename={unique_filename}"
        )
        
        return DocumentUploadResponse(
            success=True,
            message="Document uploaded successfully",
            document=DocumentResponse.model_validate(document)
        )
    
    except Exception as e:
        db.rollback()
        # Clean up uploaded file if database operation fails
        storage_service.delete_file(unique_filename)
        logger.error(
            f"Failed to create document record: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="DATABASE_ERROR",
                message="Failed to create document record",
                details={"error": str(e)}
            )
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents with access control",
    description="""
    List documents based on user role and access level.

    Validates Requirements 5.1, 5.4:
    - Public documents: accessible to everyone (including unauthenticated users)
    - Members documents: accessible to authenticated members and admins
    - Administrators documents: accessible only to admins
    - Supports filtering by category

    Access control:
    - Unauthenticated users: only public documents
    - Members: public and members documents
    - Administrators: all documents
    """
)
async def list_documents(
    category: Optional[DocumentCategory] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> DocumentListResponse:
    """List documents with role-based access control

    Validates Requirements 5.1, 5.4:
    - Filter documents by user's role and access level
    - Support filtering by category
    - Return document metadata

    Args:
        category: Optional category filter
        current_user: Optional authenticated user
        db: Database session

    Returns:
        DocumentListResponse with list of accessible documents
    """
    logger.info(
        f"Document list requested by user {current_user.id if current_user else 'anonymous'}, "
        f"category={category}"
    )

    # Build base query
    query = db.query(Document)

    # Apply category filter if provided
    if category:
        query = query.filter(Document.category == category)

    # Apply access control based on user role
    if not current_user:
        # Unauthenticated users: only public documents
        query = query.filter(Document.access_level == AccessLevel.PUBLIC)
        logger.debug("Filtering for unauthenticated user: public documents only")
    elif current_user.role == UserRole.ADMINISTRATOR:
        # Administrators: all documents (no filter needed)
        logger.debug("Administrator access: all documents")
    elif current_user.role in [UserRole.MEMBER, UserRole.VISITOR]:
        # Members and visitors: public and members documents
        query = query.filter(
            Document.access_level.in_([AccessLevel.PUBLIC, AccessLevel.MEMBERS])
        )
        logger.debug(f"Member/Visitor access: public and members documents")

    # Execute query and order by created_at descending (newest first)
    documents = query.order_by(Document.created_at.desc()).all()

    logger.info(f"Returning {len(documents)} documents")

    # Assemble responses. For links documents, expose the target URL read from
    # the stored .links file so the frontend can render an anchor without hitting
    # the download endpoint. target_url stays None for every other category and
    # for links whose file is missing/unreadable/empty (graceful fallback).
    responses = []
    for doc in documents:
        response = DocumentResponse.model_validate(doc)
        if doc.category == DocumentCategory.LINKS:
            response.target_url = _read_link_target(doc.filename)
        responses.append(response)

    return DocumentListResponse(
        documents=responses,
        total=len(documents)
    )



@router.get(
    "/{document_id}/download",
    summary="Download a document",
    description="""
    Download a document file with access control.

    Validates Requirements 5.3:
    - Checks user has access to document based on access level
    - Increments download count
    - Returns file with appropriate content-type

    Access control:
    - Public documents: accessible to everyone
    - Members documents: accessible to authenticated members and admins
    - Administrators documents: accessible only to admins
    """
)
async def download_document(
    document_id: UUID,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Download a document with access control

    Validates Requirements 5.3:
    - Verify user has permission to access document
    - Retrieve file from storage
    - Increment download count
    - Return file as downloadable response

    Args:
        document_id: UUID of document to download
        current_user: Optional authenticated user
        db: Database session

    Returns:
        FileResponse with document file

    Raises:
        HTTPException 404: If document not found
        HTTPException 403: If user lacks permission to access document
        HTTPException 404: If file not found in storage
    """
    logger.info(
        f"Document download requested: document_id={document_id}, "
        f"user={current_user.id if current_user else 'anonymous'}"
    )

    # Retrieve document from database
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        logger.warning(f"Document not found: {document_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code="DOCUMENT_NOT_FOUND",
                message="Document not found",
                details={"document_id": str(document_id)}
            )
        )

    # Apply access control based on user role and document access level
    if document.access_level == AccessLevel.ADMINISTRATORS:
        # Only administrators can access admin documents
        if not current_user or current_user.role != UserRole.ADMINISTRATOR:
            logger.warning(
                f"Access denied to admin document {document_id} for user "
                f"{current_user.id if current_user else 'anonymous'}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorResponse.create(
                    code="ACCESS_DENIED",
                    message="You do not have permission to access this document",
                    details={"document_id": str(document_id)}
                )
            )
    elif document.access_level == AccessLevel.MEMBERS:
        # Members and administrators can access member documents
        if not current_user:
            logger.warning(
                f"Access denied to members document {document_id} for unauthenticated user"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorResponse.create(
                    code="ACCESS_DENIED",
                    message="You must be logged in to access this document",
                    details={"document_id": str(document_id)}
                )
            )
    # Public documents are accessible to everyone (no check needed)

    # Retrieve file from storage
    file_path = storage_service.get_file_path(document.filename)

    if not file_path:
        logger.error(f"File not found in storage: {document.filename}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code="FILE_NOT_FOUND",
                message="Document file not found in storage",
                details={"document_id": str(document_id), "filename": document.filename}
            )
        )

    # Increment download count and log download in audit log (Requirement 5.3)
    try:
        document.download_count += 1
        
        # Log download in audit log
        audit_entry = AuditLog(
            admin_id=current_user.id if current_user else None,
            action="DOCUMENT_DOWNLOAD",
            target_type="document",
            target_id=document.id,
            details={
                "document_id": str(document.id),
                "document_name": document.original_name,
                "category": document.category.value,
                "access_level": document.access_level.value,
                "user_role": current_user.role.value if current_user else "anonymous"
            }
        )
        db.add(audit_entry)
        
        db.commit()
        logger.info(
            f"Download count incremented and logged for document {document_id}: "
            f"count={document.download_count}, user={current_user.id if current_user else 'anonymous'}"
        )
    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to increment download count or log audit for document {document_id}: {str(e)}",
            exc_info=True
        )
        # Continue with download even if count increment or audit logging fails

    # Return file as downloadable response
    from fastapi.responses import FileResponse

    logger.info(f"Serving file download: {document.original_name}")

    return FileResponse(
        path=str(file_path),
        media_type=document.mime_type,
        filename=document.original_name,
        headers={
            "Content-Disposition": f'attachment; filename="{document.original_name}"'
        }
    )



@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    summary="Delete a document (admin only)",
    description="""
    Delete a document from the system.
    
    Validates Requirements 5.7:
    - Removes file from storage
    - Deletes document metadata record
    - Logs deletion in audit log
    
    Only administrators can delete documents.
    """
)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_administrator),
    db: Session = Depends(get_db)
) -> DocumentDeleteResponse:
    """Delete a document (admin only)
    
    Validates Requirements 5.7:
    - Administrator deletes document
    - System removes file from storage
    - System removes document metadata record
    
    Args:
        document_id: UUID of document to delete
        current_user: Authenticated administrator
        db: Database session
    
    Returns:
        DocumentDeleteResponse with success status
    
    Raises:
        HTTPException 404: If document not found
        HTTPException 403: If user is not administrator
    """
    logger.info(
        f"Document deletion requested by user {current_user.id}: "
        f"document_id={document_id}"
    )
    
    # Retrieve document from database
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        logger.warning(f"Document not found for deletion: {document_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code="DOCUMENT_NOT_FOUND",
                message="Document not found",
                details={"document_id": str(document_id)}
            )
        )
    
    # Store document info for logging before deletion
    document_info = {
        "document_id": str(document.id),
        "filename": document.filename,
        "original_name": document.original_name,
        "category": document.category.value,
        "access_level": document.access_level.value
    }
    
    # Delete file from storage
    file_deleted = storage_service.delete_file(document.filename)
    
    if not file_deleted:
        logger.warning(
            f"File not found in storage during deletion: {document.filename}, "
            f"continuing with database record deletion"
        )
    
    # Delete document record from database
    try:
        db.delete(document)
        
        # Log deletion in audit log
        audit_entry = AuditLog(
            admin_id=current_user.id,
            action="DOCUMENT_DELETE",
            target_type="document",
            target_id=document_id,
            details=document_info
        )
        db.add(audit_entry)
        
        db.commit()
        
        logger.info(
            f"Document deleted successfully: id={document_id}, "
            f"filename={document_info['original_name']}"
        )
        
        return DocumentDeleteResponse(
            success=True,
            message="Document deleted successfully",
            document_id=document_id
        )
    
    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to delete document record: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="DATABASE_ERROR",
                message="Failed to delete document record",
                details={"error": str(e)}
            )
        )
