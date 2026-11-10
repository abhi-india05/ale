# WHY: D1, D3, FR-AUTH-01, FR-GEO-01, FR-PRC-01 — Comprehensive Malpe Harbour & Personas Seed Data
"""Seed script for Malpe Harbour, synthetic demo personas, fish prices, and aliases."""

import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from apps.api.core.database import async_session, init_db, engine
from apps.api.models import (
    Harbour,
    User,
    FisherProfile,
    Boat,
    FishSpecies,
    FishAlias,
    MarketPrice,
    WeatherRule,
    WeatherSnapshot,
    LedgerEntry,
    Device,
    DeviceHealthReport,
    FeatureFlag,
)


async def seed_database():
    """Populate database with harbours, species, prices, rules, and demo personas."""
    await init_db()

    async with async_session() as session:
        # Check if already seeded
        result = await session.execute(select(Harbour).limit(1))
        if result.scalar_one_or_none():
            await seed_v11_defaults(session)
            print("Database already contains core seed data. Ensured v1.1 flags & device health.")
            return

        print("Seeding Ale Voice database...")

        # 1. Coastal Karnataka Harbours
        malpe = Harbour(name="Malpe", code="MALPE", lat=13.3496, lon=74.7039)
        mangaluru = Harbour(name="Mangaluru", code="MANG", lat=12.8654, lon=74.8426)
        gangolli = Harbour(name="Gangolli", code="GANG", lat=13.6235, lon=74.6498)
        honnavar = Harbour(name="Honnavar", code="HONN", lat=14.2816, lon=74.4444)

        session.add_all([malpe, mangaluru, gangolli, honnavar])
        await session.flush()

        # 2. Weather Rules for Harbours
        for h in [malpe, mangaluru, gangolli, honnavar]:
            rule = WeatherRule(
                harbour_id=h.id,
                wind_kmh_amber=25.0,
                wind_kmh_red=40.0,
                wave_m_amber=1.8,
                wave_m_red=3.0,
            )
            session.add(rule)

        # 3. Initial Dawn Weather Snapshot (Malpe)
        snap = WeatherSnapshot(
            harbour_id=malpe.id,
            wind_kmh=12.0,
            wave_m=0.8,
            verdict="go",
            kn_summary="ಹೋಗಬಹುದು. ಗಾಳಿ ಹನ್ನೆರಡು ಕಿಲೋಮೀಟರ್, ಅಲೆ ಒಂದು ಮೀಟರ್ ಒಳಗೆ.",
            en_summary="Go. Wind 12 km/h, waves under 1 m.",
            raw_payload='{"source": "seed_dawn", "tide": "High 6:12 · Low 12:30"}',
        )
        session.add(snap)

        # 4. Fish Species
        sardine = FishSpecies(
            name_en="Sardine",
            name_kn="ಬೂತಾಯಿ",
            scientific_name="Sardinella longiceps",
            emoji="🐟",
        )
        mackerel = FishSpecies(
            name_en="Mackerel",
            name_kn="ಬಂಗುಡೆ",
            scientific_name="Rastrelliger kanagurta",
            emoji="🐠",
        )
        pomfret = FishSpecies(
            name_en="Pomfret",
            name_kn="ಮಾಂಜಿ",
            scientific_name="Pampus argenteus",
            emoji="🐡",
        )
        prawns = FishSpecies(
            name_en="Prawns",
            name_kn="ಸಿಗಡಿ",
            scientific_name="Penaeus monodon",
            emoji="🦐",
        )

        session.add_all([sardine, mackerel, pomfret, prawns])
        await session.flush()

        # 5. Fish Aliases (Phonetic & Code-mixed)
        aliases_data = [
            (sardine.id, "boothaayi", "en"),
            (sardine.id, "butai", "en"),
            (sardine.id, "mathi", "kn"),
            (sardine.id, "ಬೂತಾಯಿ", "kn"),
            (sardine.id, "tarli", "kn"),
            (mackerel.id, "bangude", "en"),
            (mackerel.id, "ayala", "kn"),
            (mackerel.id, "ಬಂಗುಡೆ", "kn"),
            (mackerel.id, "bangada", "en"),
            (pomfret.id, "maanji", "en"),
            (pomfret.id, "ಮಾಂಜಿ", "kn"),
            (pomfret.id, "paplet", "en"),
            (pomfret.id, "white pomfret", "en"),
            (prawns.id, "sigadi", "en"),
            (prawns.id, "ಸಿಗಡಿ", "kn"),
            (prawns.id, "shrimp", "en"),
            (prawns.id, "jhinga", "en"),
        ]
        for sp_id, alias_text, lang in aliases_data:
            session.add(FishAlias(species_id=sp_id, alias=alias_text, language=lang))

        # 6. Market Prices (Malpe)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        prices_data = [
            (sardine.id, 90.0, 110.0),
            (mackerel.id, 140.0, 170.0),
            (pomfret.id, 620.0, 760.0),
            (prawns.id, 380.0, 450.0),
        ]
        for sp_id, lo, hi in prices_data:
            session.add(MarketPrice(
                species_id=sp_id,
                harbour_id=malpe.id,
                price_low=lo,
                price_high=hi,
                effective_date=today,
            ))

        # 7. Synthetic Demo Personas
        # Suresh (Fisher)
        suresh = User(
            phone="9876500021",
            role="fisher",
            name="Suresh Poojary",
            harbour_id=malpe.id,
        )
        session.add(suresh)
        await session.flush()

        # Suresh's Profile & Boat
        suresh_prof = FisherProfile(
            user_id=suresh.id,
            boat_name="Ale-Malpe-07",
            emergency_phone="9876500012",
            safe_zone_km=10,
        )
        suresh_boat = Boat(
            name="Ale-Malpe-07",
            reg_number="IND-KA-02-MM-1042",
            harbour_id=malpe.id,
            owner_user_id=suresh.id,
        )
        session.add_all([suresh_prof, suresh_boat])

        # Lakshmi (Family)
        lakshmi = User(
            phone="9876500012",
            role="family",
            name="Lakshmi",
            harbour_id=malpe.id,
        )
        session.add(lakshmi)

        # Rafiq (Buyer)
        rafiq = User(
            phone="9876500031",
            role="buyer",
            name="Rafiq",
            harbour_id=malpe.id,
        )
        session.add(rafiq)

        # Inspector Naik (Coast Guard)
        naik = User(
            phone="9876500041",
            role="guard",
            name="Insp. Naik",
            harbour_id=malpe.id,
        )
        session.add(naik)

        # 8. Suresh Initial Ledger Entries (Matches Prototype: Sold 18,400, Fuel 5,200)
        session.add(LedgerEntry(
            user_id=suresh.id,
            entry_type="sale",
            amount=18400.0,
            description="Catch sale: 40 kg Sardine & 80 kg Mackerel",
            species_id=sardine.id,
            quantity_kg=120.0,
            client_op_id="seed_sale_01",
        ))
        session.add(LedgerEntry(
            user_id=suresh.id,
            entry_type="expense",
            amount=5200.0,
            description="Diesel fuel & ice",
            client_op_id="seed_fuel_01",
        ))

        await seed_v11_defaults(session)

        await session.commit()
        print("Database successfully seeded with Malpe Harbour, Personas, Prices, and v1.1 Defaults!")


