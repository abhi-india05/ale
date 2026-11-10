# WHY: G1, G2, G3, G4, D7, D8, D9, D12 — Quality Gates G1–G4 Verification Suite
"""Automated tests strictly verifying the 4 Protected Core Quality Gates."""

import pytest
import uuid
from sqlalchemy import select, func
from httpx import AsyncClient

from apps.api.services.orchestrator import VoiceOrchestrator
from apps.api.models import LedgerEntry, FishSpot, Landing, SosEvent, Alert
from apps.api.core.database import async_session


# ==============================================================================
# QUALITY GATE G1: Read-Only Kannada Intents & Stage Latencies
# ==============================================================================
@pytest.mark.asyncio
async def test_g1_readonly_intents_and_latency():
    """G1: Read-only Kannada intents act at conf >= 0.80 and record stage timings."""
    async with async_session() as db:
        # 1. Weather intent
        out_weather = await VoiceOrchestrator.process_turn(
            session_token=str(uuid.uuid4()),
            user_phone="9876500021",
            role="fisher",
            transcript_override="ಇವತ್ತು ಸಮುದ್ರಕ್ಕೆ ಹೋಗಬಹುದಾ?",
            db=db,
        )
        assert out_weather["intent"] == "check_weather"
        assert out_weather["confidence"] >= 0.80
        assert out_weather["decision"] == "act"
        assert "ಹೋಗಬಹುದು" in out_weather["reply_kn"]
        
        # Verify latency breakdown
        timings = out_weather["timings"]
        assert timings["stt_ms"] > 0
        assert timings["nlu_ms"] >= 0
        assert timings["action_ms"] >= 0
        assert timings["tts_ms"] > 0
        assert timings["total_ms"] > 0

        # 2. Price intent
        out_price = await VoiceOrchestrator.process_turn(
            session_token=str(uuid.uuid4()),
            user_phone="9876500021",
            role="fisher",
            transcript_override="ಬಂಗುಡೆ ರೇಟ್ ಎಷ್ಟು?",
            db=db,
        )
        assert out_price["intent"] == "get_price"
        assert out_price["confidence"] >= 0.80
        assert out_price["decision"] == "act"
        assert "ಬಂಗುಡೆ" in out_price["reply_kn"]

        # 3. Offer Check intent
        out_offer = await VoiceOrchestrator.process_turn(
            session_token=str(uuid.uuid4()),
            user_phone="9876500021",
            role="fisher",
            transcript_override="pomfret ಕೆಜಿಗೆ 600 ಕೊಡ್ತಾರೆ, fair ಆ?",
            db=db,
        )
        assert out_offer["intent"] == "check_offer"
        assert out_offer["confidence"] >= 0.80
        assert out_offer["decision"] == "act"
        assert "ಕಮ್ಮಿ" in out_offer["reply_kn"]


# ==============================================================================
# QUALITY GATE G2: Zero Unconfirmed Voice Writes
# ==============================================================================
@pytest.mark.asyncio
async def test_g2_zero_unconfirmed_voice_writes():
    """G2: Write intents ALWAYS require confirmation; zero commit to DB until confirmed."""
    token = f"sess_g2_{uuid.uuid4().hex[:8]}"

    async with async_session() as db:
        # Count existing ledger entries before write turn
        count_before = (await db.execute(select(func.count(LedgerEntry.id)))).scalar_one()

        # 1. Voice write turn: Diary catch & diesel
        turn_out = await VoiceOrchestrator.process_turn(
            session_token=token,
            user_phone="9876500021",
            role="fisher",
            transcript_override="ಇವತ್ತು ನಲವತ್ತು ಕೆಜಿ ಬೂತಾಯಿ ಮಾರಿದೆ, ಕೆಜಿಗೆ ನೂರು, ಡೀಸೆಲ್ ಸಾವಿರದ ಇನ್ನೂರು",
            db=db,
        )
        assert turn_out["intent"] == "log_entries"
        assert turn_out["decision"] == "confirm"
        assert turn_out["ask_confirmation"] is True
        assert "ಉಳಿಸಲೇ?" in turn_out["reply_kn"]

        # VERIFY: Zero unconfirmed commit occurred in the DB
        count_after = (await db.execute(select(func.count(LedgerEntry.id)))).scalar_one()
        assert count_after == count_before, "CRITICAL: Unconfirmed voice write committed to DB prematurely!"

        # 2. User confirms with 'ಹೌದು' (yes)
        confirm_out = await VoiceOrchestrator.process_turn(
            session_token=token,
            user_phone="9876500021",
            role="fisher",
            transcript_override="ಹೌದು",
            db=db,
        )
        assert "ಉಳಿಸಿದ್ದೇನೆ" in confirm_out["reply_kn"]

        # VERIFY: Now the record IS safely committed
        count_final = (await db.execute(select(func.count(LedgerEntry.id)))).scalar_one()
        assert count_final > count_before, "Record failed to commit after explicit voice confirmation!"


