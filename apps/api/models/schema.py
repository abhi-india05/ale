# WHY: D1, D4, D8, D11, D12, TR-DATA-01, TR-INFRA-01 — Protected Core 23 SQLAlchemy 2 Models
"""Ale Voice Protected Core Database Models with SQLite/Postgres compatibility."""

from datetime import datetime, timezone
from typing import Optional, List
import json
import uuid

from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.models.base import Base, IdMixin, TimestampMixin


# WHY: TR-DATA-02, FR-GEO-01 — 4 Coastal Karnataka Harbours
class Harbour(Base, IdMixin, TimestampMixin):
    """Malpe, Mangaluru, Gangolli, Honnavar harbour reference points."""
    __tablename__ = "harbours"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    state: Mapped[str] = mapped_column(String(30), default="Karnataka", nullable=False)

    users: Mapped[List["User"]] = relationship(back_populates="harbour")
    boats: Mapped[List["Boat"]] = relationship(back_populates="harbour")
    market_prices: Mapped[List["MarketPrice"]] = relationship(back_populates="harbour")


# WHY: FR-AUTH-01, TR-AUTH-01 — 4 Distinct Personas (Fisher, Family, Buyer, Guard)
class User(Base, IdMixin, TimestampMixin):
    """Platform users identified by phone number."""
    __tablename__ = "users"

    phone: Mapped[str] = mapped_column(String(15), unique=True, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # fisher, family, buyer, guard
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    harbour_id: Mapped[Optional[str]] = mapped_column(ForeignKey("harbours.id"), nullable=True)

    harbour: Mapped[Optional["Harbour"]] = relationship(back_populates="users")
    fisher_profile: Mapped[Optional["FisherProfile"]] = relationship(back_populates="user", uselist=False)
    boats: Mapped[List["Boat"]] = relationship(back_populates="owner")
    trips: Mapped[List["Trip"]] = relationship(back_populates="fisher")
    ledger_entries: Mapped[List["LedgerEntry"]] = relationship(back_populates="user")
    devices: Mapped[List["Device"]] = relationship(back_populates="user")


# WHY: FR-PROF-01, FR-PROF-02 — Fisher-specific profile settings & emergency contacts
class FisherProfile(Base, IdMixin, TimestampMixin):
    """Extended profile for fishers with emergency contact and boat mapping."""
    __tablename__ = "fisher_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    boat_name: Mapped[str] = mapped_column(String(100), nullable=False)
    emergency_phone: Mapped[str] = mapped_column(String(15), nullable=False)
    safe_zone_km: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="fisher_profile")


