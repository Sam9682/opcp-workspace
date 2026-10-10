"""Authentication API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models import User, UserRole, AuditLog, TokenBlacklist
from app.auth.schemas import (
    RegistrationRequest, 
    RegistrationResponse, 
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    EmailVerificationRequest,
    EmailVerificationResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    ChangePasswordRequest,
    TwoFactorStatusResponse,
    TotpSetupResponse,
    TotpConfirmRequest,
    Login2FARequest,
    Login2FAChallengeResponse,
    ErrorResponse
)
from app.auth.password import hash_password, verify_password
from app.auth import totp
from app.auth.token import create_access_token, verify_token
from app.auth.rate_limiter import login_rate_limiter
from app.auth.dependencies import get_current_user, get_token_from_request
from app.services.email import email_service
from app.logging_config import logger
from app.middleware.rate_limit import limiter
from datetime import timedelta, datetime, timezone
from typing import Optional, Union, NoReturn
from uuid import UUID
import hashlib
import secrets

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# Membership statuses that must be denied authentication.
BLOCKED_MEMBERSHIP_STATUSES: frozenset[str] = frozenset({"expired", "suspended"})


def _is_membership_blocked(membership_status: str | None) -> bool:
    """Return True iff the stored membership status denies authentication.

    Reads the stored value only (Requirements 2.1/2.2); does NOT consult
    membership_expires_at. null and any value outside the blocked set are
    allowed (Requirement 1.5).
    """
    return membership_status in BLOCKED_MEMBERSHIP_STATUSES


def _deny_blocked_login(
    db: Session,
    user: User,
    request: Request,
    audit_action: str,  # "LOGIN_FAILED" or "LOGIN_2FA_FAILED"
) -> NoReturn:
    """Record a blocked-membership denial and raise the generic 401.

    - Persists AuditLog(action=audit_action) for the user (Requirements 4.1/4.2).
    - Raises the existing generic INVALID_CREDENTIALS 401 so account state is not
      disclosed (Requirements 3.1/3.2/3.3).
    """
    audit_log = AuditLog(
        admin_id=user.id,
        action=audit_action,
        target_type="user",
        target_id=user.id,
        details={
            "email": user.email,
            "reason": "membership_blocked",
            **_client_info(request),
        },
    )
    db.add(audit_log)
    db.commit()

    logger.warning(
        f"Login blocked for user with membership_status "
        f"'{user.membership_status}': {user.email} (ID: {user.id})"
    )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ErrorResponse.create(
            code="INVALID_CREDENTIALS",
            message="Invalid email or password",
            details={},
        ),
    )


@router.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "Email already registered"},
        400: {"description": "Invalid registration data"}
    }
)
@limiter.limit("10/hour")  # Limit registration to 10 attempts per hour per IP
async def register(
    request: Request,
    registration_data: RegistrationRequest,
    db: Session = Depends(get_db)
) -> RegistrationResponse:
    """Register a new user account.
    
    Validates Requirements 2.1, 2.2, 2.7:
    - Creates new member account with valid registration data
    - Rejects duplicate email addresses
    - Enforces password complexity requirements
    - Sends email verification
    
    Args:
        registration_data: User registration information
        db: Database session
        
    Returns:
        RegistrationResponse with user details and success message
        
    Raises:
        HTTPException 409: If email is already registered
        HTTPException 400: If validation fails
    """
    try:
        # Check for duplicate email (Requirement 2.2)
        existing_user = db.query(User).filter(User.email == registration_data.email).first()
        if existing_user:
            logger.warning(f"Registration attempt with duplicate email: {registration_data.email}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists"
            )
        
        # Hash password (Requirement 9.1)
        password_hash = hash_password(registration_data.password)
        
        # Create user record (Requirement 2.1)
        new_user = User(
            email=registration_data.email,
            password_hash=password_hash,
            first_name=registration_data.first_name,
            last_name=registration_data.last_name,
            role=UserRole.MEMBER,
            is_email_verified=False  # Requirement 2.6
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"New user registered: {new_user.email} (ID: {new_user.id})")
        
        # Generate verification token (Requirement 2.6)
        verification_token = create_access_token(
            data={"sub": str(new_user.id), "type": "email_verification"},
            expires_delta=timedelta(hours=24)  # Token valid for 24 hours
        )
        
        # Send verification email (Requirement 2.6)
        email_sent = email_service.send_verification_email(
            to_email=new_user.email,
            verification_token=verification_token,
            user_name=new_user.first_name
        )
        
        if not email_sent:
            logger.warning(f"Failed to send verification email to {new_user.email}")
            # Don't fail registration if email fails - user can request resend
        
        # Return success response
        return RegistrationResponse(
            id=str(new_user.id),
            email=new_user.email,
            first_name=new_user.first_name,
            last_name=new_user.last_name
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except IntegrityError as e:
        # Handle database constraint violations
        db.rollback()
        logger.error(f"Database integrity error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists"
        )
    except ValueError as e:
        # Handle validation errors (e.g., password too long for bcrypt)
        logger.error(f"Validation error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Handle unexpected errors
        db.rollback()
        logger.error(f"Unexpected error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during registration"
        )


def _hash_2fa_code(code: str) -> str:
    """Return the SHA-256 hex digest of a 2FA verification code.

    Used to embed a hash of the emailed code in the short-lived challenge
    token (email 2FA) and to compare the submitted code in ``/login/2fa``
    without persisting the code server-side.
    """
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def _client_info(request: Request) -> dict:
    """Extract client connection metadata (IP address and user-agent).

    Used to enrich connection audit-log entries (login/logout) so the
    admin configuration view can show where and with what a user connected.
    Honors the ``X-Forwarded-For`` header when the app sits behind a proxy.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First entry in the list is the original client IP.
        ip_address = forwarded.split(",")[0].strip()
    else:
        ip_address = request.client.host if request.client else None
    return {
        "ip_address": ip_address,
        "user_agent": request.headers.get("user-agent"),
    }


