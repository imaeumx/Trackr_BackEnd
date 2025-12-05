# Email Configuration Guide for TrackR Password Reset

## Gmail Setup Instructions

Para magamit ang password reset at change password features, kailangan mo i-configure ang Gmail SMTP settings.

### Step 1: Create Gmail App Password

1. **Enable 2-Factor Authentication sa Gmail mo**
   - Go to: https://myaccount.google.com/security
   - Scroll to "2-Step Verification" at i-enable

2. **Generate App Password**
   - Go to: https://myaccount.google.com/apppasswords
   - Select "Mail" at "Other (Custom name)"
   - Type "TrackR Backend"
   - Click "Generate"
   - **IMPORTANT**: Copy yung 16-character password na lalabas (example: `abcd efgh ijkl mnop`)

### Step 2: Set Environment Variables

**Para sa Development (Windows PowerShell):**

```powershell
cd Trackr_BackEnd

# Set environment variables (temporary, for current session only)
$env:EMAIL_HOST_USER = "your-email@gmail.com"
$env:EMAIL_HOST_PASSWORD = "your-app-password"  # Yung 16-character code from Step 1

# Start Django server
python manage.py runserver
```

**Para sa Production (.env file):**

Create a `.env` file sa `Trackr_BackEnd` folder:

```env
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-16-char-app-password
```

Then install python-decouple:
```bash
pip install python-decouple
```

### Step 3: Test Email Sending

Run this sa Django shell para mag-test:

```powershell
cd Trackr_BackEnd
python manage.py shell
```

Then sa shell:
```python
from django.core.mail import send_mail
from django.conf import settings

send_mail(
    'TrackR Test',
    'This is a test email from TrackR',
    settings.DEFAULT_FROM_EMAIL,
    ['recipient@example.com'],  # Replace with your test email
    fail_silently=False,
)
```

Kung successful, makikita mo sa console: `1` (meaning 1 email sent successfully)

## How the Features Work

### 1. Forgot Password (Para sa users na nakalimutan password)
- User enters email address
- Backend sends 6-digit code sa email
- User enters code to verify
- User sets new password
- Code expires after 10 minutes

### 2. Change Password (Para sa logged-in users)
- User requests verification code from Profile > Change Password
- Backend sends 6-digit code sa registered email
- User enters:
  - Current password
  - Verification code
  - New password
  - Confirm new password
- Backend validates everything and changes password

## API Endpoints Created

### Password Reset (No authentication required):
- `POST /api/auth/password-reset/request/` - Send code to email
- `POST /api/auth/password-reset/verify/` - Verify the code
- `POST /api/auth/password-reset/confirm/` - Set new password

### Change Password (Requires authentication):
- `POST /api/auth/change-password/request/` - Request verification code
- `POST /api/auth/change-password/` - Change password with code

## Security Features

1. ✅ Codes expire after 10 minutes
2. ✅ Codes are stored in cache (not database)
3. ✅ Requires email verification before password change
4. ✅ Change password requires current password + code
5. ✅ New auth token generated after successful password change
6. ✅ Minimum password length: 8 characters

## Troubleshooting

### "Failed to send email" error:
- Check if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD are set correctly
- Verify 2FA is enabled sa Gmail
- Verify App Password is correct (no spaces)
- Check internet connection

### "Code expired" error:
- Code is valid for 10 minutes only
- Click "Resend" to get a new code

### Gmail blocking sign-in:
- Make sure you're using App Password, NOT your Gmail password
- Enable "Less secure app access" (not recommended) OR use App Password

## Alternative Email Providers

Pwede mo rin gamitin ang ibang email providers:

### SendGrid:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'
EMAIL_HOST_PASSWORD = 'your-sendgrid-api-key'
```

### Outlook:
```python
EMAIL_HOST = 'smtp-mail.outlook.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@outlook.com'
EMAIL_HOST_PASSWORD = 'your-password'
```

## Development Tips

1. **Console Backend (Testing without email)**
   Para sa development, pwede mo gamitin console backend:
   ```python
   # In settings.py
   EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
   ```
   This will print emails sa console instead of sending them.

2. **File Backend (Save to file)**
   ```python
   EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
   EMAIL_FILE_PATH = BASE_DIR / 'sent_emails'
   ```

## Production Deployment

For production (Render, Heroku, etc.):

1. Add environment variables sa hosting platform
2. Set `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD`
3. Make sure `DEBUG = False` in production
4. Use proper email service (SendGrid, Mailgun, etc.) for better deliverability
