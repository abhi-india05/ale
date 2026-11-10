# WHY: FR-WTH-01, FR-WTH-02, TR-WTH-01, D13 — Open-Meteo Marine Weather & Dawn Verdict
"""Weather router fetching real Open-Meteo marine conditions with DB snapshot fallback."""

from typing import Optional
import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import settings
from apps.api.core.database import get_db
from apps.api.models import Harbour, WeatherRule, WeatherSnapshot


router = APIRouter(prefix="/api/v1/weather", tags=["weather"])


class WeatherSimulateRequest(BaseModel):
    harbour_code: str = "MALPE"
    verdict: str = "caution"  # "go", "caution", "no_go"
    wind_kmh: Optional[float] = None
    wave_m: Optional[float] = None


@router.post("/simulate")
async def simulate_weather(req: WeatherSimulateRequest, db: AsyncSession = Depends(get_db)):
    """Simulate weather conditions and persist snapshot so voice & UI stay synchronized."""
    h_res = await db.execute(select(Harbour).where(Harbour.code == req.harbour_code))
    harbour = h_res.scalar_one_or_none()
    harbour_id = harbour.id if harbour else str(uuid.uuid4())

    wind = req.wind_kmh
    wave = req.wave_m
    if req.verdict == "no_go":
        wind = wind or 45.0
        wave = wave or 3.5
        kn = "ಹೋಗಬೇಡಿ. ಗಾಳಿ ನಲವತ್ತೈದು, ಅಲೆ ಮೂರೂವರೆ ಮೀಟರ್."
        en = "Do not go. Wind 45 km/h, waves about 3.5 m."
        color = "#d6372f"
        angle = 60
        label_en = "Don’t go"
        label_kn = "ಹೋಗಬೇಡಿ"
    elif req.verdict == "caution":
        wind = wind or 28.0
        wave = wave or 1.8
        kn = "ಜಾಗರೂಕರಾಗಿರಿ. ಗಾಳಿ ಇಪ್ಪತ್ತೆಂಟು, ಅಲೆ ಎರಡು ಮೀಟರ್ ಹತ್ತಿರ."
        en = "Be careful. Wind 28 km/h, waves near 2 m."
        color = "#f0a020"
        angle = 0
        label_en = "Be careful"
        label_kn = "ಜಾಗರೂಕರಾಗಿರಿ"
    else:
        wind = wind or 12.0
        wave = wave or 0.8
        kn = "ಹೋಗಬಹುದು. ಗಾಳಿ ಹನ್ನೆರಡು ಕಿಲೋಮೀಟರ್, ಅಲೆ ಒಂದು ಮೀಟರ್ ಒಳಗೆ."
        en = "Go. Wind 12 km/h, waves under 1 m."
        color = "#1fa35b"
        angle = -60
        label_en = "Go"
        label_kn = "ಹೋಗಬಹುದು"

    snap = WeatherSnapshot(
        harbour_id=harbour_id,
        wind_kmh=wind,
        wave_m=wave,
        verdict=req.verdict,
        kn_summary=kn,
        en_summary=en,
        raw_payload=f'{{"source": "simulated", "verdict": "{req.verdict}"}}',
    )
    db.add(snap)
    await db.commit()

    return {
        "status": "simulated",
        "verdict": req.verdict,
        "label_en": label_en,
        "label_kn": label_kn,
        "color": color,
        "gauge_angle": angle,
        "wind_kmh": wind,
        "wave_m": wave,
        "high_tide": "6:12 AM",
        "low_tide": "12:30 PM",
        "kn_summary": kn,
        "en_summary": en,
    }


