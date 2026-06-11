# app/routes/auth_routes.py

import asyncio
import os
import random
import smtplib
import string
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# ── Internal imports (graceful fallbacks keep server alive if wiring changes) ──
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

# ── Email credentials ── read at import time so they're available immediately ──
try:
    from app.config import EMAIL_USER, EMAIL_PASS
except Exception:
    # config.py raises ValueError when MONGO_URL missing (happens in unit tests);
    # fall back to direct env read so the auth module still loads.
    EMAIL_USER = os.getenv("EMAIL_USER") or os.getenv("GMAIL_USER")
    EMAIL_PASS = os.getenv("EMAIL_PASS") or os.getenv("GMAIL_PASS")

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def _build_email_html(otp: str, user_name: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;background:#F4F5FA;margin:0;padding:20px}}
  .wrap{{max-width:520px;margin:0 auto;background:#fff;border-radius:14px;overflow:hidden;
         box-shadow:0 4px 20px rgba(95,99,242,.12)}}
  .hdr{{background:linear-gradient(135deg,#5F63F2,#4347D9);color:#fff;
        padding:32px 24px;text-align:center}}
  .hdr h1{{margin:0;font-size:24px;font-weight:800;letter-spacing:.5px}}
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
  <div class="hdr">
    <h1>M-Store</h1>
    <p>Password Reset Verification</p>
  </div>
  <div class="body">
    <p style="color:#4A5568">Hello <strong>{user_name}</strong>,</p>
    <p style="color:#4A5568;font-size:14px">
      Use the one-time code below to reset your M-Store account password.
    </p>
    <div class="otp-box">
      <div style="font-size:12px;color:#9AA5B4;text-transform:uppercase;letter-spacing:2px">
        Verification Code
      </div>
      <div class="otp-code">{otp}</div>
      <div class="otp-exp">⏱ Expires in 10 minutes</div>
    </div>
    <div class="warn">
      <strong>Security notice:</strong> Never share this code with anyone.
      M-Store staff will never ask for your OTP. If you did not request this,
      please ignore this email — your account remains secure.
    </div>
  </div>
  <div class="footer">
    © 2026 M-Store · This is an automated message, please do not reply.
  </div>
</div></body></html>"""


async def _send_otp_email(to_email: str, otp: str, user_name: str = "User") -> None:
    """
    Send OTP email via Gmail SMTP SSL (port 465).
    Runs the blocking SMTP call in a thread executor so the event loop stays free.
    Raises HTTPException 500 with a user-friendly message on failure.
    """
    # Log OTP to server console when email is not configured (dev / staging)
    if not EMAIL_USER or not EMAIL_PASS:
        print(f"[OTP - email not configured] mobile OTP: {otp}")
        return

    html = _build_email_html(otp, user_name)

    def _smtp_send() -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "M-Store — Password Reset Code"
        msg["From"]    = EMAIL_USER
        msg["To"]      = to_email
        msg.attach(MIMEText(html, "html"))
        # Use SSL on port 465 — fastest path, no STARTTLS negotiation
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as srv:
            srv.login(EMAIL_USER, EMAIL_PASS)
            srv.send_message(msg)

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _smtp_send)
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(
            status_code=500,
            detail="Email authentication failed. Please contact the administrator."
        )
    except smtplib.SMTPException as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not send verification email. Please try again later."
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Could not send verification email. Please check the email address and try again."
        )


# ── STEP 1 — Master password ──────────────────────────────────────────────────

@router.post("/verify-master-password")
async def verify_master_password(data: MasterPasswordVerify):
    if data.master_password != MASTER_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid master password. Access denied."
        )
    return {"message": "Master password verified. Proceed to user identification.", "step": 2}


# ── STEP 2 — Identify user & send OTP ────────────────────────────────────────

@router.post("/forgot-password/initiate", response_model=OTPResponse)
async def forgot_password_initiate(data: ForgotPasswordInitiate):
    if users_collection is None or database is None:
        raise HTTPException(status_code=500, detail="Database not available")

    # Verify mobile exists
    user = await users_collection.find_one({"mobile": data.mobile, "is_active": True})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mobile number not found. Please check and try again."
        )

    provided_email = data.email.lower().strip()
    user_name      = user.get("name", "User")

    # Generate OTP
    otp    = _generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=10)

    otp_col = database["otp_verifications"]

    # Invalidate old OTPs for this mobile, then insert new one
    await otp_col.delete_many({"mobile": data.mobile})
    await otp_col.insert_one({
        "mobile":     data.mobile,
        "email":      provided_email,
        "otp":        otp,
        "expires_at": expiry,
        "used":       False,
        "created_at": datetime.utcnow(),
    })

    # Send — raises HTTPException on failure (OTP already stored; user can retry)
    await _send_otp_email(provided_email, otp, user_name)

    return OTPResponse(
        message="Verification code sent to your email. Please check your inbox.",
        expires_in_minutes=10,
    )


# ── STEP 3 — Verify OTP & reset password ─────────────────────────────────────

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

    # Update password
    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(data.new_password),
                  "updated_at":    datetime.utcnow()}}
    )

    # Invalidate OTP (single-use)
    await otp_col.update_one(
        {"_id": otp_record["_id"]},
        {"$set": {"used": True, "used_at": datetime.utcnow()}}
    )

    return {"message": "Password changed successfully.", "success": True}


# ── Login ─────────────────────────────────────────────────────────────────────

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
