"""
Email helper using Brevo HTTP API (works on Render free tier)
"""
import os
import requests
import threading
from flask import current_app


def send_email_async(subject, recipient_email, recipient_name, html_content, text_content=None):
    """
    Send email asynchronously using Brevo HTTP API
    Works on Render free tier (SMTP blocked but HTTPS allowed)
    """
    def send_email_thread(app, subject, recipient_email, recipient_name, html_content, text_content):
        with app.app_context():
            try:
                api_key = app.config.get('BREVO_API_KEY')
                if not api_key:
                    print("ERROR: BREVO_API_KEY not configured")
                    return
                
                # Get sender email from config (use Brevo login email)
                sender_email = app.config.get('BREVO_SENDER_EMAIL', 'no-reply@example.com')
                
                # Brevo API endpoint
                url = "https://api.brevo.com/v3/smtp/email"
                
                # Prepare email data
                payload = {
                    "sender": {
                        "name": "ELIS Smart Tenant Management",
                        "email": sender_email
                    },
                    "to": [
                        {
                            "email": recipient_email,
                            "name": recipient_name
                        }
                    ],
                    "subject": subject,
                    "htmlContent": html_content
                }
                
                # Add text content if provided
                if text_content:
                    payload["textContent"] = text_content
                
                # Send request
                headers = {
                    "accept": "application/json",
                    "api-key": api_key,
                    "content-type": "application/json"
                }
                
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                
                if response.status_code == 201:
                    print(f"✅ Email sent successfully to {recipient_email}")
                else:
                    print(f"❌ Failed to send email: {response.status_code} - {response.text}")
                    
            except Exception as e:
                print(f"❌ Email sending error: {e}")
    
    # Run in background thread
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=send_email_thread,
        args=(app, subject, recipient_email, recipient_name, html_content, text_content)
    )
    thread.daemon = True
    thread.start()


def send_otp_email(recipient_email, recipient_name, otp_code):
    """Send OTP verification email"""
    subject = "Your OTP Code - ELIS STMS"
    
    text_content = f"""
Dear {recipient_name},

Your OTP code is: {otp_code}

This code will expire in 10 minutes.

If you did not request this code, please ignore this email.

Thank you,
ELIS Smart Tenant Management System
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #D7B35B; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background-color: #f8f9fa; padding: 30px; border-radius: 0 0 8px 8px; }}
        .otp-box {{ background-color: #fff; border: 2px dashed #D7B35B; padding: 20px; margin: 20px 0; text-align: center; border-radius: 8px; }}
        .otp-code {{ font-size: 32px; font-weight: bold; color: #D7B35B; letter-spacing: 5px; }}
        .footer {{ text-align: center; margin-top: 30px; color: #6c757d; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">🔐 OTP Verification</h1>
        </div>
        <div class="content">
            <p>Dear <strong>{recipient_name}</strong>,</p>
            
            <p>Your One-Time Password (OTP) for email verification is:</p>
            
            <div class="otp-box">
                <div class="otp-code">{otp_code}</div>
            </div>
            
            <p><strong>⏰ Valid for 10 minutes</strong></p>
            
            <p>If you did not request this code, please ignore this email.</p>
            
            <p>Thank you,<br>
            <strong>ELIS Smart Tenant Management System</strong></p>
        </div>
        <div class="footer">
            <p>This is an automated message. Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email_async(subject, recipient_email, recipient_name, html_content, text_content)


def send_password_reset_email(recipient_email, recipient_name, reset_token, reset_url):
    """Send password reset email"""
    subject = "Password Reset Request - ELIS STMS"
    
    text_content = f"""
Dear {recipient_name},

You requested to reset your password for ELIS Smart Tenant Management System.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you did not request this, please ignore this email.

Thank you,
ELIS Smart Tenant Management System
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #D7B35B; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background-color: #f8f9fa; padding: 30px; border-radius: 0 0 8px 8px; }}
        .button {{ display: inline-block; padding: 12px 30px; background-color: #D7B35B; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
        .footer {{ text-align: center; margin-top: 30px; color: #6c757d; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">🔑 Password Reset</h1>
        </div>
        <div class="content">
            <p>Dear <strong>{recipient_name}</strong>,</p>
            
            <p>You requested to reset your password for ELIS Smart Tenant Management System.</p>
            
            <p style="text-align: center;">
                <a href="{reset_url}" class="button" style="color: white;">Reset Password</a>
            </p>
            
            <p>Or copy this link: <br><small>{reset_url}</small></p>
            
            <p><strong>⏰ This link will expire in 1 hour</strong></p>
            
            <p>If you did not request this, please ignore this email.</p>
            
            <p>Thank you,<br>
            <strong>ELIS Smart Tenant Management System</strong></p>
        </div>
        <div class="footer">
            <p>This is an automated message. Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email_async(subject, recipient_email, recipient_name, html_content, text_content)


def send_ban_notification(user_email, user_name, ban_reason):
    """Send ban notification email"""
    subject = "Account Suspended - The Elis Center"
    
    text_content = f"""
Dear {user_name},

Your account at The Elis Center Smart Tenant Management System has been suspended.

Reason: {ban_reason}

If you believe this is a mistake or would like to appeal this decision, please contact the administrator.

Thank you,
The Elis Center Management
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #dc3545; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background-color: #f8f9fa; padding: 30px; border-radius: 0 0 8px 8px; }}
        .reason {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px; }}
        .footer {{ text-align: center; margin-top: 30px; color: #6c757d; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">⚠️ Account Suspended</h1>
        </div>
        <div class="content">
            <p>Dear <strong>{user_name}</strong>,</p>
            
            <p>Your account at <strong>The Elis Center Smart Tenant Management System</strong> has been suspended.</p>
            
            <div class="reason">
                <strong>Reason:</strong> {ban_reason}
            </div>
            
            <p>If you believe this is a mistake or would like to appeal this decision, please contact the administrator.</p>
            
            <p>Thank you,<br>
            <strong>The Elis Center Management</strong></p>
        </div>
        <div class="footer">
            <p>This is an automated message. Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email_async(subject, user_email, user_name, html_content, text_content)


def send_unban_notification(user_email, user_name):
    """Send unban notification email"""
    subject = "Account Reactivated - The Elis Center"
    
    text_content = f"""
Dear {user_name},

Good news! Your account at The Elis Center Smart Tenant Management System has been reactivated.

You can now log in and access all features again.

If you have any questions, please contact the administrator.

Thank you,
The Elis Center Management
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #28a745; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background-color: #f8f9fa; padding: 30px; border-radius: 0 0 8px 8px; }}
        .message {{ background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin: 20px 0; border-radius: 4px; }}
        .footer {{ text-align: center; margin-top: 30px; color: #6c757d; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">✅ Account Reactivated</h1>
        </div>
        <div class="content">
            <p>Dear <strong>{user_name}</strong>,</p>
            
            <div class="message">
                <p><strong>Good news!</strong> Your account at <strong>The Elis Center Smart Tenant Management System</strong> has been reactivated.</p>
            </div>
            
            <p>You can now log in and access all features again.</p>
            
            <p>If you have any questions, please contact the administrator.</p>
            
            <p>Thank you,<br>
            <strong>The Elis Center Management</strong></p>
        </div>
        <div class="footer">
            <p>This is an automated message. Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email_async(subject, user_email, user_name, html_content, text_content)

