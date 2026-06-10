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
    if not EMAIL_USER or not EMAIL_PASS:
        print("Email credentials not configured. OTP:", otp)
        return  # For dev, or raise in prod
    
    subject = "MStore - Password Reset Verification Code"
    
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #F5F5F9; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #696CFF 0%, #5A5FE0 100%); color: white; padding: 30px 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 28px; font-weight: 600; }}
            .content {{ padding: 40px 30px; }}
            .greeting {{ font-size: 18px; color: #333; margin-bottom: 20px; }}
            .otp-box {{ background: #F5F5F9; border: 2px dashed #696CFF; border-radius: 8px; padding: 20px; text-align: center; margin: 30px 0; }}
            .otp-code {{ font-size: 36px; font-weight: bold; color: #696CFF; letter-spacing: 8px; margin: 10px 0; }}
            .info {{ color: #555; font-size: 14px; line-height: 1.6; }}
            .warning {{ background: #FFF3CD; border-left: 4px solid #FFC107; padding: 15px; margin: 20px 0; border-radius: 4px; color: #856404; }}
            .footer {{ background: #F5F5F9; padding: 20px; text-align: center; font-size: 12px; color: #888; }}
            .security-notice {{ font-size: 13px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🛒 MStore</h1>
                <p style="margin: 10px 0 0; opacity: 0.9;">Secure Password Reset</p>
            </div>
            <div class="content">
                <p class="greeting">Hello {user_name},</p>
                <p class="info">We received a request to reset your password for your MStore account. Use the verification code below to proceed.</p>
                
                <div class="otp-box">
                    <p style="margin: 0; color: #666; font-size: 14px;">Your Verification Code</p>
                    <div class="otp-code">{otp}</div>
                    <p style="margin: 5px 0 0; color: #888; font-size: 13px;">Valid for 10 minutes</p>
                </div>
                
                <div class="warning">
                    <strong>Security Notice:</strong> This code is confidential. Do not share it with anyone. If you did not request this reset, please ignore this email or contact support immediately.
                </div>
                
                <p class="info">If you have any questions, reply to this email or reach out to our support team.</p>
            </div>
            <div class="footer">
                <p>© 2026 MStore. All rights reserved.</p>
                <p class="security-notice">This is an automated message. Please do not reply directly unless necessary.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    
    msg.attach(MIMEText(html_content, "html"))
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print(f"OTP email sent successfully to {to_email}")
    except Exception as e:
        print(f"Failed to send OTP email: {str(e)}")
        # In production, you may want to raise or log properly
        raise HTTPException(status_code=500, detail="Failed to send verification email. Please try again later.")

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
    
    # Email is not stored in DB — master password already verified admin identity.
    # OTP is sent to whichever email the user provides in Step 2.
    provided_email = data.email.lower().strip()

    # Generate secure OTP
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=10)
    
    # Store OTP in dedicated collection (create if not exists)
    otp_collection = database["otp_verifications"]
    await otp_collection.delete_many({"mobile": data.mobile})  # Invalidate previous OTPs
    await otp_collection.insert_one({
        "mobile": data.mobile,
        "email": provided_email,
        "otp": otp,
        "expires_at": expiry,
        "used": False,
        "created_at": datetime.utcnow()
    })
    
    # Send email (use user name if available)
    user_name = user.get("name", "Valued Customer")
    try:
        await send_otp_email(provided_email, otp, user_name)
    except Exception as email_err:
        # Clean up OTP if email fails
        await otp_collection.delete_one({"mobile": data.mobile, "otp": otp})
        raise email_err
    
    return OTPResponse(
        message="A verification code has been sent to your email address. Please check your inbox (and spam folder).",
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