# WHY: FR-BOAT-01, TR-MAP-01 — Boats operating out of harbours
class Boat(Base, IdMixin, TimestampMixin):
    """Boats tracked for trip safety and incoming catches."""
    __tablename__ = "boats"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    reg_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    harbour_id: Mapped[str] = mapped_column(ForeignKey("harbours.id"), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    harbour: Mapped["Harbour"] = relationship(back_populates="boats")
    owner: Mapped["User"] = relationship(back_populates="boats")
    trips: Mapped[List["Trip"]] = relationship(back_populates="boat")


# WHY: FR-VOX-02, TR-NLU-01 — 4 Core Fish Species with Kannada and English names
class FishSpecies(Base, IdMixin, TimestampMixin):
    """Fish master catalogue with multilingual names and display emojis."""
    __tablename__ = "fish_species"

    name_en: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_kn: Mapped[str] = mapped_column(String(50), nullable=False)
    scientific_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    emoji: Mapped[str] = mapped_column(String(10), default="🐟", nullable=False)

    aliases: Mapped[List["FishAlias"]] = relationship(back_populates="species")
    prices: Mapped[List["MarketPrice"]] = relationship(back_populates="species")


# WHY: TR-NLU-02, D15 — Phonetic, regional, and code-mixed aliases for STT matching
class FishAlias(Base, IdMixin, TimestampMixin):
    """Phonetic and colloquial variants (e.g. boothaayi, butai, mathi)."""
    __tablename__ = "fish_aliases"

    species_id: Mapped[str] = mapped_column(ForeignKey("fish_species.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="kn", nullable=False)

    species: Mapped["FishSpecies"] = relationship(back_populates="aliases")


# WHY: FR-PRC-01, TR-PRC-01 — Fair Price Board daily reference ranges
class MarketPrice(Base, IdMixin, TimestampMixin):
    """Daily low and high price bands (₹/kg) per species per harbour."""
    __tablename__ = "market_prices"

    species_id: Mapped[str] = mapped_column(ForeignKey("fish_species.id"), nullable=False)
    harbour_id: Mapped[str] = mapped_column(ForeignKey("harbours.id"), nullable=False)
    price_low: Mapped[float] = mapped_column(Float, nullable=False)
    price_high: Mapped[float] = mapped_column(Float, nullable=False)
    effective_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD

    species: Mapped["FishSpecies"] = relationship(back_populates="prices")
    harbour: Mapped["Harbour"] = relationship(back_populates="market_prices")


# WHY: FR-WTH-01, TR-WTH-01 — Threshold rules for Go / Be careful / Don't go
class WeatherRule(Base, IdMixin, TimestampMixin):
    """Thresholds determining maritime danger levels."""
    __tablename__ = "weather_rules"

    harbour_id: Mapped[str] = mapped_column(ForeignKey("harbours.id"), nullable=False)
    wind_kmh_amber: Mapped[float] = mapped_column(Float, default=25.0, nullable=False)
    wind_kmh_red: Mapped[float] = mapped_column(Float, default=40.0, nullable=False)
    wave_m_amber: Mapped[float] = mapped_column(Float, default=1.8, nullable=False)
    wave_m_red: Mapped[float] = mapped_column(Float, default=3.0, nullable=False)


# WHY: FR-WTH-02, TR-WTH-02, D13 — Cached Dawn weather snapshots
class WeatherSnapshot(Base, IdMixin, TimestampMixin):
    """Hourly or dawn weather status for instant and offline recovery."""
    __tablename__ = "weather_snapshots"

    harbour_id: Mapped[str] = mapped_column(ForeignKey("harbours.id"), nullable=False)
    wind_kmh: Mapped[float] = mapped_column(Float, nullable=False)
    wave_m: Mapped[float] = mapped_column(Float, nullable=False)
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)  # go, caution, no_go
    kn_summary: Mapped[str] = mapped_column(Text, nullable=False)
    en_summary: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# WHY: FR-TRP-01, TR-TRP-01, G3 — Active and completed fishing voyages
class Trip(Base, IdMixin, TimestampMixin):
    """Voyage lifecycle: out -> returning -> landed or overdue."""
    __tablename__ = "trips"

    boat_id: Mapped[str] = mapped_column(ForeignKey("boats.id"), nullable=False)
    fisher_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    crew_count: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    departed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expected_back_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    landed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="out", nullable=False)  # out, returning, landed, overdue, sos
    eta_text: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    boat: Mapped["Boat"] = relationship(back_populates="trips")
    fisher: Mapped["User"] = relationship(back_populates="trips")
    checks: Mapped[List["TripCheck"]] = relationship(back_populates="trip")
    spots: Mapped[List["FishSpot"]] = relationship(back_populates="trip")
    landings: Mapped[List["Landing"]] = relationship(back_populates="trip")
    positions: Mapped[List["TripPosition"]] = relationship(back_populates="trip")


# WHY: FR-TRP-02, FR-VOX-06 — Safety pre-sail checklist items
class TripCheck(Base, IdMixin, TimestampMixin):
    """Safety checklist items (life jackets, fuel, ice/water, phone charged)."""
    __tablename__ = "trip_checks"

    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), nullable=False)
    check_key: Mapped[str] = mapped_column(String(50), nullable=False)
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    trip: Mapped["Trip"] = relationship(back_populates="checks")