# ==============================================================================
# QUALITY GATE G3: Multi-Role Safety Flow (Fisher -> Family -> Coast Guard)
# ==============================================================================
@pytest.mark.asyncio
async def test_g3_multirole_safety_flow(client: AsyncClient):
    """G3: Coordinated safety flow across Fisher, Family, and Coast Guard views."""
    # Step 1: Fisher starts trip
    trip_res = await client.post("/api/v1/trips/start", json={
        "phone": "9876500021",
        "crew_count": 3,
        "return_in_hours": 8,
    })
    assert trip_res.status_code == 200
    trip_id = trip_res.json()["trip_id"]

    # Step 2: Family view sees active trip
    fam_res1 = await client.get("/api/v1/family/status")
    assert fam_res1.status_code == 200
    assert fam_res1.json()["title"] == "Boat is out at sea"

    # Step 3: Fisher triggers SOS
    sos_op_id = f"sos_g3_{uuid.uuid4().hex[:8]}"
    sos_res = await client.post("/api/v1/trips/sos", json={
        "phone": "9876500021",
        "client_op_id": sos_op_id,
        "lat": 13.35,
        "lon": 74.69,
        "trip_id": trip_id,
    })
    assert sos_res.status_code == 200
    assert sos_res.json()["status"] == "sos_active"

    # Step 4: Family view immediately shows Red SOS alert banner
    fam_res2 = await client.get("/api/v1/family/status")
    assert fam_res2.status_code == 200
    assert "SOS" in (fam_res2.json()["alert_banner"] or "")
    assert fam_res2.json()["alert_type"] == "red"

    # Step 5: Coast Guard watch shows active emergency
    guard_res = await client.get("/api/v1/guard/watch")
    assert guard_res.status_code == 200
    assert guard_res.json()["has_active_emergency"] is True

    # Step 6: Coast Guard dispatches rescue
    disp_res = await client.post("/api/v1/guard/dispatch", json={"incident_id": "active"})
    assert disp_res.status_code == 200
    assert disp_res.json()["status"] == "dispatched"

    # Step 7: Emergency resolved on Coast Guard watch
    guard_res2 = await client.get("/api/v1/guard/watch")
    assert guard_res2.json()["has_active_emergency"] is False


# ==============================================================================
# QUALITY GATE G4: Offline Outbox Idempotency with Zero Duplicates
# ==============================================================================
@pytest.mark.asyncio
async def test_g4_idempotent_outbox(client: AsyncClient):
    """G4: Replaying offline outbox batches with client_op_id produces zero duplicate records."""
    unique_op_1 = f"sync_op_g4_{uuid.uuid4().hex[:10]}"
    unique_op_2 = f"sync_op_g4_{uuid.uuid4().hex[:10]}"

    batch_payload = {
        "operations": [
            {
                "client_op_id": unique_op_1,
                "op_type": "ledger_sale",
                "phone": "9876500021",
                "payload": {"amount": 2500.0, "description": "25 kg mackerel offshore"}
            },
            {
                "client_op_id": unique_op_2,
                "op_type": "fish_spot",
                "phone": "9876500021",
                "payload": {"lat": 13.38, "lon": 74.65, "note": "deep spot"}
            }
        ]
    }

    # 1. First sync submission
    res1 = await client.post("/api/v1/sync/outbox", json=batch_payload)
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["synced"] == 2
    assert d1["duplicates_skipped"] == 0

    # 2. Replay the exact same sync batch (simulating reconnection jitter or duplicate retry)
    res2 = await client.post("/api/v1/sync/outbox", json=batch_payload)
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["synced"] == 0, "Duplicate operation was erroneously synced!"
    assert d2["duplicates_skipped"] == 2, "Duplicate operation was not skipped!"

    # 3. Verify in DB that only exactly one row exists for each client_op_id
    async with async_session() as db:
        q_entries = await db.execute(select(LedgerEntry).where(LedgerEntry.client_op_id == unique_op_1))
        assert len(q_entries.scalars().all()) == 1, "Duplicate ledger entry found in DB!"


