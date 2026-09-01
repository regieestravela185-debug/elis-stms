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


def send_reservation_result_email(to_email, to_name, status, unit_code):
    """Send reservation result email (approved/rejected/cancelled)"""
    from datetime import date
    
    status_text = status.upper()
    
    if status == "approved":
        status_color = "#40c940"
        status_icon = "✓"
        next_steps_approved = True
    elif status == "rejected":
        status_color = "#ff5050"
        status_icon = "✗"
        next_steps_approved = False
    else:  # CANCELLED
        status_color = "#ff5050"
        status_icon = "!"
        next_steps_approved = False

    subject = f"Reservation {status_text} - The Elis Center STMS"
    
    text_content = f"""
Dear {to_name},

Your reservation for Unit {unit_code} has been {status_text.lower()}.

{'Your account is now tagged as tenant. Please login again to access your tenant portal.' if next_steps_approved else 'You may contact us or submit another reservation request for other available units.'}

Thank you,
The Elis Center Management
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reservation Status</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
        </div>
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">Reservation {status_text}</h2>
            <div style="background: #f9f9f9; border: 2px solid {status_color}; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                <span style="font-size: 48px; font-weight: 700; color: {status_color};">{status_icon}</span>
                <p style="margin: 12px 0 0 0; color: {status_color}; font-size: 18px; font-weight: 600;">{status_text}</p>
            </div>
            <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Your reservation for <strong>Unit {unit_code}</strong> has been {status_text.lower()}.</p>
            <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                {'Your account is now tagged as tenant. Please login again to access your tenant portal.' if next_steps_approved else 'You may contact us or submit another reservation request for other available units.'}
            </p>
            <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B;">
                <p style="margin: 0; color: #666666; font-size: 14px; line-height: 1.5;"><strong>Next Steps:</strong></p>
                <ul style="margin: 8px 0 0 20px; padding: 0; color: #666666; font-size: 14px; line-height: 1.5;">
                    <li>{'Complete your tenant profile setup' if next_steps_approved else 'Browse available units on our website'}</li>
                    <li>{'Review your contract details' if next_steps_approved else 'Submit a new reservation request'}</li>
                    <li>Contact admin if you have questions</li>
                </ul>
            </div>
        </div>
        <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email_async(subject, to_email, to_name, html_content, text_content)


def send_reservation_submitted_email(
    to_email, to_name, unit_code, unit_type, floor, monthly_price,
    deposit_amount, move_in_date, move_out_date,
):
    """Send confirmation email right after a reservation is submitted (pending admin review)."""
    from datetime import date

    total_due = float(monthly_price) + float(deposit_amount)
    fmt = lambda n: f"₱{n:,.2f}"
    floor_label = f"{floor}{'st' if floor == 1 else 'nd' if floor == 2 else 'rd' if floor == 3 else 'th'} Floor" if floor else "—"
    move_out_line = f"- Move-out date: {move_out_date.strftime('%B %d, %Y')}\n" if move_out_date else "- Tenancy: Month-to-month (no fixed end date — rent continues until you give move-out notice)\n"
    move_out_row_html = (
        f'<tr><td style="padding: 4px 0; color: #888888;">Move-out date</td><td style="padding: 4px 0; text-align: right; font-weight: 600;">{move_out_date.strftime("%B %d, %Y")}</td></tr>'
        if move_out_date else
        '<tr><td style="padding: 4px 0; color: #888888;">Tenancy</td><td style="padding: 4px 0; text-align: right; font-weight: 600;">Month-to-month</td></tr>'
    )

    subject = f"Reservation Received — Unit {unit_code} — The Elis Center STMS"

    text_content = f"""
Dear {to_name},

We've received your reservation for Unit {unit_code} and it is now PENDING ADMIN APPROVAL.