# WHY: FR-MAP-02, FR-VOX-05 — GPS fish spot marking via voice or button
class FishSpot(Base, IdMixin, TimestampMixin):
    """Geo-located catch spots visible privately to boat crew."""
    __tablename__ = "fish_spots"

    trip_id: Mapped[Optional[str]] = mapped_column(ForeignKey("trips.id"), nullable=True)
    fisher_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    species_id: Mapped[Optional[str]] = mapped_column(ForeignKey("fish_species.id"), nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    visible_to: Mapped[str] = mapped_column(String(20), default="crew", nullable=False)

    trip: Mapped[Optional["Trip"]] = relationship(back_populates="spots")


# WHY: FR-LND-01, FR-VOX-07 — Catch announcements for prospective buyers
class Landing(Base, IdMixin, TimestampMixin):
    """Fisher catch notice sent ~40 min prior to harbour docking."""
    __tablename__ = "landings"

    trip_id: Mapped[Optional[str]] = mapped_column(ForeignKey("trips.id"), nullable=True)
    fisher_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    harbour_id: Mapped[str] = mapped_column(ForeignKey("harbours.id"), nullable=False)
    species_id: Mapped[str] = mapped_column(ForeignKey("fish_species.id"), nullable=False)
    quantity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    eta_min: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="announced", nullable=False)  # announced, sold, cancelled

    trip: Mapped[Optional["Trip"]] = relationship(back_populates="landings")
    bids: Mapped[List["Bid"]] = relationship(back_populates="landing")


# WHY: FR-BID-01, TR-BID-01 — Buyer offers submitted in response to landings
class Bid(Base, IdMixin, TimestampMixin):
    """Offers from local buyers/agents per kg of catch."""
    __tablename__ = "bids"

    landing_id: Mapped[str] = mapped_column(ForeignKey("landings.id"), nullable=False)
    buyer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    buyer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bid_price_per_kg: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, accepted, rejected

    landing: Mapped["Landing"] = relationship(back_populates="bids")


# WHY: FR-DIR-01, FR-VOX-04, D8, D12, G4 — Earnings diary with offline idempotency
class LedgerEntry(Base, IdMixin, TimestampMixin):
    """Financial ledger for fish sales and trip expenses (fuel, ice)."""
    __tablename__ = "ledger_entries"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    trip_id: Mapped[Optional[str]] = mapped_column(ForeignKey("trips.id"), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)  # sale, expense
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    species_id: Mapped[Optional[str]] = mapped_column(ForeignKey("fish_species.id"), nullable=True)
    quantity_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    client_op_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True)

    user: Mapped["User"] = relationship(back_populates="ledger_entries")


