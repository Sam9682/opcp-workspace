# Password Reset Feature Implementation

## Summary

Added a complete password reset flow to the OPCP website, allowing users who have forgotten their password to reset it via email.

## Changes Made

### 1. Frontend Pages Created

#### `/frontend/src/pages/ForgotPasswordPage.tsx`
- New page accessible at `https://opcp-psmc.com/forgot-password`
- User enters their email address
- Sends password reset request to backend
- Shows success message after submission
- Includes link back to login page

#### `/frontend/src/pages/ResetPasswordPage.tsx`
- New page accessible at `https://opcp-psmc.com/reset-password?token=...`
- User receives this link via email
- Allows user to enter new password with confirmation
- Validates password requirements:
  - Minimum 8 characters
  - At least 1 uppercase letter
  - At least 1 lowercase letter
  - At least 1 number
- Shows success message and redirects to login after 3 seconds

### 2. Login Page Modified

#### `/frontend/src/pages/LoginPage.tsx`
- Added "🔑 Mot de passe oublié ?" link below the login button
- Link directs to `/forgot-password` page

### 3. Services Updated

#### `/frontend/src/services/authService.ts`
- Added `requestPasswordReset(email: string)` method
  - Calls `POST /api/auth/password-reset`
- Added `resetPassword(token: string, newPassword: string)` method
  - Calls `POST /api/auth/password-reset/confirm`

### 4. Routing Updated

#### `/frontend/src/App.tsx`
- Added route for `/forgot-password` → `ForgotPasswordPage`
- Added route for `/reset-password` → `ResetPasswordPage`

## Backend (Already Implemented)

The backend already had the necessary endpoints:

### `POST /api/auth/password-reset`
- Accepts email address
- Generates password reset token (valid for 1 hour)
- Sends email with reset link to user
- Returns success message (prevents email enumeration)

### `POST /api/auth/password-reset/confirm`
- Accepts token and new password
- Validates token and password requirements
- Updates user's password
- Logs password reset in audit log

### Email Service
- `send_password_reset_email()` method already implemented
- Sends French language email with reset link
- Link format: `https://opcp-psmc.com/reset-password?token={reset_token}`

## User Flow

1. User clicks "Mot de passe oublié ?" on login page
2. User enters their email address on forgot password page
3. User receives email with reset link (valid for 1 hour)
4. User clicks link in email → opens reset password page
5. User enters new password twice (with validation)
6. Password is updated successfully
7. User is redirected to login page
8. User logs in with new password

## Security Features

- Rate limiting: 5 requests per hour per IP
- Token expires after 1 hour
- Password complexity validation enforced
- Email enumeration prevention (always returns success message)
- Audit logging of password reset actions
- Token is single-use (validated against user ID)

## Testing

To test the feature:

1. Navigate to `https://opcp-psmc.com/login`
2. Click "🔑 Mot de passe oublié ?"
3. Enter a registered email address
4. Check email inbox for reset link
5. Click link and enter new password
6. Verify redirect to login page
7. Login with new password

## Files Modified/Created

### Created:
- `/frontend/src/pages/ForgotPasswordPage.tsx`
- `/frontend/src/pages/ResetPasswordPage.tsx`
- `/docs/PASSWORD_RESET_FEATURE.md` (this file)

### Modified:
- `/frontend/src/pages/LoginPage.tsx`
- `/frontend/src/services/authService.ts`
- `/frontend/src/App.tsx`

## Notes

- Backend implementation was already complete
- Email service uses SMTP configuration from environment variables
- All text is in French to match the application language
- UI follows the existing design system with gradient colors and emojis
- Feature is fully RGPD compliant (no unnecessary data collection)
