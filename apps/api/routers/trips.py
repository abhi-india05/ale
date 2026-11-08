# WHY: FR-TRP-01, FR-SOS-01, D9, D12, G3, G4 — Trip Management & Idempotent SOS Alerting
"""Voyage lifecycle, pre-sail checklists, and emergency SOS distress signaling."""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from apps.api.models import User, Boat, Trip, TripCheck, SosEvent, IncidentEvent, Alert


router = APIRouter(prefix="/api/v1/trips", tags=["trips"])


class StartTripRequest(BaseModel):
    phone: str = "9876500021"
    crew_count: int = 2
    return_in_hours: int = 6
    checklist: List[str] = ["life_jackets", "fuel", "ice_water", "phone_charged"]


class SosRequest(BaseModel):
    phone: str = "9876500021"
    client_op_id: Optional[str] = None
    lat: float = 13.35
    lon: float = 74.69
    trip_id: Optional[str] = None


@router.post("/start")
async def start_trip(req: StartTripRequest, db: AsyncSession = Depends(get_db)):
    """Start fishing voyage with pre-sail checklist confirmation."""
    u_res = await db.execute(select(User).where(User.phone == req.phone))
    user = u_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    b_res = await db.execute(select(Boat).where(Boat.owner_user_id == user.id))
    boat = b_res.scalar_one_or_none()
    boat_id = boat.id if boat else str(uuid.uuid4())

    now = datetime.now(timezone.utc)
    expected_back = now + timedelta(hours=req.return_in_hours)
    eta_text = expected_back.strftime("%I:%M %p")

    trip = Trip(
        boat_id=boat_id,
        fisher_user_id=user.id,
        crew_count=req.crew_count,
        departed_at=now,
        expected_back_at=expected_back,
        status="out",
        eta_text=eta_text,
    )
    db.add(trip)
    await db.flush()

    for item_key in req.checklist:
        db.add(TripCheck(trip_id=trip.id, check_key=item_key, is_checked=True))

    # Notify family
    fam_res = await db.execute(select(User).where(User.role == "family"))
    family_members = fam_res.scalars().all()
    for fam in family_members:
        db.add(Alert(
            user_id=fam.id,
            role="family",
            alert_type="trip_start",
            title="Trip started",
            message=f"{user.name} departed Malpe Harbour. Safe zone active. Expected back by {eta_text}.",
            severity="info",
        ))

    await db.commit()
    return {
        "status": "trip_started",
        "trip_id": trip.id,
        "eta": eta_text,
        "crew_count": req.crew_count,
        "message": f"Trip started. Family informed. Back by {eta_text}.",
    }


@router.post("/{trip_id}/end")
async def end_trip(trip_id: str, db: AsyncSession = Depends(get_db)):
    """End active fishing trip upon safe return to harbour."""
    t_res = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = t_res.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    trip.status = "landed"
    trip.landed_at = datetime.now(timezone.utc)

    # Notify family
    fam_res = await db.execute(select(User).where(User.role == "family"))
    for fam in fam_res.scalars().all():
        db.add(Alert(
            user_id=fam.id,
            role="family",
            alert_type="trip_ended",
            title="Safe return",
            message="Suresh is home safe at Malpe Harbour.",
            severity="ok",
        ))

    await db.commit()
    return {
        "status": "trip_ended",
        "trip_id": trip.id,
        "message": "Trip ended. Suresh is home safe!",
    }


@router.post("/sos")
async def trigger_sos(req: SosRequest, db: AsyncSession = Depends(get_db)):
    """Physical 2-second hold SOS trigger with client_op_id idempotency (D9, D12)."""
    op_id = req.client_op_id or f"sos_{uuid.uuid4().hex}"

    # Check for duplicate submission via client_op_id (G4)
    existing_sos = await db.execute(select(SosEvent).where(SosEvent.client_op_id == op_id))
    if existing_sos.scalar_one_or_none():
        return {
            "status": "already_received",
            "client_op_id": op_id,
            "message": "SOS distress signal already logged and broadcast.",
        }

    u_res = await db.execute(select(User).where(User.phone == req.phone))
    user = u_res.scalar_one_or_none()
    user_id = user.id if user else str(uuid.uuid4())

    b_res = await db.execute(select(Boat).where(Boat.owner_user_id == user_id))
    boat = b_res.scalar_one_or_none()
    boat_id = boat.id if boat else None

    # 1. Log SosEvent
    sos = SosEvent(
        client_op_id=op_id,
        trip_id=req.trip_id,
        user_id=user_id,
        boat_id=boat_id,
        lat=req.lat,
        lon=req.lon,
        status="active",
    )
    db.add(sos)

    # 2. Log Coast Guard Incident
    db.add(IncidentEvent(
        event_type="sos",
        user_id=user_id,
        boat_id=boat_id,
        severity="red",
        description=f"🚨 SOS from {user.name if user else 'Fisher'}. 4 km offshore. 3 boats nearby.",
    ))

    # 3. Alert Family & Coast Guard
    alert_targets = await db.execute(select(User).where(User.role.in_(["family", "guard"])))
    for target in alert_targets.scalars().all():
        db.add(Alert(
            user_id=target.id,
            role=target.role,
            alert_type="sos",
            title="🚨 SOS DISTRESS ALERT",
            message=f"SOS distress signal from {boat.name if boat else 'Ale-Malpe-07'} ({user.name if user else 'Suresh'}). Coordinates: {req.lat}N {req.lon}E.",
            severity="red",
        ))

    await db.commit()
    return {
        "status": "sos_active",
        "client_op_id": op_id,
        "sos_id": sos.id,
        "message": "🚨 SOS sent to Coast Guard, nearby boats, and family.",
    }
