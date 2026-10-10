"""Pydantic schemas for authentication endpoints"""
from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class RegistrationRequest(BaseModel):
    """Request schema for user registration
    
    Validates Requirements 2.1, 2.7:
    - Email format validation
    - Password complexity requirements
    """
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    
    @field_validator('password')
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Validate password complexity requirements.
        
        Requirements 2.7: Password must contain:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        """
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        
        return v


class RegistrationResponse(BaseModel):
    """Response schema for successful registration"""
    id: str
    email: str
    first_name: str
    last_name: str
    message: str = "Registration successful. Please check your email to verify your account."
    
    model_config = {
        "from_attributes": True
    }


class LoginRequest(BaseModel):
    """Request schema for user login
    
    Validates Requirements 2.3, 2.4:
    - Email and password credentials
    """
    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    """Response schema for successful login"""
    access_token: str
    token_type: str = "bearer"
    user: dict
    
    model_config = {
        "from_attributes": True
    }


class ErrorResponse(BaseModel):
    """Standard error response schema"""
    error: dict
    
    @staticmethod
    def create(code: str, message: str, details: dict = None) -> dict:
        """Create a standardized error response"""
        from datetime import datetime, timezone
        import uuid
        
        return {
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "requestId": str(uuid.uuid4())
            }
        }


class LogoutResponse(BaseModel):
    """Response schema for successful logout"""
    message: str = "Logout successful"
    
    model_config = {
        "from_attributes": True
    }


class EmailVerificationRequest(BaseModel):
    """Request schema for email verification
    
    Validates Requirement 2.6:
    - Token-based email verification
    """
    token: str = Field(min_length=1)


class EmailVerificationResponse(BaseModel):
    """Response schema for successful email verification"""
    message: str = "Email verified successfully. You can now log in."
    email: str
    
    model_config = {
        "from_attributes": True
    }


class PasswordResetRequest(BaseModel):
    """Request schema for password reset"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Request schema for password reset confirmation"""
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=72)
    
    @field_validator('new_password')
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        return v


class ChangePasswordRequest(BaseModel):
    """Request schema for changing the current user's password.

    Validates Requirements 3.2, 3.4:
    - Requires the current password
    - New password must meet complexity requirements (reuses the same
      validator as PasswordResetConfirm)
    """
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator('new_password')
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        return v


class TwoFactorStatusResponse(BaseModel):
    """Response schema for the two-factor status endpoint.

    Validates Requirement 8.2: reports whether each 2FA method is enabled.
    Never exposes the TOTP secret.
    """
    totp_enabled: bool
    email_2fa_enabled: bool

    model_config = {
        "from_attributes": True
    }


class TotpSetupResponse(BaseModel):
    """Response schema for starting TOTP setup.

    Validates Requirements 5.1, 5.2: returns the pending secret and the
    otpauth provisioning URI used to render a QR code.
    """
    secret: str
    otpauth_uri: str


class TotpConfirmRequest(BaseModel):
    """Request schema for confirming a pending TOTP secret.

    Validates Requirement 5.3: the user submits a code to prove possession.
    """
    code: str = Field(min_length=1, max_length=10)


class Login2FARequest(BaseModel):
    """Request schema for the second-step 2FA login verification.

    Validates Requirements 7.1, 7.2: carries the challenge token and the
    submitted verification code.
    """
    challenge_token: str = Field(min_length=1)
    code: str = Field(min_length=1, max_length=10)


class Login2FAChallengeResponse(BaseModel):
    """Response schema returned by login when a 2FA challenge is required.

    Validates Requirements 7.1, 7.2: signals the client to prompt for a
    second-step code and lists the available methods.
    """
    requires_2fa: bool = True
    methods: list[str]
    challenge_token: str

    model_config = {
        "from_attributes": True
    }
