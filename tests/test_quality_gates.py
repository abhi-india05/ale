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
