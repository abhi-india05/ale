# WHY: FR-FAM-01, TR-FAM-01, G3 — Family Connected View & Boat Status
"""Family view endpoint showing real-time boat progress and emergency alerts."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from apps.api.models import User, Trip, Alert, SosEvent


router = APIRouter(prefix="/api/v1/family", tags=["family"])


@router.get("/status")
async def get_family_status(db: AsyncSession = Depends(get_db)):
    """Retrieve boat safety status and active voyage step for family view."""
    # Check for active SOS
    sos_res = await db.execute(select(SosEvent).where(SosEvent.status == "active").limit(1))
    active_sos = sos_res.scalar_one_or_none()

    # Check for active trip
    trip_res = await db.execute(select(Trip).order_by(Trip.created_at.desc()).limit(1))
    trip = trip_res.scalar_one_or_none()

    step_idx = 0
    emoji = "⛵"
    title = "Boat is out at sea"
    subtitle = "Safe zone · last seen 2 min ago"
    alert_banner = None
    alert_type = None

    if active_sos:
        alert_banner = "🚨 SOS from Suresh. Coast guard and nearby boats alerted."
        alert_type = "red"
    elif trip:
        if trip.status == "returning":
            step_idx = 1
            emoji = "🧭"
            title = "Boat is returning"
            subtitle = "Arriving in about 40 minutes"
        elif trip.status == "landed":
            step_idx = 2
            emoji = "⚓"
            title = "Boat has landed"
            subtitle = "Suresh is safe at Malpe"
        elif trip.status == "overdue":
            alert_banner = "⏰ Overdue: expected return time has passed. Coast Guard notified."
            alert_type = "amber"

    return {
        "step_index": step_idx,
        "emoji": emoji,
        "title": title,
        "subtitle": subtitle,
        "alert_banner": alert_banner,
        "alert_type": alert_type,
        "fisher_name": "Suresh",
        "fisher_phone": "9876500021",
        "boat_name": "Ale-Malpe-07",
    }