@router.post(
    "/login",
    response_model=None,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Session token or 2FA challenge"},
        401: {"description": "Invalid credentials or email not verified"},
        429: {"description": "Too many login attempts"},
        400: {"description": "Invalid login data"}
    }
)
@limiter.limit("20/hour")  # Additional IP-based rate limiting (20 attempts per hour)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
) -> Union[LoginResponse, Login2FAChallengeResponse]:
    """Authenticate user and generate JWT token.
    
    Validates Requirements 2.3, 2.4, 2.6, 9.6:
    - Authenticates member with valid credentials
    - Rejects invalid credentials
    - Checks email verification status
    - Logs authentication attempts
    - Implements rate limiting (5 attempts per 15 minutes)
    
    Args:
        login_data: User login credentials
        db: Database session
        
    Returns:
        LoginResponse with JWT token and user details
        
    Raises:
        HTTPException 401: If credentials are invalid or email not verified
        HTTPException 429: If rate limit exceeded
        HTTPException 400: If validation fails
    """
    try:
        # Check rate limiting (Requirement 9.6)
        is_limited, remaining = login_rate_limiter.is_rate_limited(login_data.email)
        if is_limited:
            logger.warning(f"Rate limit exceeded for login attempt: {login_data.email}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=ErrorResponse.create(
                    code="RATE_LIMIT_EXCEEDED",
                    message="Too many login attempts. Please try again in 15 minutes.",
                    details={"email": login_data.email}
                )
            )
        
        # Find user by email
        user = db.query(User).filter(User.email == login_data.email).first()
        
        # Verify credentials (Requirement 2.3, 2.4)
        if not user or not verify_password(login_data.password, user.password_hash):
            # Record failed attempt
            login_rate_limiter.record_attempt(login_data.email)
            
            # Log failed authentication attempt (Requirement 9.6)
            audit_log = AuditLog(
                admin_id=user.id if user else None,
                action="LOGIN_FAILED",
                target_type="user",
                target_id=user.id if user else None,
                details={
                    "email": login_data.email,
                    "reason": "invalid_credentials",
                    "remaining_attempts": remaining - 1,
                    **_client_info(request)
                }
            )
            db.add(audit_log)
            db.commit()
            
            logger.warning(f"Failed login attempt for: {login_data.email}")
            
            # Return generic error message (don't reveal if email exists)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorResponse.create(
                    code="INVALID_CREDENTIALS",
                    message="Invalid email or password",
                    details={}
                )
            )
        
        # Check email verification status (Requirement 2.6)
        if not user.is_email_verified:
            # Record failed attempt
            login_rate_limiter.record_attempt(login_data.email)
            
            # Log failed authentication attempt
            audit_log = AuditLog(
                admin_id=user.id,
                action="LOGIN_FAILED",
                target_type="user",
                target_id=user.id,
                details={
                    "email": login_data.email,
                    "reason": "email_not_verified",
                    **_client_info(request)
                }
            )
            db.add(audit_log)
            db.commit()
            
            logger.warning(f"Login attempt with unverified email: {login_data.email}")
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorResponse.create(
                    code="EMAIL_NOT_VERIFIED",
                    message="Please verify your email address before logging in",
                    details={"email": login_data.email}
                )
            )

        # Deny expired/suspended memberships before issuing any token or challenge.
        if _is_membership_blocked(user.membership_status):
            _deny_blocked_login(db, user, request, "LOGIN_FAILED")

        # Primary credentials validated. If the user has any 2FA method
        # enabled, do NOT issue a session token yet — return a short-lived
        # challenge instead (Requirements 7.1, 7.2). Backward compatible:
        # users with no 2FA fall through to the unchanged token path (7.4).
        methods: list[str] = []
        if user.totp_enabled:
            methods.append("totp")
        if user.email_2fa_enabled:
            methods.append("email")

        if methods:
            challenge_payload = {
                "sub": str(user.id),
                "type": "2fa_challenge",
                "methods": methods,
            }

            # For the email method, generate a 6-digit code, email it, and
            # embed only its hash in the challenge token (stateless second step).
            if "email" in methods:
                code = f"{secrets.randbelow(1_000_000):06d}"
                challenge_payload["code_hash"] = _hash_2fa_code(code)
                email_sent = email_service.send_2fa_code_email(
                    user.email, code, user.first_name
                )
                if not email_sent:
                    logger.warning(f"Failed to send 2FA code email to {user.email}")

            challenge_token = create_access_token(
                data=challenge_payload,
                expires_delta=timedelta(minutes=5),
            )

            logger.info(
                f"2FA challenge issued for user: {user.email} "
                f"(ID: {user.id}, methods: {methods})"
            )

            return Login2FAChallengeResponse(
                requires_2fa=True,
                methods=methods,
                challenge_token=challenge_token,
            )

        # Generate JWT token (Requirement 2.3)
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value
            }
        )
        
        # Reset rate limiter on successful login
        login_rate_limiter.reset(login_data.email)
        
        # Log successful authentication attempt (Requirement 9.6)
        audit_log = AuditLog(
            admin_id=user.id,
            action="LOGIN_SUCCESS",
            target_type="user",
            target_id=user.id,
            details={
                "email": login_data.email,
                **_client_info(request)
            }
        )
        db.add(audit_log)
        db.commit()
        
        logger.info(f"Successful login: {user.email} (ID: {user.id})")
        
        # Return success response with token
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user={
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role.value,
                "is_email_verified": user.is_email_verified
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred during login",
                details={}
            )
        )



