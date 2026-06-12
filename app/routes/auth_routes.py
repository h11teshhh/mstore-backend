# app/routes/auth_routes.py
#
# EMAIL DELIVERY STRATEGY (in order of preference):
#   1. Gmail SMTP port 587 (STARTTLS) — works if Render allows outbound 587
#   2. Brevo (Sendinblue) HTTP API  — works on ALL networks (HTTPS port 443)
#      Free tier: 300 emails/day, no credit card required
#      Set BREVO_API_KEY env var on Render to enable
#   3. Console fallback             — OTP printed to Render logs for admin use

import asyncio
import json
import os
import random
import smtplib
import ssl
import string
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# ── Internal imports ──────────────────────────────────────────────────────────
try:
    from app.services.auth_service import login_user
except ImportError:
    login_user = None

try:
    from app.schemas.user import UserLogin
except ImportError:
    class UserLogin(BaseModel):
        mobile: str
        password: str

try:
    from app.database import users_collection, database
except ImportError:
    users_collection = None
    database = None

try:
    from app.utils.auth import hash_password
except ImportError:
    def hash_password(p): return p

# ── Email credentials (read at import time) ───────────────────────────────────
EMAIL_USER    = None
EMAIL_PASS    = None
BREVO_API_KEY = None

try:
    from app.config import EMAIL_USER, EMAIL_PASS          # type: ignore
except Exception:
    pass

if not EMAIL_USER:
    EMAIL_USER = os.getenv("EMAIL_USER") or os.getenv("GMAIL_USER")
if not EMAIL_PASS:
    EMAIL_PASS = os.getenv("EMAIL_PASS") or os.getenv("GMAIL_PASS")

BREVO_API_KEY = os.getenv("BREVO_API_KEY") or os.getenv("SENDINBLUE_API_KEY")

MASTER_PASSWORD = "ONLYSUPERADMIN.A"
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Pydantic models ───────────────────────────────────────────────────────────

class MasterPasswordVerify(BaseModel):
    master_password: str = Field(..., min_length=1)

class ForgotPasswordInitiate(BaseModel):
    mobile: str = Field(..., min_length=10, max_length=15)
    email:  str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class ForgotPasswordReset(BaseModel):
    mobile:           str = Field(..., min_length=10)
    otp:              str = Field(..., min_length=4, max_length=8)
    new_password:     str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)

class OTPResponse(BaseModel):
    message:            str
    expires_in_minutes: int = 10


# ── Email HTML template ───────────────────────────────────────────────────────

