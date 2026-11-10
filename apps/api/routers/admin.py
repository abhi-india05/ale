# WHY: D1, ADM-1, ADM-2, ADM-3, ADM-4, ADM-5 — Web Admin Console Backend API
"""Admin console endpoints for alias management, price calibration, templates, users, and voice QA."""

from datetime import datetime, timezone
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from apps.api.models import (
    User,
    Boat,
    Harbour,
    FishSpecies,
    FishAlias,
    MarketPrice,
    Alert,
    VoiceSession,
    VoiceTurn,
    FeatureFlag,
)

admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class AliasCreateRequest(BaseModel):
    species_name: str
    alias: str
    language: str = "kn"


class PriceUpdateRequest(BaseModel):
    species_id: str
    harbour_code: str = "MALPE"
    price_low: float
    price_high: float


class TemplateCreateRequest(BaseModel):
    title: str
    severity: str = "red"  # red, amber, info
    template_en: str
    template_kn: str


class BroadcastSendRequest(BaseModel):
    title: str
    severity: str = "red"
    message_en: str
    message_kn: str
    harbour_code: str = "MALPE"


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None


# --- Overview ---
@admin_router.get("/overview")
async def get_admin_overview(db: AsyncSession = Depends(get_db)):
    """Return dashboard summary metrics for Admin Console."""
    species_count = (await db.execute(select(func.count(FishSpecies.id)))).scalar_one()
    alias_count = (await db.execute(select(func.count(FishAlias.id)))).scalar_one()
    user_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    turn_count = (await db.execute(select(func.count(VoiceTurn.id)))).scalar_one()

    # User breakdown
    users_by_role = {}
    u_res = await db.execute(select(User.role, func.count(User.id)).group_by(User.role))
    for role, count in u_res.all():
        users_by_role[role] = count

    return {
        "status": "success",
        "species_count": species_count,
        "alias_count": alias_count,
        "user_count": user_count,
        "voice_turn_count": turn_count,
        "users_by_role": users_by_role,
        "system_health": "operational",
        "active_harbour": "Malpe Harbour (KA-02)",
    }


# --- ADM-1: Fish Aliases ---
@admin_router.get("/aliases")
async def list_aliases(db: AsyncSession = Depends(get_db)):
    """List all fish species with their phonetic Kannada/English aliases."""
    res = await db.execute(
        select(FishAlias, FishSpecies)
        .join(FishSpecies, FishAlias.species_id == FishSpecies.id)
        .order_by(FishSpecies.name_en, FishAlias.alias)
    )
    rows = []
    for alias, sp in res.all():
        rows.append({
            "id": alias.id,
            "species_id": sp.id,
            "species_en": sp.name_en,
            "species_kn": sp.name_kn,
            "alias": alias.alias,
            "language": alias.language,
        })
    return {"aliases": rows}


@admin_router.post("/aliases")
async def create_alias(req: AliasCreateRequest, db: AsyncSession = Depends(get_db)):
    """Add a new phonetic Kannada or code-mixed alias for a fish species."""
    # Find species
    s_res = await db.execute(
        select(FishSpecies).where(
            (FishSpecies.name_en.ilike(req.species_name)) | (FishSpecies.name_kn == req.species_name)
        )
    )
    species = s_res.scalar_one_or_none()
    if not species:
        # Create species if not exists
        species = FishSpecies(name_en=req.species_name.capitalize(), name_kn=req.species_name, emoji="🐟")
        db.add(species)
        await db.flush()

    new_alias = FishAlias(
        species_id=species.id,
        alias=req.alias.strip(),
        language=req.language,
    )
    db.add(new_alias)
    await db.commit()
    return {"status": "created", "alias_id": new_alias.id, "alias": new_alias.alias, "species": species.name_en}