@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Invalid or expired token"},
        400: {"description": "Invalid request"}
    }
)
async def logout(
    request: Request,
    token: str = Depends(get_token_from_request),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> LogoutResponse:
    """Logout user and invalidate their JWT token.
    
    Validates Requirement 2.5:
    - Terminates the session by adding the token to a blacklist
    - Prevents the token from being used again
    - Logs the logout action in the audit log
    
    Args:
        token: The JWT token to invalidate (extracted from Authorization header)
        current_user: The authenticated user (from token validation)
        db: Database session
        
    Returns:
        LogoutResponse with success message
        
    Raises:
        HTTPException 401: If token is invalid or already revoked
        HTTPException 400: If request is malformed
    """
    try:
        # Verify token and extract expiration
        payload = verify_token(token)
        if not payload:
            logger.warning(f"Logout attempt with invalid token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorResponse.create(
                    code="INVALID_TOKEN",
                    message="Invalid or expired token",
                    details={}
                )
            )
        
        # Extract expiration time from token
        exp_timestamp = payload.get("exp")
        if not exp_timestamp:
            logger.warning(f"Token missing expiration claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorResponse.create(
                    code="INVALID_TOKEN",
                    message="Invalid token format",
                    details={}
                )
            )
        
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        
        # Check if token is already blacklisted
        existing_blacklist = db.query(TokenBlacklist).filter(
            TokenBlacklist.token == token
        ).first()
        
        if existing_blacklist:
            logger.info(f"Token already blacklisted for user: {current_user.email}")
            # Return success anyway (idempotent operation)
            return LogoutResponse(message="Logout successful")
        
        # Add token to blacklist (Requirement 2.5)
        blacklist_entry = TokenBlacklist(
            token=token,
            user_id=current_user.id,
            revoked_at=datetime.now(timezone.utc),
            expires_at=expires_at
        )
        
        db.add(blacklist_entry)
        
        # Log logout action in audit log
        audit_log = AuditLog(
            admin_id=current_user.id,
            action="LOGOUT",
            target_type="user",
            target_id=current_user.id,
            details={
                "email": current_user.email,
                "token_expires_at": expires_at.isoformat(),
                **_client_info(request)
            }
        )
        
        db.add(audit_log)
        db.commit()
        
        logger.info(f"User logged out successfully: {current_user.email} (ID: {current_user.id})")
        
        return LogoutResponse(message="Logout successful")
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        db.rollback()
        logger.error(f"Unexpected error during logout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred during logout",
                details={}
            )
        )



