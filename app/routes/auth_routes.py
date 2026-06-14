# app/routes/auth_routes.py
#
# EMAIL DELIVERY — Brevo HTTP API first (always works on Render, port 443)
# Falls back to Gmail SMTP (may be blocked), then console log.
# Brevo requires sender email/domain to be verified in Brevo dashboard.

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

# ── Email credentials — read once at module import ────────────────────────────
EMAIL_USER    = None
EMAIL_PASS    = None
BREVO_API_KEY = None

try:
    from app.config import EMAIL_USER, EMAIL_PASS   # type: ignore
except Exception:
    pass

if not EMAIL_USER:
    EMAIL_USER = os.getenv("EMAIL_USER") or os.getenv("GMAIL_USER")
if not EMAIL_PASS:
    EMAIL_PASS = os.getenv("EMAIL_PASS") or os.getenv("GMAIL_PASS")

BREVO_API_KEY = (
    os.getenv("BREVO_API_KEY")
    or os.getenv("SENDINBLUE_API_KEY")
    or os.getenv("BREVO_KEY")
)

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
  .wrap{{max-width:520px;margin:0 auto;background:#fff;border-radius:14px;
         overflow:hidden;box-shadow:0 4px 20px rgba(79,82,201,.12)}}
  .hdr{{background:linear-gradient(135deg,#4F52C9,#3A3DA8);color:#fff;
        padding:32px 24px;text-align:center}}
  .hdr h1{{margin:0;font-size:24px;font-weight:800}}
  .hdr p{{margin:6px 0 0;opacity:.85;font-size:14px}}
  .body{{padding:32px 28px}}
  .otp-box{{background:#EEEEFF;border:2px dashed #4F52C9;border-radius:10px;
            padding:24px;text-align:center;margin:20px 0}}
  .otp-code{{font-size:40px;font-weight:900;color:#4F52C9;letter-spacing:10px}}
  .otp-exp{{font-size:12px;color:#B91C1C;margin-top:8px}}
  .warn{{background:#FFF8E6;border-left:4px solid #D97706;border-radius:6px;
         padding:12px 14px;font-size:12px;color:#7A5C00}}
  .footer{{background:#F4F5FA;padding:18px;text-align:center;
           font-size:11px;color:#6B7280}}
</style></head>
<body><div class="wrap">
  <div class="hdr"><h1>M-Store</h1><p>Password Reset Verification</p></div>
  <div class="body">
    <p style="color:#111827">Hello <strong>{user_name}</strong>,</p>
    <p style="color:#374151;font-size:14px">
      Use the code below to reset your M-Store account password.
    </p>
    <div class="otp-box">
      <div style="font-size:12px;color:#6B7280;text-transform:uppercase;
                  letter-spacing:2px">Verification Code</div>
      <div class="otp-code">{otp}</div>
      <div class="otp-exp">&#9201; Expires in 10 minutes</div>
    </div>
    <div class="warn">
      <strong>Security notice:</strong> Never share this code.
      If you did not request this, ignore this email.
    </div>
  </div>
  <div class="footer">&copy; 2026 M-Store &middot; Automated message, do not reply.</div>
</div></body></html>"""


# ── Email sending functions (all synchronous — run in executor) ───────────────

class _EmailError(Exception):
    """Raised when email fails with a user-facing message."""
    def __init__(self, detail: str, status_code: int = 500):
        self.detail      = detail
        self.status_code = status_code
        super().__init__(detail)


def _send_via_brevo(
    to_email: str, to_name: str, subject: str, html: str
) -> None:
    """
    Send via Brevo REST API (HTTPS port 443 — works on ALL networks).
    Raises _EmailError on failure.

    IMPORTANT: The sender email (EMAIL_USER) must be verified in the Brevo
    dashboard under Senders & Domains, otherwise Brevo returns 400.
    """
    if not BREVO_API_KEY:
        raise _EmailError("BREVO_API_KEY not configured", 503)

    sender_email = EMAIL_USER or "nilkanthtraders82@gmail.com"

    # Log what we're sending for easier Render debugging
    print(f"[BREVO] Attempting send from {sender_email} to {to_email}")
    print(f"[BREVO] API key prefix: {BREVO_API_KEY[:12]}...")

    payload = json.dumps({
        "sender":      {"name": "M-Store", "email": sender_email},
        "to":          [{"email": to_email, "name": to_name or "User"}],
        "subject":     subject,
        "htmlContent": html,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data    = payload,
        headers = {
            "accept":        "application/json",
            "content-type":  "application/json",
            "api-key":       BREVO_API_KEY,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8")
            print(f"[BREVO] Success: {body}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"[BREVO-ERR] HTTP {exc.code}: {body}")
        # Parse Brevo error for actionable messages
        try:
            err = json.loads(body)
            msg = err.get("message", body)
        except Exception:
            msg = body
        if exc.code == 401:
            raise _EmailError(
                "Email API key is invalid. Please contact the administrator.", 500)
        if exc.code == 400 and "sender" in msg.lower():
            raise _EmailError(
                "The sender email is not verified in Brevo. "
                "Please verify nilkanthtraders82@gmail.com in the Brevo dashboard "
                "(Senders & Domains → Add a sender).", 500)
        raise _EmailError(
            f"Email service error ({exc.code}). Please try again later.", 500)
    except urllib.error.URLError as exc:
        print(f"[BREVO-ERR] Network: {exc.reason}")
        raise _EmailError("Cannot reach email service. Please try again.", 503)


def _send_via_gmail_starttls(subject: str, html: str, to_email: str) -> None:
    """Gmail SMTP port 587 — may be blocked on Render free tier."""
    if not (EMAIL_USER and EMAIL_PASS):
        raise _EmailError("Gmail credentials not configured", 503)
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_USER
        msg["To"]      = to_email
        msg.attach(MIMEText(html, "html"))
        ctx = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=8) as srv:
            srv.ehlo(); srv.starttls(context=ctx); srv.ehlo()
            srv.login(EMAIL_USER, EMAIL_PASS)
            srv.sendmail(EMAIL_USER, to_email, msg.as_string())
        print(f"[GMAIL-587] Sent to {to_email}")
    except smtplib.SMTPAuthenticationError:
        raise _EmailError("Gmail authentication failed. Check credentials.", 500)
    except (OSError, smtplib.SMTPException) as e:
        print(f"[GMAIL-587-WARN] {type(e).__name__}: {e}")
        raise _EmailError("Gmail SMTP blocked or unavailable.", 503)


def _send_sync_all(
    to_email: str, to_name: str, otp: str, subject: str, html: str
) -> None:
    """
    Try delivery paths in order. Brevo first (reliable on Render).
    Falls through to Gmail only if Brevo not configured.
    """
    last_error: _EmailError | None = None

    # ── Path 1: Brevo HTTP API ───────────────────────────────────────────────
    if BREVO_API_KEY:
        try:
            _send_via_brevo(to_email, to_name, subject, html)
            return   # success — stop here
        except _EmailError as e:
            last_error = e
            print(f"[EMAIL] Brevo failed: {e.detail}")

    # ── Path 2: Gmail SMTP 587 ───────────────────────────────────────────────
    if EMAIL_USER and EMAIL_PASS:
        try:
            _send_via_gmail_starttls(subject, html, to_email)
            return   # success
        except _EmailError as e:
            last_error = e
            print(f"[EMAIL] Gmail SMTP 587 failed: {e.detail}")

    # ── Path 3: Console fallback ─────────────────────────────────────────────
    print(f"[OTP-FALLBACK] ===========================")
    print(f"[OTP-FALLBACK] OTP for {to_email}: {otp}")
    print(f"[OTP-FALLBACK] ===========================")
    print(f"[OTP-FALLBACK] Configure BREVO_API_KEY on Render to send emails.")

    # All paths failed — tell user
    if last_error:
        raise last_error
    raise _EmailError(
        "Email service not configured. Please contact the administrator.", 503)


async def _send_otp_email(to_email: str, otp: str, user_name: str = "User") -> None:
    subject = "M-Store — Password Reset Code"
    html    = _build_email_html(otp, user_name)

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(
            None, _send_sync_all, to_email, user_name, otp, subject, html
        )
    except _EmailError as exc:
        # Convert our internal error to FastAPI HTTPException
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception as exc:
        print(f"[EMAIL-ERR] Unexpected: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Could not send verification email. Please try again."
        )


# ── Helper ────────────────────────────────────────────────────────────────────

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

    # Send email — raises HTTPException on failure
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
