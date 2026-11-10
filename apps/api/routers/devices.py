# WHY: FR-APP-01, FR-SEA-07, FR-SET-02, TR-CLI-12, TR-CLI-14, TR-CLI-15, D17, D18 — Device Registration, Health Heartbeat & Version Gating
"""Device registration, OEM battery health monitoring, and client version management."""

from datetime import datetime, timezone
import json
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.database import get_db
from apps.api.models import User, Trip, Device, DeviceHealthReport, FeatureFlag, Alert, IncidentEvent


devices_router = APIRouter(prefix="/api/v1/devices", tags=["devices"])
app_router = APIRouter(prefix="/api/v1/app", tags=["app"])


class RegisterDeviceRequest(BaseModel):
    phone: str = "9876500021"
    platform: str = "android"
    push_provider: str = "fcm"
    push_token: Optional[str] = "fcm_token_demo"
    app_version: str = "1.1.0"
    os_version: str = "Android 14"
    device_model: str = "Redmi Note 12 5G"
    locale: str = "kn-IN"


class DeviceHealthSubmitRequest(BaseModel):
    device_id: Optional[str] = None
    phone: Optional[str] = "9876500021"
    trip_id: Optional[str] = None
    tracking_state: str = "running"  # running, degraded, stopped
    location_permission: str = "always"  # none, foreground, always
    notifications_enabled: bool = True
    battery_optimised: bool = False
    gps_enabled: bool = True
    battery_pct: int = 86
    network: str = "good"  # good, poor, none
    reason: Optional[str] = None


OEM_BATTERY_GUIDES = {
    "Xiaomi": "Settings > Apps > Manage Apps > Ale Voice > Battery Saver > Set to 'No restrictions'. Enable Autostart.",
    "Redmi": "Settings > Apps > Manage Apps > Ale Voice > Battery Saver > Set to 'No restrictions'. Enable Autostart.",
    "Samsung": "Settings > Battery and device care > Battery > Background usage limits > Never sleeping apps > Add Ale Voice.",
    "Vivo": "Settings > Battery > High background power consumption > Allow Ale Voice.",
    "Realme": "Settings > Battery > App Battery Management > Ale Voice > Allow background activity.",
    "Oppo": "Settings > Battery > App Battery Management > Ale Voice > Allow background activity.",
    "OnePlus": "Settings > Battery > More settings > Optimize battery use > Ale Voice > Don't optimize.",
}


@devices_router.post("/register")
async def register_device(req: RegisterDeviceRequest, db: AsyncSession = Depends(get_db)):
    """Register client device metadata and FCM push token."""
    u_res = await db.execute(select(User).where(User.phone == req.phone))
    user = u_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    d_res = await db.execute(select(Device).where(Device.user_id == user.id, Device.platform == req.platform))
    dev = d_res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if dev:
        dev.push_token = req.push_token
        dev.app_version = req.app_version
        dev.os_version = req.os_version
        dev.device_model = req.device_model
        dev.locale = req.locale
        dev.last_seen_at = now
    else:
        dev = Device(
            user_id=user.id,
            platform=req.platform,
            push_provider=req.push_provider,
            push_token=req.push_token,
            app_version=req.app_version,
            os_version=req.os_version,
            device_model=req.device_model,
            locale=req.locale,
            last_seen_at=now,
        )
        db.add(dev)

    await db.commit()
    return {
        "status": "registered",
        "device_id": dev.id,
        "platform": dev.platform,
        "app_version": dev.app_version,
        "device_model": dev.device_model,
    }


@devices_router.post("/health")
async def submit_device_health(req: DeviceHealthSubmitRequest, db: AsyncSession = Depends(get_db)):
    """Heartbeat endpoint for Android foreground tracking service."""
    dev = None
    user = None

    if req.device_id:
        d_res = await db.execute(select(Device).where(Device.id == req.device_id))
        dev = d_res.scalar_one_or_none()

    if not dev and req.phone:
        u_res = await db.execute(select(User).where(User.phone == req.phone))
        user = u_res.scalar_one_or_none()
        if user:
            d_res = await db.execute(select(Device).where(Device.user_id == user.id).order_by(Device.last_seen_at.desc()).limit(1))
            dev = d_res.scalar_one_or_none()

    if not dev and user:
        dev = Device(
            user_id=user.id,
            platform="android",
            push_provider="fcm",
            push_token="fcm_auto",
            app_version="1.1.0",
            os_version="Android 14",
            device_model="Android Device",
            locale="kn-IN",
        )
        db.add(dev)
        await db.flush()

    if not dev:
        raise HTTPException(status_code=400, detail="Device could not be resolved from device_id or phone.")

    user_id = dev.user_id

    # Resolve active trip if not provided
    trip_id = req.trip_id
    if not trip_id:
        t_res = await db.execute(
            select(Trip).where(Trip.fisher_user_id == user_id, Trip.status.in_(["out", "returning", "overdue"]))
            .order_by(Trip.created_at.desc()).limit(1)
        )
        trip = t_res.scalar_one_or_none()
        if trip:
            trip_id = trip.id

    report = DeviceHealthReport(
        device_id=dev.id,
        user_id=user_id,
        trip_id=trip_id,
        tracking_state=req.tracking_state,
        location_permission=req.location_permission,
        notifications_enabled=req.notifications_enabled,
        battery_optimised=req.battery_optimised,
        gps_enabled=req.gps_enabled,
        battery_pct=req.battery_pct,
        network=req.network,
        reason=req.reason,
    )
    db.add(report)

    dev.last_seen_at = datetime.now(timezone.utc)

    # N-15 Degraded Tracking Incident & Alerts
    if req.tracking_state in ["degraded", "stopped"]:
        reason_text = req.reason or "Foreground tracking service killed or permissions missing."
        db.add(Alert(
            user_id=user_id,
            role="fisher",
            alert_type="tracking_degraded",
            title="N-15 Tracking Degraded",
            message=f"⚠️ Trip tracking interrupted: {reason_text}. Tap to restore.",
            severity="amber",
        ))
        # Alert family that tracking is degraded
        fam_res = await db.execute(select(User).where(User.role == "family"))
        for fam in fam_res.scalars().all():
            db.add(Alert(
                user_id=fam.id,
                role="family",
                alert_type="tracking_degraded",
                title="Boat Tracking Degraded",
                message="GPS tracking signal for Suresh's boat is temporarily degraded.",
                severity="amber",
            ))

    await db.commit()
    return {
        "status": "recorded",
        "report_id": report.id,
        "tracking_state": report.tracking_state,
        "battery_pct": report.battery_pct,
    }