# ==============================================================================
# QUALITY GATE G5: Spec v1.1 Mobile Tracking, Health Heartbeat & Version Gate
# ==============================================================================
@pytest.mark.asyncio
async def test_g5_v11_mobile_tracking_and_health(client: AsyncClient):
    """G5: Verify device registration, N-15 degraded heartbeat alerts, GPS deduplication, version gate, and admin overview."""
    # 1. Device Registration (D17, D18)
    reg_res = await client.post("/api/v1/devices/register", json={
        "phone": "9876500021",
        "platform": "android",
        "push_token": "fcm_token_g5_test",
        "app_version": "1.1.0",
        "os_version": "Android 14",
        "device_model": "Xiaomi Redmi Note 12 5G",
        "locale": "kn-IN",
    })
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert reg_data["status"] == "registered"
    device_id = reg_data["device_id"]

    # 2. Healthy & Degraded Heartbeats (D17, N-15)
    h_res = await client.post("/api/v1/devices/health", json={
        "device_id": device_id,
        "phone": "9876500021",
        "tracking_state": "running",
        "location_permission": "always",
        "battery_pct": 86,
        "reason": "Foreground service running",
    })
    assert h_res.status_code == 200
    assert h_res.json()["tracking_state"] == "running"

    # Degraded heartbeat creates N-15 Alert
    deg_res = await client.post("/api/v1/devices/health", json={
        "device_id": device_id,
        "phone": "9876500021",
        "tracking_state": "degraded",
        "location_permission": "always",
        "battery_pct": 14,
        "reason": "Battery manager killed service (N-15)",
    })
    assert deg_res.status_code == 200
    assert deg_res.json()["tracking_state"] == "degraded"

    async with async_session() as db:
        a_res = await db.execute(select(Alert).where(Alert.alert_type == "tracking_degraded"))
        alerts = a_res.scalars().all()
        assert len(alerts) > 0, "N-15 tracking degraded alert was not created!"

    # 3. OEM Battery Guidance (FR-SET-02)
    gh_res = await client.get("/api/v1/devices/health?phone=9876500021")
    assert gh_res.status_code == 200
    gh_data = gh_res.json()
    assert "oem_guidance" in gh_data
    assert "Battery" in gh_data["oem_guidance"] or "restrictions" in gh_data["oem_guidance"]

    # 4. Batched GPS Positions Deduplication (TR-CLI-11, TR-OFF-03)
    pos_op_1 = f"pos_g5_{uuid.uuid4().hex[:8]}"
    pos_op_2 = f"pos_g5_{uuid.uuid4().hex[:8]}"
    batch_pos = {
        "phone": "9876500021",
        "positions": [
            {"lat": 13.35, "lon": 74.69, "speed_kn": 6.8, "client_op_id": pos_op_1},
            {"lat": 13.36, "lon": 74.68, "speed_kn": 7.0, "client_op_id": pos_op_2},
            {"lat": 13.36, "lon": 74.68, "speed_kn": 7.0, "client_op_id": pos_op_1},  # Duplicate op
        ],
    }
    p_res = await client.post("/api/v1/trips/positions", json=batch_pos)
    assert p_res.status_code == 200
    p_data = p_res.json()
    assert p_data["saved"] == 2
    assert p_data["duplicates_skipped"] == 1
    assert p_data["continuity_pct"] > 90.0

    # 5. Remote Version Gate (TR-CLI-15)
    v11_res = await client.get("/api/v1/app/version?client_version=1.1.0")
    assert v11_res.status_code == 200
    assert v11_res.json()["force_update"] is False

    v10_res = await client.get("/api/v1/app/version?client_version=1.0.0")
    assert v10_res.status_code == 200
    assert v10_res.json()["force_update"] is True

    # 6. Admin Console Overview (ADM-1 - ADM-5)
    adm_res = await client.get("/api/v1/admin/overview")
    assert adm_res.status_code == 200
    adm_data = adm_res.json()
    assert adm_data["alias_count"] > 0
    assert adm_data["user_count"] > 0