@admin_router.delete("/aliases/{alias_id}")
async def delete_alias(alias_id: str, db: AsyncSession = Depends(get_db)):
    """Remove a fish alias."""
    res = await db.execute(select(FishAlias).where(FishAlias.id == alias_id))
    alias = res.scalar_one_or_none()
    if not alias:
        raise HTTPException(status_code=404, detail="Alias not found")
    await db.delete(alias)
    await db.commit()
    return {"status": "deleted", "alias_id": alias_id}


# --- ADM-2: Market Prices Calibration ---
@admin_router.get("/prices")
async def list_prices(db: AsyncSession = Depends(get_db)):
    """List current market price ranges for all species at Malpe."""
    res = await db.execute(
        select(MarketPrice, FishSpecies, Harbour)
        .join(FishSpecies, MarketPrice.species_id == FishSpecies.id)
        .join(Harbour, MarketPrice.harbour_id == Harbour.id)
        .order_by(FishSpecies.name_en)
    )
    prices = []
    for mp, sp, h in res.all():
        prices.append({
            "id": mp.id,
            "species_id": sp.id,
            "species_en": sp.name_en,
            "species_kn": sp.name_kn,
            "harbour": h.name,
            "price_low": mp.price_low,
            "price_high": mp.price_high,
            "effective_date": mp.effective_date,
        })
    return {"prices": prices}