# WHY: FR-APP-01, FR-SEA-07, TR-CLI-12, TR-CLI-15 — Default feature flags and Android device health seed
async def seed_v11_defaults(session):
    """Seed feature flags, Suresh's Xiaomi Redmi Note 12 device and initial health report."""
    flags = [
        ("min_app_version", True, '{"min_version": "1.1.0", "current_version": "1.1.0", "play_store_url": "https://play.google.com/store/apps/details?id=in.alevoice.mobile", "apk_download_url": "/downloads/ale-v1.1.0.apk"}'),
        ("llm_fallback", False, '{"mode": "offline_first", "timeout_ms": 1500}'),
        ("helpline", True, '{"number": "1554", "label_kn": "ಕರಾವಳಿ ಕಾವಲು ಪಡೆ (1554)"}'),
        ("inspector", True, '{"allowed_roles": ["guard", "admin"]}'),
    ]
    for key, enabled, payload in flags:
        res = await session.execute(select(FeatureFlag).where(FeatureFlag.key == key))
        if not res.scalar_one_or_none():
            session.add(FeatureFlag(key=key, enabled=enabled, payload_json=payload))

    # Suresh's Android Device & Health
    u_res = await session.execute(select(User).where(User.phone == "9876500021"))
    suresh = u_res.scalar_one_or_none()
    if suresh:
        d_res = await session.execute(select(Device).where(Device.user_id == suresh.id))
        dev = d_res.scalar_one_or_none()
        if not dev:
            dev = Device(
                user_id=suresh.id,
                platform="android",
                push_provider="fcm",
                push_token="fcm_token_suresh_redmi12_demo",
                app_version="1.1.0",
                os_version="Android 14 (HyperOS)",
                device_model="Xiaomi Redmi Note 12 5G",
                locale="kn-IN",
            )
            session.add(dev)
            await session.flush()

        h_res = await session.execute(select(DeviceHealthReport).where(DeviceHealthReport.user_id == suresh.id))
        if not h_res.scalar_one_or_none():
            session.add(DeviceHealthReport(
                device_id=dev.id,
                user_id=suresh.id,
                tracking_state="running",
                location_permission="always",
                notifications_enabled=True,
                battery_optimised=False,
                gps_enabled=True,
                battery_pct=86,
                network="good",
                reason="Foreground service active with ongoing notification (Spec v1.1 D17).",
            ))

    await session.commit()


async def main():
    try:
        await seed_database()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
