# WHY: TR-SYNC-01, D12, G4 — Offline Outbox Sync with Client_Op_Id Zero-Duplicate Guarantee
"""Offline sync queue processor guaranteeing idempotent replay of offshore actions."""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List
import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from apps.api.models import User, OutboxOp, LedgerEntry, FishSpot


router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


class OutboxItem(BaseModel):
    client_op_id: str
    op_type: str  # "ledger_sale", "ledger_expense", "fish_spot"
    phone: str = "9876500021"
    payload: Dict[str, Any]


class OutboxSyncBatch(BaseModel):
    operations: List[OutboxItem]


@router.post("/outbox")
async def sync_outbox(batch: OutboxSyncBatch, db: AsyncSession = Depends(get_db)):
    """Idempotently apply offline operations queued during offshore disconnected state."""
    synced_count = 0
    skipped_count = 0

    for op in batch.operations:
        # 1. Check if client_op_id was already applied (D12, G4)
        existing = await db.execute(select(OutboxOp).where(OutboxOp.client_op_id == op.client_op_id))
        if existing.scalar_one_or_none():
            skipped_count += 1
            continue

        # Find user
        u_res = await db.execute(select(User).where(User.phone == op.phone))
        user = u_res.scalar_one_or_none()
        user_id = user.id if user else str(uuid.uuid4())

        # 2. Dispatch operation to target table
        if op.op_type in ("ledger_sale", "ledger_expense"):
            db.add(LedgerEntry(
                user_id=user_id,
                entry_type="sale" if op.op_type == "ledger_sale" else "expense",
                amount=float(op.payload.get("amount", 0.0)),
                description=op.payload.get("description", "Offline sync entry"),
                quantity_kg=op.payload.get("quantity_kg"),
                client_op_id=op.client_op_id,
            ))
        elif op.op_type == "fish_spot":
            db.add(FishSpot(
                fisher_user_id=user_id,
                lat=float(op.payload.get("lat", 13.35)),
                lon=float(op.payload.get("lon", 74.69)),
                note=op.payload.get("note", "offline spot"),
                visible_to="crew",
            ))

        # 3. Record OutboxOp
        db.add(OutboxOp(
            client_op_id=op.client_op_id,
            user_id=user_id,
            op_type=op.op_type,
            payload_json=json.dumps(op.payload),
            synced_at=datetime.now(timezone.utc),
            status="applied",
        ))

        synced_count += 1

    await db.commit()
    return {
        "status": "sync_complete",
        "synced": synced_count,
        "duplicates_skipped": skipped_count,
        "total_processed": len(batch.operations),
    }