@router.post(
    "/verify-email",
    response_model=EmailVerificationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid or expired verification token"},
        404: {"description": "User not found"},
        409: {"description": "Email already verified"}
    }
)
@limiter.limit("10/hour")  # Limit email verification attempts
async def verify_email(
    request: Request,
    verification_data: EmailVerificationRequest,
    db: Session = Depends(get_db)
) -> EmailVerificationResponse:
    """Verify user's email address using verification token.
    
    Validates Requirement 2.6:
    - Verifies token and activates account
    - Allows user to login after verification
    
    Args:
        verification_data: Contains the verification token
        db: Database session
        
    Returns:
        EmailVerificationResponse with success message
        
    Raises:
        HTTPException 400: If token is invalid or expired
        HTTPException 404: If user not found
        HTTPException 409: If email already verified
    """
    return await _verify_email_logic(verification_data.token, db)


@router.get(
    "/verify-email",
    response_model=EmailVerificationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid or expired verification token"},
        404: {"description": "User not found"},
        409: {"description": "Email already verified"}
    }
)
@limiter.limit("10/hour")
async def verify_email_get(
    request: Request,
    token: str = Query(..., description="Email verification token"),
    db: Session = Depends(get_db)
) -> EmailVerificationResponse:
    """Verify user's email address using verification token from query parameter."""
    return await _verify_email_logic(token, db)


async def _verify_email_logic(token: str, db: Session) -> EmailVerificationResponse:
    """Verify user's email address using verification token - shared logic."""
    try:
        # Verify and decode token
        payload = verify_token(token)
        if not payload:
            logger.warning(f"Email verification attempt with invalid token")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse.create(
                    code="INVALID_TOKEN",
                    message="Invalid or expired verification token",
                    details={}
                )
            )
        
        # Check token type
        token_type = payload.get("type")
        if token_type != "email_verification":
            logger.warning(f"Email verification attempt with wrong token type: {token_type}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse.create(
                    code="INVALID_TOKEN",
                    message="Invalid verification token",
                    details={}
                )
            )
        
        # Extract user ID from token
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            logger.warning(f"Verification token missing user ID")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse.create(
                    code="INVALID_TOKEN",
                    message="Invalid token format",
                    details={}
                )
            )
        
        # Convert user_id string to UUID
        try:
            from uuid import UUID
            user_uuid = UUID(user_id)
        except (ValueError, AttributeError):
            logger.warning(f"Invalid user ID format in verification token: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse.create(
                    code="INVALID_TOKEN",
                    message="Invalid token format",
                    details={}
                )
            )
        
        # Fetch user from database
        user = db.query(User).filter(User.id == user_uuid).first()
        if not user:
            logger.warning(f"User not found for verification token: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse.create(
                    code="USER_NOT_FOUND",
                    message="User not found",
                    details={}
                )
            )
        
        # Check if email is already verified
        if user.is_email_verified:
            logger.info(f"Email already verified for user: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorResponse.create(
                    code="EMAIL_ALREADY_VERIFIED",
                    message="Email address is already verified",
                    details={"email": user.email}
                )
            )
        
        # Activate account by setting is_email_verified to True
        user.is_email_verified = True
        user.updated_at = datetime.now(timezone.utc)
        
        # Log verification action in audit log
        audit_log = AuditLog(
            admin_id=user.id,
            action="EMAIL_VERIFIED",
            target_type="user",
            target_id=user.id,
            details={
                "email": user.email
            }
        )
        
        db.add(audit_log)
        db.commit()
        db.refresh(user)
        
        logger.info(f"Email verified successfully for user: {user.email} (ID: {user.id})")
        
        return EmailVerificationResponse(
            email=user.email
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        db.rollback()
        logger.error(f"Unexpected error during email verification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred during email verification",
                details={}
            )
        )


