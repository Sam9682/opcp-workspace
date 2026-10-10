# Fix SMTP Authentication Error

## Problem
Password reset emails fail with error:
```
535, b'5.7.8 Error: authentication failed: (reason unavailable)'
```

## Root Cause
The SMTP password in `.env` is set to the placeholder `your-email-password` instead of a valid credential.

## Solution

### For Gandi.net Email (current setup)

1. **Login to Gandi Admin Panel**
   - Go to https://admin.gandi.net/

2. **Generate App Password**
   - Navigate to: **Email** → **Your mailbox** → **Settings** → **App passwords**
   - Click "Create a new app password"
   - Give it a name (e.g., "OPCP Website")
   - Copy the generated password

3. **Update .env file**
   ```bash
   SMTP_HOST=mail.gandi.net
   SMTP_PORT=587
   SMTP_USER=admin@opcp-psmc.com
   SMTP_PASSWORD=<paste-your-app-password-here>
   SMTP_FROM=noreply@opcp-psmc.com
   ```

4. **Restart the application**
   ```bash
   docker-compose restart backend
   # or
   ./scripts/restart.sh
   ```

### For Gmail (alternative)

1. **Enable 2-Step Verification**
   - Go to Google Account settings
   - Security → 2-Step Verification

2. **Generate App Password**
   - Security → App passwords
   - Select "Mail" and your device
   - Copy the 16-character password

3. **Update .env file**
   ```bash
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=<16-character-app-password>
   SMTP_FROM=your-email@gmail.com
   ```

### For Outlook/Office365 (alternative)

1. **Enable SMTP AUTH**
   - Go to Outlook settings
   - Enable "SMTP AUTH" in account settings

2. **Update .env file**
   ```bash
   SMTP_HOST=smtp-mail.outlook.com
   SMTP_PORT=587
   SMTP_USER=your-email@outlook.com
   SMTP_PASSWORD=<your-account-password>
   SMTP_FROM=your-email@outlook.com
   ```

## Testing

Test SMTP configuration:
```bash
python app/test_smtp.py
```

Or test password reset from the frontend:
1. Go to login page
2. Click "Mot de passe oublié"
3. Enter a registered email
4. Check logs for success message

## Code Changes

The email service now:
- ✅ Detects unconfigured SMTP (placeholder password)
- ✅ Logs clear warning messages
- ✅ Handles authentication errors gracefully
- ✅ Adds timeout to prevent hanging
- ✅ Doesn't crash the application

## Security Notes

- Never commit real passwords to git
- Use app-specific passwords, not account passwords
- Keep `.env` file in `.gitignore`
- Rotate passwords regularly