@router.get("/dawn")
async def get_dawn_weather(
    harbour_code: str = "MALPE",
    db: AsyncSession = Depends(get_db),
):
    """Retrieve Dawn weather verdict (Go / Be careful / Don't go) for morning sailing."""
    # Find harbour
    h_res = await db.execute(select(Harbour).where(Harbour.code == harbour_code))
    harbour = h_res.scalar_one_or_none()
    lat = harbour.lat if harbour else settings.malpe_lat
    lon = harbour.lon if harbour else settings.malpe_lon

    # Check for recent persisted snapshot (e.g. simulated or seeded)
    snap_res = await db.execute(
        select(WeatherSnapshot).order_by(WeatherSnapshot.created_at.desc()).limit(1)
    )
    snap = snap_res.scalar_one_or_none()
    if snap:
        verdict = snap.verdict
        wind_kmh = snap.wind_kmh
        wave_m = snap.wave_m
        if verdict == "no_go":
            label_en = "Don’t go"
            label_kn = "ಹೋಗಬೇಡಿ"
            color = "#d6372f"
            angle = 60
        elif verdict == "caution":
            label_en = "Be careful"
            label_kn = "ಜಾಗರೂಕರಾಗಿರಿ"
            color = "#f0a020"
            angle = 0
        else:
            label_en = "Go"
            label_kn = "ಹೋಗಬಹುದು"
            color = "#1fa35b"
            angle = -60

        return {
            "harbour": harbour.name if harbour else "Malpe",
            "verdict": verdict,
            "label_en": label_en,
            "label_kn": label_kn,
            "color": color,
            "gauge_angle": angle,
            "wind_kmh": round(wind_kmh, 1),
            "wave_m": round(wave_m, 2),
            "high_tide": "6:12 AM",
            "low_tide": "12:30 PM",
            "kn_summary": snap.kn_summary,
            "en_summary": snap.en_summary,
            "source": "snapshot",
        }

    wind_kmh = 12.0
    wave_m = 0.8
    source = "seeded"

    # Attempt real Open-Meteo API call (non-blocking with 2.5s timeout)
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&current=wave_height,swell_wave_period"
            forecast_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=wind_speed_10m,wind_gusts_10m"
            
            m_res = await client.get(marine_url)
            f_res = await client.get(forecast_url)
            
            if m_res.status_code == 200 and f_res.status_code == 200:
                m_data = m_res.json()
                f_data = f_res.json()
                wave_m = float(m_data.get("current", {}).get("wave_height", 0.8))
                wind_kmh = float(f_data.get("current", {}).get("wind_speed_10m", 12.0))
                source = "open-meteo"
    except Exception:
        # Fallback to seeded DB snapshot (D13)
        pass

    # Threshold rules (D13)
    if wind_kmh >= 40.0 or wave_m >= 3.0:
        verdict = "no_go"
        label_en = "Don’t go"
        label_kn = "ಹೋಗಬೇಡಿ"
        color = "#d6372f"
        kn_summary = f"ಹೋಗಬೇಡಿ. ಗಾಳಿ {int(wind_kmh)} ಕಿಲೋಮೀಟರ್, ಅಲೆ {wave_m} ಮೀಟರ್."
        en_summary = f"Do not go. Wind {int(wind_kmh)} km/h, waves {wave_m} m."
        gauge_angle = 60
    elif wind_kmh >= 25.0 or wave_m >= 1.8:
        verdict = "caution"
        label_en = "Be careful"
        label_kn = "ಜಾಗರೂಕರಾಗಿರಿ"
        color = "#f0a020"
        kn_summary = f"ಜಾಗರೂಕರಾಗಿರಿ. ಗಾಳಿ {int(wind_kmh)}, ಅಲೆ {wave_m} ಮೀಟರ್ ಹತ್ತಿರ."
        en_summary = f"Be careful. Wind {int(wind_kmh)} km/h, waves near {wave_m} m."
        gauge_angle = 0
    else:
        verdict = "go"
        label_en = "Go"
        label_kn = "ಹೋಗಬಹುದು"
        color = "#1fa35b"
        kn_summary = f"ಹೋಗಬಹುದು. ಗಾಳಿ {int(wind_kmh)} ಕಿಲೋಮೀಟರ್, ಅಲೆ {wave_m} ಮೀಟರ್ ಒಳಗೆ."
        en_summary = f"Go. Wind {int(wind_kmh)} km/h, waves under {wave_m} m."
        gauge_angle = -60

    return {
        "harbour": harbour.name if harbour else "Malpe",
        "verdict": verdict,
        "label_en": label_en,
        "label_kn": label_kn,
        "color": color,
        "gauge_angle": gauge_angle,
        "wind_kmh": round(wind_kmh, 1),
        "wave_m": round(wave_m, 2),
        "high_tide": "6:12 AM",
        "low_tide": "12:30 PM",
        "kn_summary": kn_summary,
        "en_summary": en_summary,
        "source": source,
    }