@router.post("/password-reset", status_code=status.HTTP_200_OK)
@limiter.limit("5/hour")
async def request_password_reset(
    request: Request,
    reset_data: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """Request password reset email."""
    user = db.query(User).filter(User.email == reset_data.email).first()
    
    # Always return success to prevent email enumeration
    if not user:
        logger.info(f"Password reset requested for non-existent email: {reset_data.email}")
        return {"message": "Si cet email existe, un lien de réinitialisation a été envoyé."}
    
    # Generate reset token
    reset_token = create_access_token(
        data={"sub": str(user.id), "type": "password_reset"},
        expires_delta=timedelta(hours=1)
    )
    
    # Send reset email
    email_sent = email_service.send_password_reset_email(
        to_email=user.email,
        reset_token=reset_token,
        user_name=user.first_name
    )
    
    if email_sent:
        logger.info(f"Password reset email sent to {user.email}")
    else:
        logger.warning(f"Failed to send password reset email to {user.email}")
    
    return {"message": "Si cet email existe, un lien de réinitialisation a été envoyé."}


@router.post("/password-reset/confirm", status_code=status.HTTP_200_OK)
@limiter.limit("5/hour")
async def confirm_password_reset(
    request: Request,
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """Confirm password reset with token."""
    payload = verify_token(reset_data.token)
    if not payload or payload.get("type") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_TOKEN",
                message="Invalid or expired reset token",
                details={}
            )
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_TOKEN",
                message="Invalid token format",
                details={}
            )
        )
    
    from uuid import UUID
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_TOKEN",
                message="Invalid token format",
                details={}
            )
        )
    
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code="USER_NOT_FOUND",
                message="User not found",
                details={}
            )
        )
    
    # Update password
    user.password_hash = hash_password(reset_data.new_password)
    user.updated_at = datetime.now(timezone.utc)
    
    # Log password reset
    audit_log = AuditLog(
        admin_id=user.id,
        action="PASSWORD_RESET",
        target_type="user",
        target_id=user.id,
        details={"email": user.email}
    )
    db.add(audit_log)
    db.commit()
    
    logger.info(f"Password reset successful for user: {user.email}")
    
    return {"message": "Mot de passe réinitialisé avec succès."}