# WHY: FR-SOS-01, TR-SOS-01, D9, D12, G3 — Physical 2-sec hold SOS event log
class SosEvent(Base, IdMixin, TimestampMixin):
    """High-priority distress alerts with client_op_id idempotency."""
    __tablename__ = "sos_events"

    client_op_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True)
    trip_id: Mapped[Optional[str]] = mapped_column(ForeignKey("trips.id"), nullable=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    boat_id: Mapped[Optional[str]] = mapped_column(ForeignKey("boats.id"), nullable=True)
    lat: Mapped[float] = mapped_column(Float, default=13.35, nullable=False)
    lon: Mapped[float] = mapped_column(Float, default=74.69, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active, dispatched, resolved
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# WHY: FR-CG-01, TR-CG-01 — Maritime incident logs for Coast Guard dashboard
class IncidentEvent(Base, IdMixin, TimestampMixin):
    """Incidents including overdue boats, boundary exit, and SOS."""
    __tablename__ = "incident_events"

    event_type: Mapped[str] = mapped_column(String(30), nullable=False)  # sos, overdue, boundary_exit, storm
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    boat_id: Mapped[Optional[str]] = mapped_column(ForeignKey("boats.id"), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="amber", nullable=False)  # ok, amber, red
    description: Mapped[str] = mapped_column(Text, nullable=False)


# WHY: FR-FAM-01, FR-NOT-01 — User notifications and role-specific alerts
class Alert(Base, IdMixin, TimestampMixin):
    """Notification stream for family members, coast guard, and fishers."""
    __tablename__ = "alerts"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# WHY: TR-VOX-01, TR-VOX-02 — Multi-turn voice conversation sessions
class VoiceSession(Base, IdMixin, TimestampMixin):
    """User voice dialogue session tracking state and pending confirmations."""
    __tablename__ = "voice_sessions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    session_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    turns: Mapped[List["VoiceTurn"]] = relationship(back_populates="session")


# WHY: TR-VOX-03, TR-VOX-04, D7, D8, G1, G2 — Full voice turn audit and timing logs
class VoiceTurn(Base, IdMixin, TimestampMixin):
    """Each individual voice exchange with latency breakdowns for the Inspector."""
    __tablename__ = "voice_turns"

    session_id: Mapped[Optional[str]] = mapped_column(ForeignKey("voice_sessions.id"), nullable=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    raw_audio_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    intent: Mapped[str] = mapped_column(String(50), nullable=False)
    slots_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pending_action_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    
    # Timing benchmarks in milliseconds
    stt_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nlu_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    action_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tts_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    session: Mapped[Optional["VoiceSession"]] = relationship(back_populates="turns")


# WHY: TR-TTS-01, D11 — Audio synthesis cache keyed by SHA-256(text+voice+model+format)
class TtsCache(Base, IdMixin, TimestampMixin):
    """Pre-computed or previously synthesized audio blobs to bypass Gnani call."""
    __tablename__ = "tts_cache"

    cache_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    voice: Mapped[str] = mapped_column(String(30), default="Lakshmi", nullable=False)
    model: Mapped[str] = mapped_column(String(30), default="timbre-v3.0", nullable=False)
    audio_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


# WHY: TR-SYNC-01, D12, G4 — Outbox operations queued offline by client_op_id
class OutboxOp(Base, IdMixin, TimestampMixin):
    """Idempotent sync log of voice and tap actions queued while offshore."""
    __tablename__ = "outbox_ops"

    client_op_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    op_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)  # queued, applied, conflict


# WHY: TR-SEC-01, TR-AUD-01 — Immutable audit log of all safety and financial changes
class AuditLog(Base, IdMixin, TimestampMixin):
    """Security and compliance traceability log."""
    __tablename__ = "audit_log"

    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# WHY: D17, D18, TR-CLI-14, TR-CLI-15 — Device registration & FCM push token management
class Device(Base, IdMixin, TimestampMixin):
    """Registered user device with push token, platform, and OS version."""
    __tablename__ = "devices"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), default="android", nullable=False)  # android, ios, web
    push_provider: Mapped[str] = mapped_column(String(20), default="fcm", nullable=False)
    push_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    app_version: Mapped[str] = mapped_column(String(20), default="1.1.0", nullable=False)
    os_version: Mapped[str] = mapped_column(String(50), default="Android 14", nullable=False)
    device_model: Mapped[str] = mapped_column(String(100), default="Redmi Note 12", nullable=False)
    locale: Mapped[str] = mapped_column(String(10), default="kn", nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user: Mapped["User"] = relationship(back_populates="devices")
    health_reports: Mapped[List["DeviceHealthReport"]] = relationship(back_populates="device")


# WHY: FR-SEA-07, FR-SET-02, TR-CLI-12, D17 — PRO-2 Tracking Health & OEM Battery Monitor
class DeviceHealthReport(Base, IdMixin, TimestampMixin):
    """Device tracking health heartbeat feeding PRO-2 screen and family last-seen."""
    __tablename__ = "device_health_reports"

    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    trip_id: Mapped[Optional[str]] = mapped_column(ForeignKey("trips.id"), nullable=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    tracking_state: Mapped[str] = mapped_column(String(20), default="running", nullable=False)  # running, degraded, stopped
    location_permission: Mapped[str] = mapped_column(String(20), default="always", nullable=False)  # none, foreground, always
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    battery_optimised: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gps_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    battery_pct: Mapped[int] = mapped_column(Integer, default=86, nullable=False)
    network: Mapped[str] = mapped_column(String(20), default="good", nullable=False)  # good, poor, none
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    device: Mapped["Device"] = relationship(back_populates="health_reports")


# WHY: FR-SEA-02, TR-CLI-11, TR-OFF-03, D17 — Screen-off 60s foreground location track
class TripPosition(Base, IdMixin, TimestampMixin):
    """Batched GPS positions uploaded by Android background location service."""
    __tablename__ = "trip_positions"

    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    speed_kn: Mapped[float] = mapped_column(Float, default=6.5, nullable=False)
    heading: Mapped[float] = mapped_column(Float, default=240.0, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), default="gps", nullable=False)  # gps, fused, network
    battery_pct: Mapped[int] = mapped_column(Integer, default=86, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    client_op_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    trip: Mapped["Trip"] = relationship(back_populates="positions")


# WHY: FR-APP-01, TR-CLI-15 — Remote feature flags and minimum supported client versions
class FeatureFlag(Base):
    """Dynamic platform toggles and minimum app version gating."""
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
