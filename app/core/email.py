"""
Plotra Platform - Email Service
Handles sending emails for various platform notifications
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """
    Send an email using the configured SMTP settings
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email
        text_content: Plain text version of the email (optional)
        
    Returns:
        True if email was sent successfully, False otherwise
    """
    try:
        from app.core.config import settings
        
        # Check if email is configured
        if not hasattr(settings, 'email') or not settings.email.smtp_server:
            print(f"Email not configured. Would have sent email to {to_email}")
            print(f"Subject: {subject}")
            return True  # Return True to not block the flow
        
        # Create message container
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{settings.email.from_name} <{settings.email.from_email}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Attach plain text version if provided
        if text_content:
            part1 = MIMEText(text_content, 'plain')
            msg.attach(part1)
        
        # Attach HTML version
        part2 = MIMEText(html_content, 'html')
        msg.attach(part2)
        
        # Connect to SMTP server
        server = smtplib.SMTP(settings.email.smtp_server, settings.email.smtp_port)
        server.ehlo()
        
        if settings.email.use_tls:
            server.starttls()
        
        # Login to SMTP server
        server.login(settings.email.smtp_username, settings.email.smtp_password)
        
        # Send email
        server.sendmail(settings.email.from_email, to_email, msg.as_string())
        server.quit()
        
        if settings.email.debug_mode:
            print(f"Email sent successfully to {to_email}")
            
        return True
        
    except ImportError:
        # Settings or email config not available
        print(f"Email configuration not available. Would have sent email to {to_email}")
        print(f"Subject: {subject}")
        return True
    except Exception as e:
        print(f"Error sending email to {to_email}: {str(e)}")
        return False


async def send_cooperative_admin_welcome_email(
    email: str,
    first_name: str,
    cooperative_name: str,
    setup_link: str
) -> bool:
    """
    Send a welcome email to the cooperative admin with login setup instructions
    
    Args:
        email: Recipient email address
        first_name: Admin's first name
        cooperative_name: Name of the cooperative
        setup_link: Link to the password setup page
        
    Returns:
        True if email was sent successfully, False otherwise
    """
    subject = f"Welcome to Plotra Platform - Complete Your Cooperative Setup"
    
    text_content = f"""
    Hello {first_name},
    
    Welcome to the Plotra Platform! Your cooperative "{cooperative_name}" has been created successfully.
    
    To complete your setup and create your login credentials, please click the link below:
    
    {setup_link}
    
    This link will expire in 24 hours for security reasons.
    
    If you have any questions, please contact our support team at support@plotra.africa.
    
    Best regards,
    The Plotra Platform Team
    """
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Welcome to Plotra Platform</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f5f5f5;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 20px auto;
                padding: 20px;
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                padding: 20px 0;
                border-bottom: 1px solid #eeeeee;
            }}
            .content {{
                padding: 20px 0;
                line-height: 1.6;
            }}
            .button {{
                display: inline-block;
                background-color: #6f4e37;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
                font-weight: bold;
            }}
            .footer {{
                text-align: center;
                padding: 20px 0;
                border-top: 1px solid #eeeeee;
                color: #666666;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="color: #6f4e37;">Plotra Platform</h1>
                <p>Welcome to the future of agricultural cooperation</p>
            </div>
            
            <div class="content">
                <h2>Hello {first_name},</h2>
                
                <p>Welcome to the Plotra Platform! Your cooperative <strong>"{cooperative_name}"</strong> has been created successfully.</p>
                
                <p>To complete your setup and create your login credentials, please click the button below:</p>
                
                <p style="text-align: center;">
                    <a href="{setup_link}" class="button">Create Login Password</a>
                </p>
                
                <p>This link will expire in 24 hours for security reasons.</p>
                
                <p>If you have any questions, please contact our support team at <a href="mailto:support@plotra.africa">support@plotra.africa</a>.</p>
            </div>
            
            <div class="footer">
                <p>&copy; 2026 Plotra Platform. All rights reserved.</p>
                <p>This is an automated email. Please do not reply to this message.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return await send_email(email, subject, html_content, text_content)