@router.post("/change-password", status_code=status.HTTP_200_OK)
@limiter.limit("10/hour")
async def change_password(
    request: Request,
    change_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change the currently authenticated user's password.

    Validates Requirements 3.3, 3.4, 3.5, 3.6, 3.7:
    - Verifies the submitted current password against the stored credential
      before applying any change (3.3).
    - On success, persists the new password hash as the user's credential (3.4)
      and records the event in the audit log (3.6).
    - On mismatch, rejects the request with an authentication error and leaves
      the stored credential unchanged (3.5).
    - Returns a French success message consumed by the security page (3.7).

    Args:
        change_data: The current and new password.
        current_user: The authenticated user (from get_current_user).
        db: Database session.

    Returns:
        A French success message.

    Raises:
        HTTPException 401: If the current password does not match.
    """
    try:
        # Verify the current password before applying any change (Requirement 3.3, 3.5)
        if not verify_password(change_data.current_password, current_user.password_hash):
            logger.warning(f"Failed password change (invalid current password): {current_user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorResponse.create(
                    code="INVALID_CREDENTIALS",
                    message="Le mot de passe actuel est incorrect.",
                    details={}
                )
            )

        # Persist the new password (Requirement 3.4)
        current_user.password_hash = hash_password(change_data.new_password)
        current_user.updated_at = datetime.now(timezone.utc)

        # Record the event in the audit log (Requirement 3.6)
        audit_log = AuditLog(
            admin_id=current_user.id,
            action="PASSWORD_CHANGED",
            target_type="user",
            target_id=current_user.id,
            details={"email": current_user.email}
        )
        db.add(audit_log)
        db.commit()

        logger.info(f"Password changed successfully for user: {current_user.email} (ID: {current_user.id})")

        # French confirmation message (Requirement 3.7)
        return {"message": "Mot de passe modifié avec succès."}

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during password change: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred during password change",
                details={}
            )
        )


@router.get(
    "/2fa/status",
    response_model=TwoFactorStatusResponse,
    status_code=status.HTTP_200_OK,
    responses={401: {"description": "Invalid or expired token"}},
)
async def two_factor_status(
    current_user: User = Depends(get_current_user),
) -> TwoFactorStatusResponse:
    """Return the current 2FA configuration for the authenticated user.

    Validates Requirements 8.1, 8.2:
    - Reports whether TOTP and Email 2FA are enabled.
    - Never exposes ``totp_secret``.

    Args:
        current_user: The authenticated user (from get_current_user).

    Returns:
        The enabled state of each 2FA method.
    """
    return TwoFactorStatusResponse(
        totp_enabled=current_user.totp_enabled,
        email_2fa_enabled=current_user.email_2fa_enabled,
    )


@router.post(
    "/2fa/totp/setup",
    response_model=TotpSetupResponse,
    status_code=status.HTTP_200_OK,
    responses={401: {"description": "Invalid or expired token"}},
)
@limiter.limit("10/hour")
async def totp_setup(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TotpSetupResponse:
    """Begin TOTP setup by generating and storing a pending secret.

    Validates Requirements 5.1, 5.2:
    - Generates a TOTP secret and stores it as pending on the user
      (``totp_secret`` set, ``totp_enabled`` stays false until confirmed).
    - Returns the secret and the otpauth provisioning URI for QR rendering.

    Args:
        current_user: The authenticated user (from get_current_user).
        db: Database session.

    Returns:
        The pending secret and its otpauth provisioning URI.
    """
    try:
        secret = totp.generate_secret()

        # Store as pending: secret set, but TOTP not yet enabled (Requirement 5.1)
        current_user.totp_secret = secret
        current_user.updated_at = datetime.now(timezone.utc)
        db.commit()

        otpauth_uri = totp.provisioning_uri(secret, current_user.email)

        logger.info(f"TOTP setup started for user: {current_user.email} (ID: {current_user.id})")

        return TotpSetupResponse(secret=secret, otpauth_uri=otpauth_uri)

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during TOTP setup: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred during TOTP setup",
                details={},
            ),
        )


@router.post(
    "/2fa/totp/confirm",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid TOTP code"},
        401: {"description": "Invalid or expired token"},
    },
)
async def totp_confirm(
    request: Request,
    confirm_data: TotpConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm a pending TOTP secret and enable TOTP 2FA.

    Validates Requirements 5.3, 5.4, 5.5:
    - Validates the submitted code against the stored (pending) secret (5.3).
    - On valid code: enables TOTP, records ``TOTP_2FA_ENABLED`` audit (5.4).
    - On invalid code: rejects with ``400 INVALID_2FA_CODE`` and leaves
      TOTP disabled (5.5).

    Args:
        confirm_data: The submitted TOTP code.
        current_user: The authenticated user (from get_current_user).
        db: Database session.

    Returns:
        ``{ "totp_enabled": true }`` on success.

    Raises:
        HTTPException 400: If the submitted code is invalid.
    """
    try:
        # Validate the submitted code against the pending secret (Requirement 5.3)
        if not totp.verify_code(current_user.totp_secret, confirm_data.code):
            logger.warning(f"Invalid TOTP confirmation code for user: {current_user.email}")
            # Leave TOTP disabled (Requirement 5.5)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse.create(
                    code="INVALID_2FA_CODE",
                    message="Le code de vérification est invalide.",
                    details={},
                ),
            )

        # Enable TOTP and persist (Requirement 5.4)
        current_user.totp_enabled = True
        current_user.updated_at = datetime.now(timezone.utc)

        audit_log = AuditLog(
            admin_id=current_user.id,
            action="TOTP_2FA_ENABLED",
            target_type="user",
            target_id=current_user.id,
            details={"email": current_user.email},
        )
        db.add(audit_log)
        db.commit()

        logger.info(f"TOTP 2FA enabled for user: {current_user.email} (ID: {current_user.id})")

        return {"totp_enabled": True}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during TOTP confirmation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred during TOTP confirmation",
                details={},
            ),
        )


