# WHY: FR-DIR-01, FR-VOX-04, D12, G4 — Earnings Diary Ledger with Idempotent Entry Logging
"""Fisher earnings diary: tap & voice financial records with offline client_op_id safety."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from apps.api.models import User, LedgerEntry


router = APIRouter(prefix="/api/v1/diary", tags=["diary"])


class AddEntryRequest(BaseModel):
    phone: str = "9876500021"
    entry_type: str  # "sale" or "expense"
    amount: float
    description: str
    quantity_kg: Optional[float] = None
    client_op_id: Optional[str] = None


@router.get("/summary")
async def get_diary_summary(
    phone: str = "9876500021",
    db: AsyncSession = Depends(get_db),
):
    """Retrieve financial summary for the week: Sold, Fuel, Kept."""
    u_res = await db.execute(select(User).where(User.phone == phone))
    user = u_res.scalar_one_or_none()
    user_id = user.id if user else None

    # Fetch entries
    if user_id:
        q = select(LedgerEntry).where(LedgerEntry.user_id == user_id).order_by(LedgerEntry.created_at.desc())
    else:
        q = select(LedgerEntry).order_by(LedgerEntry.created_at.desc())

    res = await db.execute(q)
    entries = res.scalars().all()

    total_sold = sum(e.amount for e in entries if e.entry_type == "sale")
    total_fuel = sum(e.amount for e in entries if e.entry_type == "expense")
    total_kept = total_sold - total_fuel

    recent_logs = [
        f"{'＋' if e.entry_type == 'sale' else '⛽'} ₹{int(e.amount):,} · {e.description}"
        for e in entries[:5]
    ]

    return {
        "sold": total_sold,
        "fuel": total_fuel,
        "kept": total_kept,
        "sold_display": f"₹{int(total_sold):,}",
        "fuel_display": f"₹{int(total_fuel):,}",
        "kept_display": f"₹{int(total_kept):,}",
        "recent_logs": recent_logs,
        "weekly_bars": [
            {"day": "M", "height_pct": 45},
            {"day": "T", "height_pct": 70},
            {"day": "W", "height_pct": 30},
            {"day": "T", "height_pct": 90},
            {"day": "F", "height_pct": 60},
            {"day": "S", "height_pct": 100},
        ],
    }


@router.post("/entries")
async def add_diary_entry(req: AddEntryRequest, db: AsyncSession = Depends(get_db)):
    """Add a financial transaction with client_op_id idempotency (G4)."""
    op_id = req.client_op_id or f"ledger_{uuid.uuid4().hex}"

    # Check for duplicate idempotency key
    dup = await db.execute(select(LedgerEntry).where(LedgerEntry.client_op_id == op_id))
    if dup.scalar_one_or_none():
        return {
            "status": "already_recorded",
            "client_op_id": op_id,
            "message": "Transaction already recorded in ledger.",
        }

    u_res = await db.execute(select(User).where(User.phone == req.phone))
    user = u_res.scalar_one_or_none()
    user_id = user.id if user else str(uuid.uuid4())

    entry = LedgerEntry(
        user_id=user_id,
        entry_type=req.entry_type,
        amount=req.amount,
        description=req.description,
        quantity_kg=req.quantity_kg,
        client_op_id=op_id,
    )
    db.add(entry)
    await db.commit()

    return {
        "status": "recorded",
        "entry_id": entry.id,
        "client_op_id": op_id,
        "amount": req.amount,
        "entry_type": req.entry_type,
    }