Unit details:
- Unit: {unit_code} ({unit_type})
- Floor: {floor_label}
- Monthly rent: {fmt(float(monthly_price))}
- Reservation deposit: {fmt(float(deposit_amount))} (one month's rent + ₱1,000, refundable after contract ends minus damages and unpaid bills)
- Total due on approval: {fmt(total_due)}
- Move-in date: {move_in_date.strftime('%B %d, %Y')}
{move_out_line}
Our team will review your submitted ID and reservation details. You'll receive another email as soon as it's approved or if we need anything else from you.

Thank you,
The Elis Center Management
"""

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reservation Received</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
        </div>
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 8px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">Reservation Received</h2>
            <p style="margin: 0 0 20px 0; color: #666666; line-height: 1.6;">Hi {to_name}, thank you for reserving with us. Here's a summary of your submission.</p>

            <div style="background: #f9f9f9; border: 2px solid #f0ad4e; border-radius: 8px; padding: 18px; text-align: center; margin: 0 0 24px 0;">
                <p style="margin: 0; color: #b8860b; font-size: 16px; font-weight: 700; letter-spacing: 0.04em;">PENDING ADMIN APPROVAL</p>
                <p style="margin: 6px 0 0 0; color: #8a6d1e; font-size: 13px;">We'll email you again once it's reviewed.</p>
            </div>

            <div style="background: #f9f9f9; border-radius: 8px; padding: 20px; margin: 0 0 20px 0;">
                <p style="margin: 0 0 12px 0; color: #1a1a1a; font-size: 15px; font-weight: 700;">Unit {unit_code} &mdash; {unit_type}</p>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px; color: #444444;">
                    <tr><td style="padding: 4px 0; color: #888888;">Floor</td><td style="padding: 4px 0; text-align: right; font-weight: 600;">{floor_label}</td></tr>
                    <tr><td style="padding: 4px 0; color: #888888;">Move-in date</td><td style="padding: 4px 0; text-align: right; font-weight: 600;">{move_in_date.strftime('%B %d, %Y')}</td></tr>
                    {move_out_row_html}
                </table>
            </div>

            <div style="background: #fff9ec; border: 1px solid #D7B35B; border-radius: 8px; padding: 20px; margin: 0 0 24px 0;">
                <p style="margin: 0 0 12px 0; color: #8a6d1e; font-size: 15px; font-weight: 700;">Payment Breakdown</p>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px; color: #444444;">
                    <tr><td style="padding: 4px 0; color: #888888;">Monthly rent</td><td style="padding: 4px 0; text-align: right; font-weight: 600;">{fmt(float(monthly_price))}</td></tr>
                    <tr><td style="padding: 4px 0; color: #888888;">Reservation deposit</td><td style="padding: 4px 0; text-align: right; font-weight: 600;">{fmt(float(deposit_amount))}</td></tr>
                    <tr><td style="padding: 10px 0 0; color: #1a1a1a; font-weight: 700; border-top: 1px solid #e8dcc0;">Total due on approval</td><td style="padding: 10px 0 0; text-align: right; color: #B8922F; font-weight: 700; font-size: 16px; border-top: 1px solid #e8dcc0;">{fmt(total_due)}</td></tr>
                </table>
                <p style="margin: 12px 0 0 0; color: #999999; font-size: 12px; line-height: 1.5;">Deposit = one month's rent + ₱1,000, refundable after your contract ends minus damages and unpaid bills.</p>
            </div>

            <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B;">
                <p style="margin: 0; color: #666666; font-size: 14px; line-height: 1.5;"><strong>What happens next:</strong></p>
                <ul style="margin: 8px 0 0 20px; padding: 0; color: #666666; font-size: 14px; line-height: 1.5;">
                    <li>Our team reviews your submitted ID and reservation details</li>
                    <li>You'll receive an email once it's approved or if anything else is needed</li>
                    <li>Once approved, your account becomes your tenant portal</li>
                </ul>
            </div>
        </div>
        <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

    send_email_async(subject, to_email, to_name, html_content, text_content)


def send_renewal_reminder_email(tenant_name, tenant_email, unit_code, contract_end_date, days_remaining):
    """Send contract renewal reminder email"""
    from datetime import date
    
    subject = f"Contract Renewal Reminder - {days_remaining} Days Remaining"
    
    text_content = f"""
Dear {tenant_name},

Your lease contract for Unit {unit_code} will expire on {contract_end_date.strftime('%B %d, %Y')}. 
You have {days_remaining} days remaining.

To continue your stay, please submit a renewal request through your tenant portal or contact our administration office.

Thank you,
The Elis Center Management
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contract Renewal Reminder</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
        </div>
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">Contract Renewal Reminder</h2>
            <div style="background: rgba(255, 80, 80, 0.1); border: 2px solid #ff5050; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                <span style="font-size: 48px; font-weight: 700; color: #ff5050;">⚠️</span>
                <p style="margin: 12px 0 0 0; color: #ff5050; font-size: 18px; font-weight: 600;">Contract Expiring Soon</p>
            </div>
            <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
            <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                Your lease contract for <strong>Unit {unit_code}</strong> will expire on <strong>{contract_end_date.strftime('%B %d, %Y')}</strong>. 
                You have <strong>{days_remaining} days</strong> remaining.
            </p>
            <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                To continue your stay, please submit a renewal request through your tenant portal or contact our administration office.
            </p>
            <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B;">
                <p style="margin: 0; color: #666666; font-size: 14px; line-height: 1.5;"><strong>Next Steps:</strong></p>
                <ul style="margin: 8px 0 0 20px; padding: 0; color: #666666; font-size: 14px; line-height: 1.5;">
                    <li>Login to your tenant portal</li>
                    <li>Go to Renewal section</li>
                    <li>Submit your renewal request</li>
                    <li>Or contact us directly for assistance</li>
                </ul>
            </div>
        </div>
        <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email_async(subject, tenant_email, tenant_name, html_content, text_content)


def send_payment_reminder_email(tenant_name, tenant_email, unit_code, due_date, days_remaining, amount):
    """Send monthly rent payment reminder email"""
    from datetime import date

    if days_remaining <= 0:
        subject = "Rent Payment Due Today - The Elis Center"
        due_text = "is due today"
    else:
        subject = f"Rent Payment Reminder - {days_remaining} Day{'s' if days_remaining != 1 else ''} Left"
        due_text = f"is due in {days_remaining} day{'s' if days_remaining != 1 else ''}"

    amount_text = f"₱{amount:,.2f}" if amount else "your monthly rent"

    text_content = f"""
Dear {tenant_name},

Your rent payment for Unit {unit_code} {due_text} ({due_date.strftime('%B %d, %Y')}).
Amount due: {amount_text}

Please settle your payment through your tenant portal or contact our administration office.
If you have already paid, you may disregard this reminder.

Thank you,
The Elis Center Management
"""

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rent Payment Reminder</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
        </div>
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">Rent Payment Reminder</h2>
            <div style="background: rgba(245, 158, 11, 0.1); border: 2px solid #f59e0b; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                <span style="font-size: 48px; font-weight: 700; color: #f59e0b;">⏰</span>
                <p style="margin: 12px 0 0 0; color: #b45309; font-size: 18px; font-weight: 600;">Payment {due_text.replace('is ', '').capitalize()}</p>
            </div>
            <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
            <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                Your rent payment for <strong>Unit {unit_code}</strong> {due_text} on <strong>{due_date.strftime('%B %d, %Y')}</strong>.
            </p>
            <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B; margin: 24px 0;">
                <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Amount Due:</strong></p>
                <p style="margin: 0; color: #1a1a1a; font-size: 20px; font-weight: 700;">{amount_text}</p>
            </div>
            <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                Please settle your payment through your tenant portal or contact our administration office. If you have already paid, you may disregard this reminder.
            </p>
        </div>
        <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

    send_email_async(subject, tenant_email, tenant_name, html_content, text_content)


def send_utility_bill_reminder_email(
    tenant_name, tenant_email, unit_code, due_date, days_remaining,
    rent_amount, electric_amount, water_amount, carried_over_amount,
    electric_paid=False, water_paid=False,
    carried_over_electric=0, carried_over_water=0,
):
    """Monthly Rent + Electric + Water reminder, 7 days before due date.
    Unlike rent, utilities have no late penalty — an unpaid balance simply
    carries into next month's bill, so the carried-over line (and any
    "previous balance" language) only appears when there actually is one.

    Electric and water are settled independently, so each line states its
    own status: a component already paid is shown as settled and is left
    out of the total, and each carry-over is shown against the component
    it came from rather than as one unattributed lump."""
    from datetime import date

    electric_due = float(electric_amount) + float(carried_over_electric)
    water_due = float(water_amount) + float(carried_over_water)
    total = float(rent_amount)
    if not electric_paid:
        total += electric_due
    if not water_paid:
        total += water_due

    def _status(paid, carried):
        """Trailing note on a line: settled, or how much of it is arrears."""
        if paid:
            return " — already settled"
        if carried:
            return f" (includes ₱{carried:,.2f} unpaid from last month)"
        return ""

    electric_note = _status(electric_paid, float(carried_over_electric))
    water_note = _status(water_paid, float(carried_over_water))

    if days_remaining <= 0:
        subject = "Bill Due Today - The Elis Center"
        due_text = "is due today"
    else:
        subject = f"Monthly Bill Reminder - {days_remaining} Day{'s' if days_remaining != 1 else ''} Left"
        due_text = f"is due in {days_remaining} day{'s' if days_remaining != 1 else ''}"

    text_content = f"""
Dear {tenant_name},

Your monthly bill for Unit {unit_code} {due_text} ({due_date.strftime('%B %d, %Y')}).

Monthly Rent: ₱{rent_amount:,.2f}
Electric: ₱{electric_due:,.2f}{electric_note}
Water: ₱{water_due:,.2f}{water_note}
Total Amount Due: ₱{total:,.2f}

Please settle your payment before the due date. If you have already paid, you may disregard this reminder.

Thank you,
The Elis Center Management
"""

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monthly Bill Reminder</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
        </div>
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">Monthly Bill Reminder</h2>
            <div style="background: rgba(245, 158, 11, 0.1); border: 2px solid #f59e0b; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                <span style="font-size: 48px; font-weight: 700; color: #f59e0b;">⏰</span>
                <p style="margin: 12px 0 0 0; color: #b45309; font-size: 18px; font-weight: 600;">Bill {due_text.replace('is ', '').capitalize()}</p>
            </div>
            <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
            <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                Your monthly bill for <strong>Unit {unit_code}</strong> {due_text} on <strong>{due_date.strftime('%B %d, %Y')}</strong>.
            </p>
            <div style="background: #f9f9f9; padding: 20px; border-radius: 8px; border-left: 4px solid #D7B35B; margin: 24px 0;">
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <tr>
                        <td style="padding: 6px 0; color: #666666;">Monthly Rent</td>
                        <td style="padding: 6px 0; color: #1a1a1a; text-align: right; font-weight: 600;">₱{rent_amount:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #666666;">Electric{electric_note}</td>
                        <td style="padding: 6px 0; color: #1a1a1a; text-align: right; font-weight: 600;">₱{electric_due:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #666666;">Water{water_note}</td>
                        <td style="padding: 6px 0; color: #1a1a1a; text-align: right; font-weight: 600;">₱{water_due:,.2f}</td>
                    </tr>
                    <tr>
                        <td colspan="2" style="border-top: 1px solid #e5e5e5; padding-top: 10px;"></td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #1a1a1a; font-size: 16px; font-weight: 700;">Total Amount Due</td>
                        <td style="padding: 6px 0; color: #D7B35B; text-align: right; font-size: 20px; font-weight: 700;">₱{total:,.2f}</td>
                    </tr>
                </table>
            </div>
            <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                Please settle your payment before the due date above. If you have already paid, you may disregard this reminder.
            </p>
        </div>
        <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

    send_email_async(subject, tenant_email, tenant_name, html_content, text_content)


def send_inquiry_confirmation_email(full_name, email, subject_text, message_text):
    """Send inquiry confirmation email to the person who submitted the inquiry"""
    from datetime import datetime
    
    subject = f"Inquiry Received - {subject_text}"
    
    text_content = f"""
Dear {full_name},

We have received your inquiry regarding: {subject_text}

Our team will review your message and respond to you as soon as possible at {email}.

Your Message:
{message_text}

If you have any urgent concerns, please contact us directly at:
Phone: 0918-912-6340 or 0918-920-5645
Hours: Mon–Sat, 9:00 AM – 6:00 PM

Thank you,
The Elis Center Management
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Inquiry Received</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
        </div>
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">Inquiry Received</h2>
            <div style="background: rgba(64, 201, 64, 0.1); border: 2px solid #40c940; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                <span style="font-size: 48px; font-weight: 700; color: #40c940;">✓</span>
                <p style="margin: 12px 0 0 0; color: #40c940; font-size: 18px; font-weight: 600;">Thank You!</p>
            </div>
            <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{full_name}</strong>,</p>
            <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                We have received your inquiry regarding: <strong>{subject_text}</strong>
            </p>
            <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                Our team will review your message and respond to you as soon as possible at <strong>{email}</strong>.
            </p>
            <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B;">
                <p style="margin: 0; color: #666666; font-size: 14px; line-height: 1.5;"><strong>Your Message:</strong></p>
                <p style="margin: 8px 0 0 0; color: #666666; font-size: 14px; line-height: 1.5;">{message_text}</p>
            </div>
            <p style="margin: 24px 0 0 0; color: #666666; font-size: 14px; line-height: 1.5;">
                If you have any urgent concerns, please contact us directly at:<br/>
                <strong>Phone:</strong> 0918-912-6340 or 0918-920-5645<br/>
                <strong>Hours:</strong> Mon–Sat, 9:00 AM – 6:00 PM
            </p>
        </div>
        <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {datetime.now().year} The Elis Center. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email_async(subject, email, full_name, html_content, text_content)




def send_document_notification_email(tenant_name, tenant_email, document_title, unit_code):
    """Send notification when admin uploads a new document for tenant"""
    from datetime import datetime
    
    subject = f"New Document: {document_title} - The Elis Center"
    
    text_content = f"""
Dear {tenant_name},

A new document has been uploaded to your tenant portal: {document_title}

You can view this document by logging into your tenant dashboard.

Unit: {unit_code}

If you have any questions, please contact the administrator.

Thank you,
The Elis Center Management
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New Document Uploaded</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
        </div>
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">📄 New Document Uploaded</h2>
            <div style="background: rgba(64, 201, 64, 0.1); border: 2px solid #40c940; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                <span style="font-size: 48px; font-weight: 700; color: #40c940;">📄</span>
                <p style="margin: 12px 0 0 0; color: #40c940; font-size: 18px; font-weight: 600;">Document Available</p>
            </div>
            <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
            <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                A new document has been uploaded to your tenant portal:
            </p>
            <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B; margin: 24px 0;">
                <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Document:</strong></p>
                <p style="margin: 0 0 16px 0; color: #1a1a1a; font-size: 16px; font-weight: 600;">{document_title}</p>
                <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Unit:</strong></p>
                <p style="margin: 0; color: #1a1a1a; font-size: 16px;">{unit_code}</p>
            </div>
            <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                You can view this document by logging into your tenant dashboard.
            </p>
        </div>
        <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {datetime.now().year} The Elis Center. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email_async(subject, tenant_email, tenant_name, html_content, text_content)


def send_renewal_result_email(tenant_name, tenant_email, unit_code, status, old_end_date=None, new_end_date=None):
    """Send renewal request result email (approved/rejected)"""
    from datetime import date
    
    if status == 'approved':
        status_color = "#10b981"
        status_icon = "✓"
        status_text = "APPROVED"
        message = f"Your contract renewal request has been approved! Your new contract end date is {new_end_date.strftime('%B %d, %Y')}."
    else:
        status_color = "#ef4444"
        status_icon = "✗"
        status_text = "REJECTED"
        message = "Your contract renewal request has been rejected. Please contact the admin office for more information."
    
    subject = f"Renewal Request {status_text} - The Elis Center"
    
    text_content = f"""
Dear {tenant_name},

{message}

Unit: {unit_code}
{'Previous Contract End: ' + old_end_date.strftime('%B %d, %Y') if old_end_date and status == 'approved' else ''}
{'New Contract End: ' + new_end_date.strftime('%B %d, %Y') if new_end_date and status == 'approved' else ''}

Thank you,
The Elis Center Management
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Renewal Request {status_text}</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
        </div>
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">↻ Renewal Request {status_text}</h2>
            <div style="background: rgba({'16, 185, 129' if status == 'approved' else '239, 68, 68'}, 0.1); border: 2px solid {status_color}; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                <span style="font-size: 48px; font-weight: 700; color: {status_color};">{status_icon}</span>
                <p style="margin: 12px 0 0 0; color: {status_color}; font-size: 18px; font-weight: 600;">{status_text}</p>
            </div>
            <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
            <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                {message}
            </p>
            <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B; margin: 24px 0;">
                <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Unit:</strong></p>
                <p style="margin: 0 0 16px 0; color: #1a1a1a; font-size: 16px; font-weight: 600;">{unit_code}</p>
                {f'<p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Previous Contract End:</strong></p><p style="margin: 0 0 16px 0; color: #1a1a1a; font-size: 16px;">{old_end_date.strftime("%B %d, %Y") if old_end_date else "N/A"}</p>' if status == 'approved' else ''}
                {f'<p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>New Contract End:</strong></p><p style="margin: 0; color: #10b981; font-size: 18px; font-weight: 700;">{new_end_date.strftime("%B %d, %Y")}</p>' if status == 'approved' and new_end_date else ''}
            </div>
        </div>
        <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email_async(subject, tenant_email, tenant_name, html_content, text_content)


def send_concern_status_update_email(tenant_name, tenant_email, subject_text, status_text, unit_code):
    """Send email when concern status is updated"""
    from datetime import datetime
    
    subject = f"Concern Status Updated - {subject_text}"
    
    text_content = f"""
Dear {tenant_name},

Your concern has been updated:

Subject: {subject_text}
New Status: {status_text}
Unit: {unit_code}

You can view the full details by logging into your tenant dashboard.

Thank you,
The Elis Center Management
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Concern Status Updated</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
        </div>
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">🔔 Concern Status Updated</h2>
            <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
            <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                Your concern has been updated:
            </p>
            <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B; margin: 24px 0;">
                <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Subject:</strong></p>
                <p style="margin: 0 0 16px 0; color: #1a1a1a; font-size: 16px; font-weight: 600;">{subject_text}</p>
                <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>New Status:</strong></p>
                <p style="margin: 0 0 16px 0; color: #10b981; font-size: 16px; font-weight: 600;">{status_text}</p>
                <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Unit:</strong></p>
                <p style="margin: 0; color: #1a1a1a; font-size: 16px;">{unit_code}</p>
            </div>
            <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                You can view the full details by logging into your tenant dashboard.
            </p>
        </div>
        <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {datetime.now().year} The Elis Center. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email_async(subject, tenant_email, tenant_name, html_content, text_content)


def send_concern_response_email(tenant_name, tenant_email, subject_text, admin_response, unit_code):
    """Send email when admin responds to a concern"""
    from datetime import datetime
    
    subject = f"Admin Response - {subject_text}"
    
    text_content = f"""
Dear {tenant_name},

The administrator has responded to your concern:

Subject: {subject_text}
Unit: {unit_code}

Admin Response:
{admin_response}

You can view the full conversation by logging into your tenant dashboard.

Thank you,
The Elis Center Management
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Response</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
        </div>
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">💬 Admin Response</h2>
            <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
            <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                The administrator has responded to your concern:
            </p>
            <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B; margin: 24px 0;">
                <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Subject:</strong></p>
                <p style="margin: 0 0 16px 0; color: #1a1a1a; font-size: 16px; font-weight: 600;">{subject_text}</p>
                <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Unit:</strong></p>
                <p style="margin: 0 0 16px 0; color: #1a1a1a; font-size: 16px;">{unit_code}</p>
                <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Admin Response:</strong></p>
                <p style="margin: 0; color: #1a1a1a; font-size: 14px; line-height: 1.6;">{admin_response}</p>
            </div>
            <p style="margin: 0 0 24px 0; color: #666666; line-height: 1.6;">
                You can view the full conversation by logging into your tenant dashboard.
            </p>
        </div>
        <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {datetime.now().year} The Elis Center. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email_async(subject, tenant_email, tenant_name, html_content, text_content)


def send_inquiry_response_email(inquirer_name, inquirer_email, subject_text, admin_response):
    """Send email response to an inquiry from the contact form"""
    from datetime import datetime
    
    subject = f"Reply to Your Inquiry - {subject_text}"
    
    text_content = f"""
Dear {inquirer_name},

Thank you for your inquiry. Here is our response:

Your Inquiry: {subject_text}

Our Response:
{admin_response}

If you have any additional questions, please feel free to contact us.

Contact: 0918-912-6340 or 0918-920-5645
Hours: Mon–Sat, 9:00 AM – 6:00 PM

Thank you,
The Elis Center Management
"""
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reply to Your Inquiry</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
        </div>
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">💬 Reply to Your Inquiry</h2>
            <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{inquirer_name}</strong>,</p>
            <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                Thank you for your inquiry. Here is our response:
            </p>
            <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B; margin: 24px 0;">
                <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Your Inquiry:</strong></p>
                <p style="margin: 0 0 16px 0; color: #1a1a1a; font-size: 16px; font-weight: 600;">{subject_text}</p>
                <p style="margin: 0 0 8px 0; color: #666666; font-size: 14px;"><strong>Our Response:</strong></p>
                <p style="margin: 0; color: #1a1a1a; font-size: 14px; line-height: 1.6;">{admin_response}</p>
            </div>
            <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                If you have any additional questions, please feel free to contact us.
            </p>
            <p style="margin: 0 0 24px 0; color: #666666; font-size: 14px; line-height: 1.5;">
                <strong>Contact:</strong> 0918-912-6340 or 0918-920-5645<br/>
                <strong>Hours:</strong> Mon–Sat, 9:00 AM – 6:00 PM
            </p>
        </div>
        <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {datetime.now().year} The Elis Center. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

    send_email_async(subject, inquirer_email, inquirer_name, html_content, text_content)


def send_payment_verified_email(tenant_name, tenant_email, amount, unit_code, payment_method="cash", payment_month=None):
    """Send confirmation email when a payment is verified/recorded — whether
    admin entered it directly (cash/other) or approved a tenant-submitted
    bank transfer proof."""
    from datetime import date

    method_label = {"cash": "Cash", "bank_transfer": "Bank Transfer", "other": "Other"}.get(payment_method, "Cash")
    amount_text = f"₱{float(amount):,.2f}"
    month_text = f" for {payment_month}" if payment_month else ""

    subject = f"Payment Received - {amount_text} ({method_label})"

    text_content = f"""
Dear {tenant_name},

We've received and confirmed your payment{month_text} for Unit {unit_code}.

Amount: {amount_text}
Method: {method_label}

Thank you for your payment. You can view your full payment history and download
your official receipt anytime from your tenant portal.

Thank you,
The Elis Center Management
"""

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Received</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
        </div>
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">Payment Received</h2>
            <div style="background: rgba(16, 185, 129, 0.1); border: 2px solid #10b981; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                <p style="margin: 0; color: #059669; font-size: 32px; font-weight: 700;">{amount_text}</p>
                <p style="margin: 6px 0 0 0; color: #059669; font-size: 14px; font-weight: 600;">Confirmed{month_text}</p>
            </div>
            <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
            <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                We've received and confirmed your payment for <strong>Unit {unit_code}</strong>.
            </p>
            <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #D7B35B; margin: 24px 0;">
                <p style="margin: 0 0 4px 0; color: #666666; font-size: 13px;"><strong>Payment Method:</strong> {method_label}</p>
            </div>
            <p style="margin: 0; color: #666666; line-height: 1.6;">
                You can view your full payment history and download your official receipt anytime from your tenant portal.
            </p>
        </div>
        <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

    send_email_async(subject, tenant_email, tenant_name, html_content, text_content)


def send_payment_rejected_email(tenant_name, tenant_email, amount, unit_code, reason):
    """Send email when admin rejects a tenant-submitted bank transfer proof."""
    from datetime import date

    amount_text = f"₱{float(amount):,.2f}"
    subject = f"Payment Proof Needs Attention - {amount_text}"

    text_content = f"""
Dear {tenant_name},

Your submitted payment proof of {amount_text} for Unit {unit_code} could not be verified.

Reason: {reason}

Please review the details and resubmit your payment proof through your tenant portal.

Thank you,
The Elis Center Management
"""

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Proof Needs Attention</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <div style="background: linear-gradient(135deg, #D7B35B 0%, #C9A84A 100%); padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">The Elis Center</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255, 255, 255, 0.9); font-size: 14px;">Commercial and Residences</p>
        </div>
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; color: #1a1a1a; font-size: 20px; font-weight: 600;">Payment Proof Needs Attention</h2>
            <div style="background: rgba(239, 68, 68, 0.08); border: 2px solid #ef4444; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
                <p style="margin: 0; color: #dc2626; font-size: 28px; font-weight: 700;">{amount_text}</p>
                <p style="margin: 6px 0 0 0; color: #dc2626; font-size: 14px; font-weight: 600;">Could not be verified</p>
            </div>
            <p style="margin: 0 0 8px 0; color: #666666; line-height: 1.6;">Dear <strong>{tenant_name}</strong>,</p>
            <p style="margin: 0 0 16px 0; color: #666666; line-height: 1.6;">
                Your submitted payment proof for <strong>Unit {unit_code}</strong> could not be verified.
            </p>
            <div style="background: #f9f9f9; padding: 16px; border-radius: 8px; border-left: 4px solid #ef4444; margin: 24px 0;">
                <p style="margin: 0 0 4px 0; color: #666666; font-size: 13px;"><strong>Reason:</strong></p>
                <p style="margin: 0; color: #1a1a1a; font-size: 14px;">{reason}</p>
            </div>
            <p style="margin: 0; color: #666666; line-height: 1.6;">
                Please review the details above and resubmit your payment proof through your tenant portal.
            </p>
        </div>
        <div style="background: #fdfdfd; padding: 20px; text-align: center; border-top: 1px solid #eeeeee;">
            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {date.today().year} The Elis Center. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

    send_email_async(subject, tenant_email, tenant_name, html_content, text_content)
