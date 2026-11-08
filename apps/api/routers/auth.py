# WHY: FR-AUTH-01, TR-AUTH-01, D1 — Mobile OTP Authentication with Demo Code 4821
"""Authentication router for all 4 personas (Fisher, Family, Buyer, Guard)."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import settings
from apps.api.core.database import get_db
from apps.api.models import User, FisherProfile, Harbour


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class SendOtpRequest(BaseModel):
    phone: str
    role: str = "fisher"


class VerifyOtpRequest(BaseModel):
    phone: str
    otp: str
    role: str = "fisher"
    name: Optional[str] = None
    boat_name: Optional[str] = None
    harbour_code: Optional[str] = "MALPE"
    emergency_phone: Optional[str] = None


@router.post("/send-otp")
async def send_otp(req: SendOtpRequest):
    """Simulate sending 4-digit SMS OTP (Demo OTP: 4821)."""
    clean_phone = req.phone.strip().replace("+91", "").replace(" ", "")
    if len(clean_phone) != 10 or not clean_phone.isdigit():
        raise HTTPException(status_code=400, detail="Invalid 10-digit mobile number")

    return {
        "status": "sent",
        "phone": clean_phone,
        "demo_otp": settings.demo_otp,
        "message": f"Ale code is {settings.demo_otp}",
    }


@router.post("/verify-otp")
async def verify_otp(req: VerifyOtpRequest, db: AsyncSession = Depends(get_db)):
    """Verify demo OTP 4821 and return or create user session."""
    clean_phone = req.phone.strip().replace("+91", "").replace(" ", "")
    if req.otp != settings.demo_otp:
        raise HTTPException(status_code=401, detail="Invalid OTP code. Please enter 4821.")

    # Find existing user or create
    res = await db.execute(select(User).where(User.phone == clean_phone))
    user = res.scalar_one_or_none()

    if not user:
        # Find harbour
        h_res = await db.execute(select(Harbour).where(Harbour.code == req.harbour_code))
        harbour = h_res.scalar_one_or_none()
        harbour_id = harbour.id if harbour else None

        user = User(
            phone=clean_phone,
            role=req.role,
            name=req.name or f"Fisher {clean_phone[-4:]}",
            harbour_id=harbour_id,
        )
        db.add(user)
        await db.flush()

        if req.role == "fisher":
            profile = FisherProfile(
                user_id=user.id,
                boat_name=req.boat_name or "Ale-Malpe-07",
                emergency_phone=req.emergency_phone or "9876500012",
            )
            db.add(profile)

        await db.commit()
        await db.refresh(user)

    session_token = f"ale_sess_{uuid.uuid4().hex}"
    return {
        "session_token": session_token,
        "user": {
            "id": user.id,
            "phone": user.phone,
            "role": user.role,
            "name": user.name,
            "harbour_id": user.harbour_id,
        },
    }