@devices_router.get("/health")
async def get_device_health(phone: Optional[str] = "9876500021", device_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Retrieve the latest tracking health report and OEM battery optimization steps."""
    dev = None
    if device_id:
        d_res = await db.execute(select(Device).where(Device.id == device_id))
        dev = d_res.scalar_one_or_none()
    elif phone:
        u_res = await db.execute(select(User).where(User.phone == phone))
        user = u_res.scalar_one_or_none()
        if user:
            d_res = await db.execute(select(Device).where(Device.user_id == user.id).order_by(Device.last_seen_at.desc()).limit(1))
            dev = d_res.scalar_one_or_none()

    if not dev:
        return {
            "status": "healthy",
            "tracking_state": "running",
            "location_permission": "always",
            "notifications_enabled": True,
            "battery_optimised": False,
            "gps_enabled": True,
            "battery_pct": 86,
            "network": "good",
            "oem_guidance": OEM_BATTERY_GUIDES["Xiaomi"],
            "device_model": "Xiaomi Redmi Note 12",
        }

    h_res = await db.execute(
        select(DeviceHealthReport).where(DeviceHealthReport.device_id == dev.id)
        .order_by(DeviceHealthReport.reported_at.desc()).limit(1)
    )
    report = h_res.scalar_one_or_none()

    matched_guide = OEM_BATTERY_GUIDES.get("Xiaomi")
    for brand, guide in OEM_BATTERY_GUIDES.items():
        if brand.lower() in (dev.device_model or "").lower():
            matched_guide = guide
            break

    if report:
        return {
            "status": "recorded",
            "device_id": dev.id,
            "device_model": dev.device_model,
            "tracking_state": report.tracking_state,
            "location_permission": report.location_permission,
            "notifications_enabled": report.notifications_enabled,
            "battery_optimised": report.battery_optimised,
            "gps_enabled": report.gps_enabled,
            "battery_pct": report.battery_pct,
            "network": report.network,
            "reason": report.reason,
            "reported_at": report.reported_at.isoformat(),
            "oem_guidance": matched_guide,
        }

    return {
        "status": "default",
        "device_id": dev.id,
        "device_model": dev.device_model,
        "tracking_state": "running",
        "location_permission": "always",
        "battery_pct": 86,
        "oem_guidance": matched_guide,
    }


# WHY: TR-CLI-15 — Minimum app version check and remote feature flags
@app_router.get("/version")
async def get_app_version(client_version: Optional[str] = "1.1.0", db: AsyncSession = Depends(get_db)):
    """Validate client app version against remote minimum version gate."""
    res = await db.execute(select(FeatureFlag).where(FeatureFlag.key == "min_app_version"))
    flag = res.scalar_one_or_none()

    min_ver = "1.1.0"
    current_ver = "1.1.0"
    play_url = "https://play.google.com/store/apps/details?id=in.alevoice.mobile"
    apk_url = "/downloads/ale-v1.1.0.apk"

    if flag and flag.payload_json:
        try:
            data = json.loads(flag.payload_json)
            min_ver = data.get("min_version", min_ver)
            current_ver = data.get("current_version", current_ver)
            play_url = data.get("play_store_url", play_url)
            apk_url = data.get("apk_download_url", apk_url)
        except Exception:
            pass

    def parse_ver(v: str):
        try:
            return [int(x) for x in v.split(".")]
        except Exception:
            return [1, 0, 0]

    force_update = parse_ver(client_version) < parse_ver(min_ver)

    return {
        "min_app_version": min_ver,
        "current_version": current_ver,
        "force_update": force_update,
        "play_store_url": play_url,
        "apk_download_url": apk_url,
    }

