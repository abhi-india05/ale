# WHY: FR-PRC-01, FR-LND-01, FR-BID-01, TR-PRC-01 — Market Prices, Offer Checker, Landings & Bids
"""Fair price board, offer evaluation, catch announcements, and competitive bids."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from apps.api.models import User, FishSpecies, MarketPrice, Landing, Bid, LedgerEntry
from apps.api.services.lexicon import FISH_CATALOGUE


router = APIRouter(prefix="/api/v1/market", tags=["market"])


class OfferCheckRequest(BaseModel):
    species: str
    offer_per_kg: Optional[float] = None
    offer_price: Optional[float] = None

    @property
    def effective_offer(self) -> float:
        if self.offer_per_kg is not None:
            return self.offer_per_kg
        if self.offer_price is not None:
            return self.offer_price
        return 100.0


class LandingRequest(BaseModel):
    phone: str = "9876500021"
    species: str = "Sardine"
    quantity_kg: float = 40.0
    eta_min: int = 40


class PlaceBidRequest(BaseModel):
    landing_id: Optional[str] = None
    buyer_name: str = "Rafiq, Harbour Agent"
    buyer_phone: str = "9876500031"
    bid_per_kg: Optional[float] = None
    bid_price_per_kg: Optional[float] = None

    @property
    def price(self) -> float:
        if self.bid_per_kg is not None:
            return self.bid_per_kg
        if self.bid_price_per_kg is not None:
            return self.bid_price_per_kg
        return 100.0


@router.get("/prices")
async def get_prices():
    """Retrieve today's fair price bands for 4 species at Malpe."""
    result = []
    for sp_key, info in FISH_CATALOGUE.items():
        lo, hi = info["price_range"]
        result.append({
            "species": sp_key,
            "name_kn": info["name_kn"],
            "emoji": info["emoji"],
            "low": lo,
            "high": hi,
            "display": f"₹{lo}–{hi}",
            "trend": "▲ ₹12" if sp_key == "Sardine" else "▼ ₹8" if sp_key == "Mackerel" else "▲ ₹40",
            "trend_dir": "up" if sp_key != "Mackerel" else "down",
        })
    return {"harbour": "Malpe", "prices": result}


@router.post("/offer-check")
async def check_offer(req: OfferCheckRequest):
    """Evaluate whether a buyer's offer is low, fair, or great."""
    info = FISH_CATALOGUE.get(req.species, FISH_CATALOGUE["Sardine"])
    lo, hi = info["price_range"]
    offer = req.effective_offer

    if offer < lo:
        verdict = "Too low"
        advice_en = f"Too low. Ask for more (₹{lo}–{hi})."
        advice_kn = f"ಇದು ಕಮ್ಮಿ. ಇವತ್ತಿನ ರೇಟ್ {lo} ರಿಂದ {hi}. ಇನ್ನೂ ಕೇಳಿ."
        color = "#d6372f"
    elif offer > hi:
        verdict = "Great offer"
        advice_en = f"Great offer. Take it! (₹{lo}–{hi})."
        advice_kn = f"ಒಳ್ಳೆ ಬೆಲೆ! ಇವತ್ತಿನ ರೇಟ್ {lo} ರಿಂದ {hi}. ಒಪ್ಪಿಕೊಳ್ಳಿ."
        color = "#1fa35b"
    else:
        verdict = "Fair price"
        advice_en = f"Fair price (₹{lo}–{hi})."
        advice_kn = f"ನ್ಯಾಯಯುತ ಬೆಲೆ. ಇವತ್ತಿನ ರೇಟ್ {lo} ರಿಂದ {hi}."
        color = "#0a4d7a"

    return {
        "species": req.species,
        "offer": offer,
        "range": [lo, hi],
        "range_min": lo,
        "range_max": hi,
        "verdict": verdict,
        "verdict_en": verdict,
        "advice_en": advice_en,
        "advice_kn": advice_kn,
        "color": color,
    }


