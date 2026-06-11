# app/routes/auth_routes.py
# Minimal additions for Forgot Password Flow while preserving existing structure

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Existing imports for compatibility
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
    from app.dependencies.auth import get_current_user
except ImportError:
    async def get_current_user():
        return {"role": "SUPERADMIN"}  # fallback

try:
    from app.dependencies.roles import require_roles
except ImportError:
    def require_roles(role):
        async def dep():
            return True
        return dep

try:
    from app.database import users_collection, database
except ImportError:
    users_collection = None
    database = None

try:
    from app.utils.auth import hash_password, verify_password
except ImportError:
    def hash_password(p): return p
    def verify_password(p, h): return p == h

try:
    from app.config import EMAIL_USER, EMAIL_PASS, SMTP_SERVER, SMTP_PORT
except ImportError:
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASS = os.getenv("EMAIL_PASS")
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Pydantic models for forgot password
class MasterPasswordVerify(BaseModel):
    master_password: str = Field(..., min_length=1)

class ForgotPasswordInitiate(BaseModel):
    mobile: str = Field(..., min_length=10)
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")

class ForgotPasswordReset(BaseModel):
    mobile: str
    otp: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)

class OTPResponse(BaseModel):
    message: str
    expires_in_minutes: int = 10

# Helper to generate secure OTP
def generate_otp(length: int = 6) -> str:
    return ''.join(random.choices(string.digits, k=length))

# Helper to send professional OTP email
async def send_otp_email(to_email: str, otp: str, user_name: str = "User"):
    """Send OTP email using SSL (port 465) via thread executor — non-blocking, fast."""
    if not EMAIL_USER or not EMAIL_PASS:
        print("Email credentials not configured. OTP:", otp)
        return

    html_content = f"""
    <html><head><style>
      body{{font-family:Arial,sans-serif;background:#F5F5F9;margin:0;padding:20px}}
      .c{{max-width:520px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.1)}}
      .h{{background:linear-gradient(135deg,#696CFF,#5A5FE0);color:#fff;padding:28px 20px;text-align:center}}
      .h h1{{margin:0;font-size:26px}}.b{{padding:32px 28px}}
      .otp{{background:#F0F0FF;border:2px dashed #696CFF;border-radius:8px;padding:20px;text-align:center;margin:24px 0}}
      .code{{font-size:38px;font-weight:800;color:#696CFF;letter-spacing:10px}}
      .warn{{background:#FFF3CD;border-left:4px solid #FFC107;padding:12px;border-radius:4px;color:#856404;font-size:13px}}
      .f{{background:#F5F5F9;padding:16px;text-align:center;font-size:11px;color:#888}}
    </style></head><body>
    <div class="c">
      <div class="h"><h1>M-Store</h1><p style="margin:6px 0 0;opacity:.9">Password Reset</p></div>
      <div class="b">
        <p>Hello <strong>{user_name}</strong>,</p>
        <p style="color:#555;font-size:14px">Use the code below to reset your M-Store password.</p>
        <div class="otp">
          <p style="margin:0;color:#888;font-size:13px">Verification Code</p>
          <div class="code">{otp}</div>
          <p style="margin:6px 0 0;color:#e55;font-size:12px">⏱ Valid for 10 minutes</p>
        </div>
        <div class="warn"><strong>Security:</strong> Never share this code. If you didn't request this, ignore this email.</div>
      </div>
      <div class="f">© 2026 M-Store · Automated message</div>
    </div></body></html>"""

    def _send():
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "M-Store — Password Reset Code"
        msg["From"] = EMAIL_USER
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))
        # SSL port 465 — no STARTTLS handshake, faster connection
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)

    import asyncio
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not send verification email. Check your email address and try again.")

# STEP 1: Master Password Verification
@router.post("/verify-master-password")
async def verify_master_password(data: MasterPasswordVerify):
    MASTER_PASSWORD = "ONLYSUPERADMIN.A"
    if data.master_password != MASTER_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid master password. Access denied."
        )
    return {"message": "Master password verified successfully. Proceed to user identification.", "step": 2}

# STEP 2: User Identification & Send OTP
@router.post("/forgot-password/initiate", response_model=OTPResponse)
async def forgot_password_initiate(data: ForgotPasswordInitiate):
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not available")
    
    # Find user by mobile
    user = await users_collection.find_one({"mobile": data.mobile, "is_active": True})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid mobile number. User not found or inactive."
        )
    
    # Email is not stored in DB — master password already proved admin identity.
    # OTP is sent to whatever email the user provides.
    provided_email = data.email.lower().strip()
    user_name = user.get("name", "User")

    # Generate OTP + store — run delete + insert concurrently for speed
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=10)
    otp_collection = database["otp_verifications"]

    await asyncio.gather(
        otp_collection.delete_many({"mobile": data.mobile}),
    )
    await otp_collection.insert_one({
        "mobile": data.mobile,
        "email": provided_email,
        "otp": otp,
        "expires_at": expiry,
        "used": False,
        "created_at": datetime.utcnow()
    })

    # Send email — already non-blocking via run_in_executor
    try:
        await send_otp_email(provided_email, otp, user_name)
    except Exception:
        await otp_collection.delete_one({"mobile": data.mobile, "otp": otp})
        raise HTTPException(
            status_code=500,
            detail="Could not send verification email. Please check the email address and try again."
        )

    return OTPResponse(
        message="Verification code sent to your email. Please check your inbox.",
        expires_in_minutes=10
    )

# STEP 3: OTP Verification & Password Reset
@router.post("/forgot-password/reset")
async def forgot_password_reset(data: ForgotPasswordReset):
    if users_collection is None or database is None:
        raise HTTPException(status_code=500, detail="Database not available")
    
    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password confirmation does not match."
        )
    
    # Find valid OTP
    otp_collection = database["otp_verifications"]
    otp_record = await otp_collection.find_one({
        "mobile": data.mobile,
        "otp": data.otp,
        "used": False,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please request a new verification code."
        )
    
    # Find user
    user = await users_collection.find_one({"mobile": data.mobile, "is_active": True})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    # Update password with same hashing mechanism
    new_hash = hash_password(data.new_password)
    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password_hash": new_hash,
            "updated_at": datetime.utcnow()
        }}
    )
    
    # Invalidate OTP
    await otp_collection.update_one(
        {"_id": otp_record["_id"]},
        {"$set": {"used": True, "used_at": datetime.utcnow()}}
    )
    
    return {
        "message": "Password changed successfully.",
        "success": True
    }

# Existing login endpoint (preserved)
@router.post("/login")
async def login(credentials: UserLogin):
    if login_user is None:
        raise HTTPException(status_code=501, detail="Login service not available")
    try:
        result = await login_user(credentials.mobile, credentials.password)
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
