# WHY: G1, G2, G3, G4, TR-TEST-01 — Direct runner for Quality Gates G1–G4 without external plugins
"""Quality Gates Test Runner for Ale Voice."""

import os
import sys

# Ensure repository root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import time
from httpx import AsyncClient, ASGITransport

from apps.api.main import app
from apps.api.core.database import init_db, engine
from tests.test_quality_gates import (
    test_g1_readonly_intents_and_latency,
    test_g2_zero_unconfirmed_voice_writes,
    test_g3_multirole_safety_flow,
    test_g4_idempotent_outbox,
    test_g5_v11_mobile_tracking_and_health,
)


async def main():
    print("=" * 60)
    print("ALE VOICE — QUALITY GATES G1–G5 VERIFICATION SUITE (SPEC v1.1)")
    print("=" * 60)

    await init_db()
    transport = ASGITransport(app=app)

    # Gate G1
    print("\n▶ Running Quality Gate G1 (Read-Only Kannada Intents & Stage Latencies)...")
    t0 = time.perf_counter()
    await test_g1_readonly_intents_and_latency()
    print(f"✔ G1 PASSED ({int((time.perf_counter() - t0) * 1000)} ms)")

    # Gate G2
    print("\n▶ Running Quality Gate G2 (Zero Unconfirmed Voice Writes)...")
    t0 = time.perf_counter()
    await test_g2_zero_unconfirmed_voice_writes()
    print(f"✔ G2 PASSED ({int((time.perf_counter() - t0) * 1000)} ms)")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Gate G3
        print("\n▶ Running Quality Gate G3 (Multi-Role Safety Flow: Fisher -> Family -> Coast Guard)...")
        t0 = time.perf_counter()
        await test_g3_multirole_safety_flow(client)
        print(f"✔ G3 PASSED ({int((time.perf_counter() - t0) * 1000)} ms)")

        # Gate G4
        print("\n▶ Running Quality Gate G4 (Offline Outbox Zero-Duplicate Idempotency)...")
        t0 = time.perf_counter()
        await test_g4_idempotent_outbox(client)
        print(f"✔ G4 PASSED ({int((time.perf_counter() - t0) * 1000)} ms)")

        # Gate G5
        print("\n▶ Running Quality Gate G5 (v1.1 Mobile Tracking, Health Heartbeat & Version Gate)...")
        t0 = time.perf_counter()
        await test_g5_v11_mobile_tracking_and_health(client)
        print(f"✔ G5 PASSED ({int((time.perf_counter() - t0) * 1000)} ms)")

    print("\n" + "=" * 60)
    print("ALL 5 QUALITY GATES (G1, G2, G3, G4, G5) PASSED PERFECTLY!")
    print("=" * 60)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