@router.post("/landings")
async def create_landing(req: LandingRequest, db: AsyncSession = Depends(get_db)):
    """Announce incoming catch to notified buyers."""
    u_res = await db.execute(select(User).where(User.phone == req.phone))
    user = u_res.scalar_one_or_none()
    user_id = user.id if user else str(uuid.uuid4())
    harbour_id = user.harbour_id if user and user.harbour_id else str(uuid.uuid4())

    sp_res = await db.execute(select(FishSpecies).where(FishSpecies.name_en == req.species))
    species = sp_res.scalar_one_or_none()
    species_id = species.id if species else str(uuid.uuid4())

    landing = Landing(
        fisher_user_id=user_id,
        harbour_id=harbour_id,
        species_id=species_id,
        quantity_kg=req.quantity_kg,
        eta_min=req.eta_min,
        status="announced",
    )
    db.add(landing)
    await db.commit()

    # Pre-generate 3 buyer bids for demo flow (Rafiq, Fish Mart, Hotel Mitra)
    lo, hi = FISH_CATALOGUE.get(req.species, {}).get("price_range", (90, 110))
    mid_price = round((lo + hi) / 2)
    sample_bids = [
        ("Rafiq, Harbour Agent", "🧑‍💼", lo),
        ("Fish Mart Udupi", "🏪", mid_price),
        ("Hotel Mitra", "🏨", hi),
    ]
    created_bids = []
    for b_name, b_emoji, b_price in sample_bids:
        b_user = await db.execute(select(User).where(User.role == "buyer"))
        buyer = b_user.scalars().first()
        bid_item = Bid(
            landing_id=landing.id,
            buyer_user_id=buyer.id if buyer else str(uuid.uuid4()),
            buyer_name=f"{b_emoji} {b_name}",
            bid_price_per_kg=b_price,
            status="pending",
        )
        db.add(bid_item)
        created_bids.append(bid_item)
    await db.commit()

    bids_out = [
        {
            "id": b.id,
            "buyer_name": b.buyer_name,
            "bid_price_per_kg": b.bid_price_per_kg,
            "status": b.status,
        }
        for b in created_bids
    ]

    return {
        "status": "announced",
        "landing_id": landing.id,
        "species": req.species,
        "quantity_kg": req.quantity_kg,
        "eta_min": req.eta_min,
        "notified_buyers": 12,
        "message": f"📣 12 buyers notified. ETA {req.eta_min} min.",
        "bids": bids_out,
    }


@router.get("/landings")
async def list_incoming_landings(db: AsyncSession = Depends(get_db)):
    """List incoming catches for buyer perspective."""
    l_res = await db.execute(select(Landing).order_by(Landing.created_at.desc()).limit(10))
    landings = l_res.scalars().all()
    out = []
    for l in landings:
        sp = await db.execute(select(FishSpecies).where(FishSpecies.id == l.species_id))
        species = sp.scalar_one_or_none()
        sp_name = species.name_en if species else "Sardine"
        out.append({
            "landing_id": l.id,
            "species": sp_name,
            "emoji": FISH_CATALOGUE.get(sp_name, {}).get("emoji", "🐟"),
            "quantity_kg": l.quantity_kg,
            "eta_min": l.eta_min,
            "status": l.status,
            "boat": "Ale-Malpe-07",
        })
    return {"incoming_landings": out}


@router.post("/landings/{landing_id}/bids")
async def place_bid(landing_id: str, req: PlaceBidRequest, db: AsyncSession = Depends(get_db)):
    """Buyer submits bid for announced catch."""
    actual_landing_id = landing_id
    if landing_id == "active":
        active_res = await db.execute(
            select(Landing).where(Landing.status == "announced").order_by(Landing.created_at.desc()).limit(1)
        )
        act_l = active_res.scalar_one_or_none()
        if act_l:
            actual_landing_id = act_l.id
        else:
            actual_landing_id = str(uuid.uuid4())

    bid = Bid(
        landing_id=actual_landing_id,
        buyer_user_id=str(uuid.uuid4()),
        buyer_name=req.buyer_name,
        bid_price_per_kg=req.price,
        status="pending",
    )
    db.add(bid)
    await db.commit()
    return {"status": "bid_placed", "bid_id": bid.id, "amount": req.price, "landing_id": actual_landing_id}


@router.post("/bids/{bid_id}/accept")
async def accept_bid(bid_id: str, db: AsyncSession = Depends(get_db)):
    """Fisher accepts buyer bid; automatically logs sale to earnings diary."""
    b_res = await db.execute(select(Bid).where(Bid.id == bid_id))
    bid = b_res.scalar_one_or_none()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")

    bid.status = "accepted"

    # Fetch landing
    l_res = await db.execute(select(Landing).where(Landing.id == bid.landing_id))
    landing = l_res.scalar_one_or_none()
    total_amount = bid.bid_price_per_kg * (landing.quantity_kg if landing else 40.0)

    # Auto-add sale to diary
    db.add(LedgerEntry(
        user_id=landing.fisher_user_id if landing else str(uuid.uuid4()),
        entry_type="sale",
        amount=total_amount,
        description=f"{landing.quantity_kg if landing else 40} kg catch sold to {bid.buyer_name}",
        quantity_kg=landing.quantity_kg if landing else 40.0,
        client_op_id=f"bid_sale_{bid.id[:12]}",
    ))
    await db.commit()
    return {
        "status": "sold",
        "total_sale": total_amount,
        "buyer": bid.buyer_name,
        "message": f"✔ Sold to {bid.buyer_name} for ₹{int(total_amount):,}",
    }