@router.post(
    "/2fa/totp/disable",
    status_code=status.HTTP_200_OK,
    responses={401: {"description": "Invalid or expired token"}},
)
async def totp_disable(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disable TOTP 2FA and clear the stored secret.

    Validates Requirement 8.2 (management):
    - Sets ``totp_enabled=false``, clears ``totp_secret``, and records a
      ``TOTP_2FA_DISABLED`` audit event.

    Args:
        current_user: The authenticated user (from get_current_user).
        db: Database session.

    Returns:
        ``{ "totp_enabled": false }``.
    """
    try:
        current_user.totp_enabled = False
        current_user.totp_secret = None
        current_user.updated_at = datetime.now(timezone.utc)

        audit_log = AuditLog(
            admin_id=current_user.id,
            action="TOTP_2FA_DISABLED",
            target_type="user",
            target_id=current_user.id,
            details={"email": current_user.email},
        )
        db.add(audit_log)
        db.commit()

        logger.info(f"TOTP 2FA disabled for user: {current_user.email} (ID: {current_user.id})")

        return {"totp_enabled": False}

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error while disabling TOTP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred while disabling TOTP",
                details={},
            ),
        )


@router.post(
    "/2fa/email/enable",
    status_code=status.HTTP_200_OK,
    responses={401: {"description": "Invalid or expired token"}},
)
async def email_2fa_enable(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable email-based 2FA for the authenticated user.

    Validates Requirement 6.1:
    - Sets ``email_2fa_enabled=true`` and records an ``EMAIL_2FA_ENABLED``
      audit event.

    Args:
        current_user: The authenticated user (from get_current_user).
        db: Database session.

    Returns:
        ``{ "email_2fa_enabled": true }``.
    """
    try:
        current_user.email_2fa_enabled = True
        current_user.updated_at = datetime.now(timezone.utc)

        audit_log = AuditLog(
            admin_id=current_user.id,
            action="EMAIL_2FA_ENABLED",
            target_type="user",
            target_id=current_user.id,
            details={"email": current_user.email},
        )
        db.add(audit_log)
        db.commit()

        logger.info(f"Email 2FA enabled for user: {current_user.email} (ID: {current_user.id})")

        return {"email_2fa_enabled": True}

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error while enabling email 2FA: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred while enabling email 2FA",
                details={},
            ),
        )