@admin_router.post("/prices")
async def update_market_price(req: PriceUpdateRequest, db: AsyncSession = Depends(get_db)):
    """Calibrate today's low/high price for a fish species."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    h_res = await db.execute(select(Harbour).where(Harbour.code == req.harbour_code))
    harbour = h_res.scalar_one_or_none()
    if not harbour:
        harbour = (await db.execute(select(Harbour).limit(1))).scalar_one_or_none()

    # Find existing price record or create
    p_res = await db.execute(
        select(MarketPrice).where(
            MarketPrice.species_id == req.species_id,
            MarketPrice.harbour_id == (harbour.id if harbour else None),
            MarketPrice.effective_date == today,
        )
    )
    mp = p_res.scalar_one_or_none()
    if mp:
        mp.price_low = req.price_low
        mp.price_high = req.price_high
    else:
        mp = MarketPrice(
            species_id=req.species_id,
            harbour_id=harbour.id if harbour else str(uuid.uuid4()),
            price_low=req.price_low,
            price_high=req.price_high,
            effective_date=today,
        )
        db.add(mp)

    await db.commit()
    return {"status": "updated", "price_id": mp.id, "price_low": mp.price_low, "price_high": mp.price_high}


# --- ADM-3: Emergency Broadcast Templates ---
DEFAULT_TEMPLATES = [
    {
        "id": "tpl_cyclone",
        "title": "Severe Cyclone / Storm Surge Warning",
        "severity": "red",
        "template_en": "RED ALERT: Cyclone warning within 40 km. High waves 4.2m. All boats return to harbour immediately.",
        "template_kn": "ಕೆಂಪು ಎಚ್ಚರಿಕೆ: ಚಂಡಮಾರುತದ ಎಚ್ಚರಿಕೆ. 4.2 ಮೀಟರ್ ಎತ್ತರದ ಅಲೆಗಳು. ಎಲ್ಲಾ ದೋಣಿಗಳು ತಕ್ಷಣ ಬಂದರಿಗೆ ಮರಳಿ.",
    },
    {
        "id": "tpl_rough_sea",
        "title": "Rough Sea Advisory",
        "severity": "amber",
        "template_en": "AMBER ADVISORY: Squally weather with wind speed 45-55 km/h. Small craft advised not to venture.",
        "template_kn": "ಎಚ್ಚರಿಕೆ: ಗಾಳಿಯ ವೇಗ 45-55 ಕಿ.ಮೀ. ಸಣ್ಣ ದೋಣಿಗಳು ಸಮುದ್ರಕ್ಕೆ ಇಳಿಯಬೇಡಿ.",
    },
    {
        "id": "tpl_all_clear",
        "title": "Weather All Clear",
        "severity": "info",
        "template_en": "ALL CLEAR: Wind 12 km/h, calm sea. Fishing conditions favorable.",
        "template_kn": "ಶಾಂತ ಸಮುದ್ರ: ಗಾಳಿ 12 ಕಿ.ಮೀ. ಮೀನುಗಾರಿಕೆಗೆ ಪರಿಸ್ಥಿತಿ ಅನುಕೂಲಕರವಾಗಿದೆ.",
    },
]


@admin_router.get("/templates")
async def list_broadcast_templates():
    """List standard Coast Guard broadcast templates."""
    return {"templates": DEFAULT_TEMPLATES}


@admin_router.post("/broadcast")
async def send_admin_broadcast(req: BroadcastSendRequest, db: AsyncSession = Depends(get_db)):
    """Trigger voice alert & push notification to all fishers and families."""
    users = (await db.execute(select(User).where(User.role.in_(["fisher", "family"])))).scalars().all()
    count = 0
    for u in users:
        db.add(Alert(
            user_id=u.id,
            role=u.role,
            alert_type="broadcast",
            title=req.title,
            message=f"{req.message_kn}\n({req.message_en})",
            severity=req.severity,
        ))
        count += 1
    await db.commit()
    return {
        "status": "broadcast_sent",
        "recipients_notified": count,
        "title": req.title,
        "severity": req.severity,
    }


# --- ADM-4: User Directory & Harbours ---
@admin_router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    """List all registered users, boat registrations, and roles."""
    res = await db.execute(
        select(User, Boat)
        .outerjoin(Boat, Boat.owner_user_id == User.id)
        .order_by(User.role, User.name)
    )
    users = []
    for u, b in res.all():
        users.append({
            "id": u.id,
            "name": u.name,
            "phone": u.phone,
            "role": u.role,
            "boat_name": b.name if b else "—",
            "boat_reg": b.reg_number if b else "—",
        })
    return {"users": users}


@admin_router.put("/users/{user_id}")
async def update_user(user_id: str, req: UserUpdateRequest, db: AsyncSession = Depends(get_db)):
    """Update user role, name, or phone."""
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if req.role:
        user.role = req.role
    if req.name:
        user.name = req.name
    if req.phone:
        user.phone = req.phone

    await db.commit()
    return {"status": "updated", "user_id": user.id, "name": user.name, "role": user.role}


# --- ADM-5: Voice Quality Assurance & Flagged Turns ---
@admin_router.get("/voice-turns")
async def list_voice_turns(db: AsyncSession = Depends(get_db)):
    """List recent voice turns with STT transcript, intent, TTS audio and latency for QA."""
    res = await db.execute(
        select(VoiceTurn).order_by(VoiceTurn.created_at.desc()).limit(50)
    )
    turns = []
    for vt in res.scalars().all():
        turns.append({
            "id": vt.id,
            "session_id": vt.session_id,
            "turn_index": vt.turn_index,
            "speaker": vt.speaker,
            "transcript_raw": vt.transcript_raw,
            "intent": vt.intent,
            "confidence": vt.confidence,
            "audio_duration_sec": vt.audio_duration_sec,
            "stt_latency_ms": vt.stt_latency_ms,
            "nlu_latency_ms": vt.nlu_latency_ms,
            "tts_latency_ms": vt.tts_latency_ms,
            "total_latency_ms": vt.total_latency_ms,
            "flagged": vt.flagged_for_review,
            "created_at": vt.created_at.isoformat() if vt.created_at else None,
        })
    return {"turns": turns}


@admin_router.post("/voice-turns/{turn_id}/flag")
async def flag_voice_turn(turn_id: str, db: AsyncSession = Depends(get_db)):
    """Toggle flagged review status on a voice turn for speech engine retraining."""
    res = await db.execute(select(VoiceTurn).where(VoiceTurn.id == turn_id))
    turn = res.scalar_one_or_none()
    if not turn:
        raise HTTPException(status_code=404, detail="Voice turn not found")

    turn.flagged_for_review = not turn.flagged_for_review
    await db.commit()
    return {"status": "updated", "turn_id": turn.id, "flagged": turn.flagged_for_review}