def _build_email_html(otp: str, user_name: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;background:#F4F5FA;margin:0;padding:20px}}
  .wrap{{max-width:520px;margin:0 auto;background:#fff;border-radius:14px;overflow:hidden;
         box-shadow:0 4px 20px rgba(95,99,242,.12)}}
  .hdr{{background:linear-gradient(135deg,#5F63F2,#4347D9);color:#fff;padding:32px 24px;text-align:center}}
  .hdr h1{{margin:0;font-size:24px;font-weight:800}}
  .hdr p{{margin:6px 0 0;opacity:.85;font-size:14px}}
  .body{{padding:32px 28px}}
  .otp-box{{background:#EEEEFF;border:2px dashed #5F63F2;border-radius:10px;
            padding:24px;text-align:center;margin:20px 0}}
  .otp-code{{font-size:40px;font-weight:900;color:#5F63F2;letter-spacing:10px}}
  .otp-exp{{font-size:12px;color:#D93025;margin-top:8px}}
  .warn{{background:#FFF8E6;border-left:4px solid #F59E0B;border-radius:6px;
         padding:12px 14px;font-size:12px;color:#7A5C00}}
  .footer{{background:#F4F5FA;padding:18px;text-align:center;font-size:11px;color:#9AA5B4}}
</style></head>
<body><div class="wrap">
  <div class="hdr"><h1>M-Store</h1><p>Password Reset Verification</p></div>
  <div class="body">
    <p style="color:#4A5568">Hello <strong>{user_name}</strong>,</p>
    <p style="color:#4A5568;font-size:14px">Your one-time password reset code:</p>
    <div class="otp-box">
      <div style="font-size:12px;color:#9AA5B4;text-transform:uppercase;letter-spacing:2px">Verification Code</div>
      <div class="otp-code">{otp}</div>
      <div class="otp-exp">&#9201; Expires in 10 minutes</div>
    </div>
    <div class="warn"><strong>Security notice:</strong> Never share this code.
      If you did not request this, ignore this email.</div>
  </div>
  <div class="footer">&copy; 2026 M-Store &middot; Automated message, do not reply.</div>
</div></body></html>"""


# ── Email sending strategies ──────────────────────────────────────────────────

def _try_gmail_smtp(to_email: str, subject: str, html: str) -> bool:
    """
    Attempt Gmail SMTP via port 587 (STARTTLS).
    Returns True on success, False on network/connection failure.
    Raises on auth failure (no point retrying with wrong credentials).
    """
    if not EMAIL_USER or not EMAIL_PASS:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_USER
        msg["To"]      = to_email
        msg.attach(MIMEText(html, "html"))
        ctx = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as srv:
            srv.ehlo()
            srv.starttls(context=ctx)
            srv.ehlo()
            srv.login(EMAIL_USER, EMAIL_PASS)
            srv.sendmail(EMAIL_USER, to_email, msg.as_string())
        print(f"[OTP-EMAIL] Sent via Gmail SMTP 587 to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as exc:
        print(f"[OTP-EMAIL-ERR] Gmail auth failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Email authentication failed. Please contact the administrator."
        )
    except (OSError, smtplib.SMTPException) as exc:
        # Network blocked or connection refused — try next method
        print(f"[OTP-EMAIL-WARN] Gmail SMTP 587 blocked/failed: {type(exc).__name__}: {exc}")
        return False


def _try_gmail_smtp_ssl(to_email: str, subject: str, html: str) -> bool:
    """
    Attempt Gmail SMTP via port 465 (SSL). Secondary Gmail attempt.
    Returns True on success, False on network failure.
    """
    if not EMAIL_USER or not EMAIL_PASS:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_USER
        msg["To"]      = to_email
        msg.attach(MIMEText(html, "html"))
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=20) as srv:
            srv.login(EMAIL_USER, EMAIL_PASS)
            srv.sendmail(EMAIL_USER, to_email, msg.as_string())
        print(f"[OTP-EMAIL] Sent via Gmail SMTP 465 to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as exc:
        print(f"[OTP-EMAIL-ERR] Gmail SSL auth failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Email authentication failed. Please contact the administrator."
        )
    except (OSError, smtplib.SMTPException) as exc:
        print(f"[OTP-EMAIL-WARN] Gmail SMTP 465 blocked/failed: {type(exc).__name__}: {exc}")
        return False


def _try_brevo_api(to_email: str, to_name: str, subject: str, html: str) -> bool:
    """
    Send via Brevo (Sendinblue) REST API over HTTPS port 443.
    Always works on Render — no SMTP ports required.
    Free tier: 300 emails/day. Get key at: https://app.brevo.com/settings/keys/api
    Set env var: BREVO_API_KEY=xkeysib-...
    Returns True on success, False if key not configured.
    Raises HTTPException on API error.
    """
    if not BREVO_API_KEY:
        print("[OTP-EMAIL-WARN] BREVO_API_KEY not set — skipping Brevo")
        return False

    sender_name  = "M-Store"
    sender_email = EMAIL_USER or "nilkanthtraders82@gmail.com"

    payload = json.dumps({
        "sender":     {"name": sender_name, "email": sender_email},
        "to":         [{"email": to_email, "name": to_name}],
        "subject":    subject,
        "htmlContent": html,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=payload,
        headers={
            "accept":       "application/json",
            "content-type": "application/json",
            "api-key":      BREVO_API_KEY,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp_body = resp.read().decode("utf-8")
            print(f"[OTP-EMAIL] Sent via Brevo API to {to_email}: {resp_body}")
            return True
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"[OTP-EMAIL-ERR] Brevo HTTP {exc.code}: {body}")
        raise HTTPException(
            status_code=500,
            detail="Could not send verification email. Please try again."
        )
    except urllib.error.URLError as exc:
        print(f"[OTP-EMAIL-ERR] Brevo network error: {exc.reason}")
        return False


async def _send_otp_email(to_email: str, otp: str, user_name: str = "User") -> None:
    """
    Multi-path OTP email sender.
    Path 1: Gmail SMTP port 587 (STARTTLS)
    Path 2: Gmail SMTP port 465 (SSL)
    Path 3: Brevo HTTP API (always works on Render)
    Path 4: Console log (dev/admin fallback)
    """
    subject = "M-Store — Password Reset Code"
    html    = _build_email_html(otp, user_name)

    def _send_sync() -> bool:
        # Try Gmail 587 first
        if _try_gmail_smtp(to_email, subject, html):
            return True
        # Try Gmail 465
        if _try_gmail_smtp_ssl(to_email, subject, html):
            return True
        # Try Brevo HTTP API
        if _try_brevo_api(to_email, user_name, subject, html):
            return True
        # All delivery paths failed — log to console
        print(f"[OTP-CONSOLE-FALLBACK] ===== OTP for {to_email}: {otp} =====")
        print("[OTP-CONSOLE-FALLBACK] Set BREVO_API_KEY env var to enable reliable email delivery")
        return False

    try:
        loop    = asyncio.get_running_loop()
        success = await loop.run_in_executor(None, _send_sync)
        if not success:
            # Email delivery unavailable but OTP is stored in DB
            # Raise so user knows to check with admin
            raise HTTPException(
                status_code=503,
                detail=(
                    "Email service is currently unavailable. "
                    "Please contact the administrator — the reset code "
                    "has been generated and can be retrieved from server logs."
                )
            )
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[OTP-EMAIL-ERR] Unexpected error: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again."
        )


# ── OTP generator ─────────────────────────────────────────────────────────────

def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/verify-master-password")
async def verify_master_password(data: MasterPasswordVerify):
    if data.master_password != MASTER_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid master password. Access denied."
        )
    return {"message": "Master password verified.", "step": 2}


@router.post("/forgot-password/initiate", response_model=OTPResponse)
async def forgot_password_initiate(data: ForgotPasswordInitiate):
    if users_collection is None or database is None:
        raise HTTPException(status_code=500, detail="Database not available")

    user = await users_collection.find_one({"mobile": data.mobile, "is_active": True})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mobile number not found. Please check and try again."
        )

    provided_email = data.email.lower().strip()
    user_name      = user.get("name", "User")
    otp            = _generate_otp()
    expiry         = datetime.utcnow() + timedelta(minutes=10)
    otp_col        = database["otp_verifications"]

    await otp_col.delete_many({"mobile": data.mobile})
    await otp_col.insert_one({
        "mobile":     data.mobile,
        "email":      provided_email,
        "otp":        otp,
        "expires_at": expiry,
        "used":       False,
        "created_at": datetime.utcnow(),
    })

    await _send_otp_email(provided_email, otp, user_name)

    return OTPResponse(
        message="Verification code sent. Please check your inbox.",
        expires_in_minutes=10,
    )


@router.post("/forgot-password/reset")
async def forgot_password_reset(data: ForgotPasswordReset):
    if users_collection is None or database is None:
        raise HTTPException(status_code=500, detail="Database not available")

    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match. Please try again."
        )

    otp_col    = database["otp_verifications"]
    otp_record = await otp_col.find_one({
        "mobile":     data.mobile,
        "otp":        data.otp,
        "used":       False,
        "expires_at": {"$gt": datetime.utcnow()},
    })
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code. Please request a new one."
        )

    user = await users_collection.find_one({"mobile": data.mobile, "is_active": True})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(data.new_password),
                  "updated_at":    datetime.utcnow()}}
    )
    await otp_col.update_one(
        {"_id": otp_record["_id"]},
        {"$set": {"used": True, "used_at": datetime.utcnow()}}
    )
    return {"message": "Password changed successfully.", "success": True}


@router.post("/login")
async def login(credentials: UserLogin):
    if login_user is None:
        raise HTTPException(status_code=501, detail="Login service unavailable")
    try:
        return await login_user(credentials.mobile, credentials.password)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