@router.post(
    "/2fa/email/disable",
    status_code=status.HTTP_200_OK,
    responses={401: {"description": "Invalid or expired token"}},
)
async def email_2fa_disable(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disable email-based 2FA for the authenticated user.

    Supports Requirement 6.1 (management):
    - Sets ``email_2fa_enabled=false`` and records an ``EMAIL_2FA_DISABLED``
      audit event.

    Args:
        current_user: The authenticated user (from get_current_user).
        db: Database session.

    Returns:
        ``{ "email_2fa_enabled": false }``.
    """
    try:
        current_user.email_2fa_enabled = False
        current_user.updated_at = datetime.now(timezone.utc)

        audit_log = AuditLog(
            admin_id=current_user.id,
            action="EMAIL_2FA_DISABLED",
            target_type="user",
            target_id=current_user.id,
            details={"email": current_user.email},
        )
        db.add(audit_log)
        db.commit()

        logger.info(f"Email 2FA disabled for user: {current_user.email} (ID: {current_user.id})")

        return {"email_2fa_enabled": False}

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error while disabling email 2FA: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred while disabling email 2FA",
                details={},
            ),
        )


@router.post(
    "/login/2fa",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Invalid challenge token or verification code"},
        429: {"description": "Too many attempts"},
    },
)
@limiter.limit("20/hour")
async def login_2fa(
    request: Request,
    login_data: Login2FARequest,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Complete the second (2FA) step of login and issue a session token.

    Validates Requirements 7.1, 7.2, 7.3:
    - Verifies the short-lived challenge token (``type == "2fa_challenge"``,
      not expired) and resolves the user by ``sub``. Invalid/expired token →
      ``401 INVALID_TOKEN`` with no session token.
    - Validates the submitted code: TOTP is checked against the user's stored
      secret; the emailed code is checked against the ``code_hash`` embedded in
      the challenge token. A valid TOTP OR a matching email code is accepted.
    - Invalid code → ``401 INVALID_2FA_CODE``, no token,
      ``AuditLog(action="LOGIN_2FA_FAILED")`` (7.3).
    - Valid code → issue the normal session token (same claims/shape as the
      no-2FA login path), reset the login rate limiter, and record
      ``AuditLog(action="LOGIN_SUCCESS")`` (7.1, 7.2).

    Args:
        login_data: The challenge token and the submitted verification code.
        db: Database session.

    Returns:
        LoginResponse with a session access token on success.

    Raises:
        HTTPException 401: If the challenge token or code is invalid.
    """
    try:
        # Verify the challenge token (not expired, correct type)
        payload = verify_token(login_data.challenge_token)
        if not payload or payload.get("type") != "2fa_challenge":
            logger.warning("2FA login attempt with invalid/expired challenge token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorResponse.create(
                    code="INVALID_TOKEN",
                    message="Le jeton de vérification est invalide ou expiré.",
                    details={},
                ),
            )

        # Resolve the user by subject claim
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("2FA challenge token missing subject claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorResponse.create(
                    code="INVALID_TOKEN",
                    message="Le jeton de vérification est invalide.",
                    details={},
                ),
            )

        try:
            user_uuid = UUID(user_id)
        except (ValueError, AttributeError):
            logger.warning(f"Invalid user ID in 2FA challenge token: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorResponse.create(
                    code="INVALID_TOKEN",
                    message="Le jeton de vérification est invalide.",
                    details={},
                ),
            )

        user = db.query(User).filter(User.id == user_uuid).first()
        if not user:
            logger.warning(f"User not found for 2FA challenge token: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorResponse.create(
                    code="INVALID_TOKEN",
                    message="Le jeton de vérification est invalide.",
                    details={},
                ),
            )

        # Validate the submitted code. Accept a valid TOTP code OR a matching
        # emailed code, based on which methods the challenge covers.
        methods = payload.get("methods") or []
        code_valid = False

        if user.totp_enabled and "totp" in methods:
            if totp.verify_code(user.totp_secret, login_data.code):
                code_valid = True

        if not code_valid and user.email_2fa_enabled and "email" in methods:
            code_hash = payload.get("code_hash")
            if code_hash and secrets.compare_digest(
                _hash_2fa_code(login_data.code), code_hash
            ):
                code_valid = True

        if not code_valid:
            # Invalid second-step code (Requirement 7.3): no token issued.
            audit_log = AuditLog(
                admin_id=user.id,
                action="LOGIN_2FA_FAILED",
                target_type="user",
                target_id=user.id,
                details={"email": user.email},
            )
            db.add(audit_log)
            db.commit()

            logger.warning(f"Invalid 2FA code for user: {user.email} (ID: {user.id})")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorResponse.create(
                    code="INVALID_2FA_CODE",
                    message="Le code de vérification est invalide.",
                    details={},
                ),
            )

        # Deny expired/suspended memberships before issuing the session token.
        if _is_membership_blocked(user.membership_status):
            _deny_blocked_login(db, user, request, "LOGIN_2FA_FAILED")

        # Valid code: issue the normal session token (same shape/claims as the
        # no-2FA login path) (Requirements 7.1, 7.2).
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value,
            }
        )

        # Reset rate limiter on successful login
        login_rate_limiter.reset(user.email)

        audit_log = AuditLog(
            admin_id=user.id,
            action="LOGIN_SUCCESS",
            target_type="user",
            target_id=user.id,
            details={"email": user.email, "method": "2fa", **_client_info(request)},
        )
        db.add(audit_log)
        db.commit()

        logger.info(f"Successful 2FA login: {user.email} (ID: {user.id})")

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user={
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role.value,
                "is_email_verified": user.is_email_verified,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during 2FA login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred during 2FA login",
                details={},
            ),
        )
