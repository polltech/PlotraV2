"""
Plotra Platform - Email Service
Sends emails via Resend HTTP API (bypasses SMTP port restrictions)
"""
import httpx
from typing import Optional
from app.core.config import settings

RESEND_API_URL = "https://api.resend.com/emails"


async def _get_resend_key() -> str:
    """Read Resend API key from DB config first, fall back to env var."""
    try:
        from app.core.database import async_session_factory
        from app.models.system import SystemConfig
        from sqlalchemy import select
        async with async_session_factory() as session:
            result = await session.execute(
                select(SystemConfig).where(SystemConfig.config_key == "cfg_email_resend_api_key")
            )
            cfg = result.scalar_one_or_none()
            if cfg and cfg.config_value and cfg.config_value not in ("", "***"):
                return cfg.config_value
    except Exception:
        pass
    return settings.email.resend_api_key


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    api_key = await _get_resend_key()
    if not api_key:
        print(f"[Email] RESEND_API_KEY not set — skipping email to {to_email}")
        return False

    payload = {
        "from": f"{settings.email.from_name} <{settings.email.from_email}>",
        "to": [to_email],
        "subject": subject,
        "html": html_content,
    }
    if text_content:
        payload["text"] = text_content

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        if resp.status_code in (200, 201):
            if settings.email.debug_mode:
                print(f"[Email] Sent to {to_email}: {resp.json()}")
            return True
        else:
            print(f"[Email] Failed to send to {to_email}: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"[Email] Error sending to {to_email}: {e}")
        return False


async def send_cooperative_admin_welcome_email(
    email: str,
    first_name: str,
    cooperative_name: str,
    setup_link: str
) -> bool:
    subject = "Welcome to Plotra Platform - Complete Your Cooperative Setup"
    text_content = f"""Hello {first_name},

Welcome to the Plotra Platform! Your cooperative "{cooperative_name}" has been created successfully.

To complete your setup, click the link below:
{setup_link}

This link expires in 24 hours.

Best regards,
The Plotra Platform Team"""

    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:0;">
  <div style="max-width:600px;margin:20px auto;padding:20px;background:#fff;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,.1);">
    <div style="text-align:center;padding:20px 0;border-bottom:1px solid #eee;">
      <h1 style="color:#6f4e37;">Plotra Platform</h1>
    </div>
    <div style="padding:20px 0;line-height:1.6;">
      <h2>Hello {first_name},</h2>
      <p>Welcome to the Plotra Platform! Your cooperative <strong>"{cooperative_name}"</strong> has been created successfully.</p>
      <p>To complete your setup and create your login credentials:</p>
      <p style="text-align:center;">
        <a href="{setup_link}" style="display:inline-block;background:#6f4e37;color:#fff;padding:12px 24px;text-decoration:none;border-radius:4px;font-weight:bold;">Create Login Password</a>
      </p>
      <p>This link expires in 24 hours.</p>
      <p>Questions? Contact <a href="mailto:support@plotra.africa">support@plotra.africa</a></p>
    </div>
    <div style="text-align:center;padding:20px 0;border-top:1px solid #eee;color:#666;font-size:14px;">
      <p>&copy; 2026 Plotra Platform. All rights reserved.</p>
    </div>
  </div>
</body>
</html>"""

    return await send_email(email, subject, html_content, text_content)


async def send_cooperative_contact_welcome_email(
    email: str,
    contact_person: str,
    cooperative_name: str,
    setup_link: str
) -> bool:
    subject = "Welcome to Plotra Platform - Cooperative Contact Person"
    text_content = f"""Hello {contact_person},

You have been designated as the contact person for cooperative "{cooperative_name}" on the Plotra Platform.

To create your login credentials:
{setup_link}

This link expires in 24 hours.

Best regards,
The Plotra Platform Team"""

    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:0;">
  <div style="max-width:600px;margin:20px auto;padding:20px;background:#fff;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,.1);">
    <div style="text-align:center;padding:20px 0;border-bottom:1px solid #eee;">
      <h1 style="color:#6f4e37;">Plotra Platform</h1>
    </div>
    <div style="padding:20px 0;line-height:1.6;">
      <h2>Hello {contact_person},</h2>
      <p>You have been designated as the contact person for cooperative <strong>"{cooperative_name}"</strong>.</p>
      <p style="text-align:center;">
        <a href="{setup_link}" style="display:inline-block;background:#6f4e37;color:#fff;padding:12px 24px;text-decoration:none;border-radius:4px;font-weight:bold;">Create Login Password</a>
      </p>
      <p>This link expires in 24 hours.</p>
    </div>
    <div style="text-align:center;padding:20px 0;border-top:1px solid #eee;color:#666;font-size:14px;">
      <p>&copy; 2026 Plotra Platform. All rights reserved.</p>
    </div>
  </div>
</body>
</html>"""

    return await send_email(email, subject, html_content, text_content)
