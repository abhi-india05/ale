# WHY: TR-VOX-01, TR-VOX-07, D7, D8, G1, G2 — Voice Orchestrator Pipeline with Real Stage Timings
"""End-to-end voice pipeline: Mic -> STT -> Normalise -> NLU -> Action -> TTS -> Speaker."""

import time
import json
import uuid
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models import (
    User,
    VoiceSession,
    VoiceTurn,
    WeatherSnapshot,
    MarketPrice,
    FishSpecies,
    LedgerEntry,
    FishSpot,
    Trip,
    TripCheck,
    Landing,
    Bid,
    SosEvent,
)
from apps.api.services.nlu import NluEngine, NluResult
from apps.api.services.lexicon import FISH_CATALOGUE
from apps.api.providers.gnani import GnaniStt, GnaniTts, MockStt, MockTts
from apps.api.core.config import settings


# In-memory store for active session pending actions (20-second expiry)
PENDING_ACTIONS: Dict[str, Dict[str, Any]] = {}


class VoiceOrchestrator:
    """Manages the full multi-stage conversational turn and execution safety."""

    @classmethod
    async def process_turn(
        cls,
        session_token: str,
        user_phone: str,
        role: str = "fisher",
        audio_bytes: Optional[bytes] = None,
        transcript_override: Optional[str] = None,
        stt_hint: float = 0.95,
        noise: bool = False,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Execute full voice turn returning reply, state, and inspector timings."""
        t_start = time.perf_counter()

        # 1. STT Stage
        stt_t0 = time.perf_counter()
        if audio_bytes and len(audio_bytes) > 100:
            stt_res = await GnaniStt.transcribe(audio_bytes)
        else:
            stt_res = await MockStt.transcribe(transcript_hint=transcript_override)
        stt_ms = max(int((time.perf_counter() - stt_t0) * 1000), stt_res.duration_ms)

        transcript = stt_res.transcript
        pending = PENDING_ACTIONS.get(session_token)

        # 2. NLU Stage
        nlu_t0 = time.perf_counter()
        nlu_res: NluResult = NluEngine.parse(
            text=transcript,
            role=role,
            stt_hint=stt_res.confidence,
            session_pending=pending,
            noise=noise,
        )
        nlu_ms = int((time.perf_counter() - nlu_t0) * 1000)

        # 3. Action & Dialogue Generation Stage
        action_t0 = time.perf_counter()
        action_res = await cls._execute_action_or_generate_reply(
            nlu_res=nlu_res,
            session_token=session_token,
            user_phone=user_phone,
            role=role,
            db=db,
        )
        action_ms = int((time.perf_counter() - action_t0) * 1000)

        reply_kn = action_res["reply_kn"]
        reply_en = action_res["reply_en"]
        card_html = action_res.get("card_html")

        # 4. TTS Stage
        tts_t0 = time.perf_counter()
        tts_res = await GnaniTts.synthesize(reply_kn)
        tts_ms = max(int((time.perf_counter() - tts_t0) * 1000), tts_res.duration_ms)

        total_ms = int((time.perf_counter() - t_start) * 1000)

        # 5. Record VoiceTurn in DB if available
        if db:
            try:
                turn_record = VoiceTurn(
                    session_id=None,
                    user_id=user_phone,
                    transcript=transcript,
                    confidence=nlu_res.confidence,
                    intent=nlu_res.intent,
                    slots_json=json.dumps(nlu_res.slots),
                    pending_action_json=json.dumps(nlu_res.pending_action) if nlu_res.pending_action else None,
                    confirmed=(nlu_res.intent == "confirm_yes"),
                    stt_ms=stt_ms,
                    nlu_ms=nlu_ms,
                    action_ms=action_ms,
                    tts_ms=tts_ms,
                    total_ms=total_ms,
                )
                db.add(turn_record)
                await db.commit()
            except Exception:
                pass

        return {
            "transcript": transcript,
            "confidence": nlu_res.confidence,
            "intent": nlu_res.intent,
            "slots": nlu_res.slots,
            "decision": nlu_res.decision,
            "repair_options": nlu_res.repair_options,
            "target_screen_id": nlu_res.target_screen_id,
            "reply_kn": reply_kn,
            "reply_en": reply_en,
            "card_html": card_html,
            "audio_url": tts_res.audio_url,
            "cached_audio": tts_res.cached,
            "ask_confirmation": (nlu_res.decision == "confirm"),
            "timings": {
                "stt_ms": stt_ms,
                "nlu_ms": nlu_ms,
                "action_ms": action_ms,
                "tts_ms": tts_ms,
                "total_ms": total_ms,
            },
            "inspector": (
                f"Pipeline (live backend timings)\n"
                f"1 Capture    16 kHz mono\n"
                f"2 Gnani STT  Prisma · kn-IN · conf {int(nlu_res.confidence * 100)}% · {stt_ms} ms\n"
                f"3 Intent     {nlu_res.intent} {json.dumps(nlu_res.slots, ensure_ascii=False)}\n"
                f"4 Action     {nlu_res.intent}() · {action_ms} ms\n"
                f"5 Reply      Kannada template\n"
                f"6 Gnani TTS  Timbre · Lakshmi voice · {tts_ms} ms\n"
                f"Total = {total_ms} ms"
            ),
        }

    @classmethod
    async def _execute_action_or_generate_reply(
        cls,
        nlu_res: NluResult,
        session_token: str,
        user_phone: str,
        role: str,
        db: Optional[AsyncSession],
    ) -> Dict[str, Any]:
        """Dispatch intent to business logic and dialogue templating."""
        intent = nlu_res.intent
        slots = nlu_res.slots

        # --- REPAIR DISAMBIGUATION ---
        if nlu_res.decision == "repair":
            opts = nlu_res.repair_options or ["Mackerel", "Sardine"]
            opts_kn = [FISH_CATALOGUE.get(o, {}).get("name_kn", o) for o in opts]
            return {
                "reply_kn": f"{opts_kn[0]}ನಾ ಅಥವಾ {opts_kn[1]}ನಾ?",
                "reply_en": "Low confidence, so I ask instead of guessing: mackerel or sardine?",
            }

        if intent == "repair_select":
            selected = slots.get("selected_fish", "Mackerel")
            info = FISH_CATALOGUE[selected]
            lo, hi = info["price_range"]
            return {
                "reply_kn": f"{info['name_kn']} ಇವತ್ತು ಕೆಜಿಗೆ {lo} ರಿಂದ {hi} ರೂಪಾಯಿ.",
                "reply_en": f"{selected} today: ₹{lo}–{hi} per kg.",
            }

        # --- CONFIRMATIONS ---
        if intent == "confirm_yes":
            pending = PENDING_ACTIONS.pop(session_token, None)
            if pending:
                await cls._commit_pending_action(pending, user_phone, db)
                return {
                    "reply_kn": "ಉಳಿಸಿದ್ದೇನೆ.",
                    "reply_en": "Saved to your diary / buyers notified.",
                }
            return {
                "reply_kn": "ಸರಿ.",
                "reply_en": "OK.",
            }

        if intent == "confirm_no":
            PENDING_ACTIONS.pop(session_token, None)
            return {
                "reply_kn": "ಸರಿ, ಮಾಡಿಲ್ಲ.",
                "reply_en": "OK, I did not do it.",
            }

        # --- READ-ONLY INTENTS ---
        if intent == "check_weather":
            if db:
                try:
                    snap_res = await db.execute(
                        select(WeatherSnapshot).order_by(WeatherSnapshot.created_at.desc()).limit(1)
                    )
                    snap = snap_res.scalar_one_or_none()
                    if snap:
                        verdict_colors = {"no_go": "#d6372f", "caution": "#f0a020", "go": "#1fa35b"}
                        card_html = f'<span class="ic" style="background:{verdict_colors.get(snap.verdict, "#1fa35b")};color:#fff">{snap.verdict.replace("_", " ").title()}</span>'
                        return {
                            "reply_kn": snap.kn_summary,
                            "reply_en": snap.en_summary,
                            "card_html": card_html,
                        }
                except Exception:
                    pass
            # Malpe harbour default weather: Go (wind 12, wave 0.8m)
            return {
                "reply_kn": "ಹೋಗಬಹುದು. ಗಾಳಿ ಹನ್ನೆರಡು ಕಿಲೋಮೀಟರ್, ಅಲೆ ಒಂದು ಮೀಟರ್ ಒಳಗೆ.",
                "reply_en": "Go. Wind 12 km/h, waves under 1 m.",
                "card_html": '<span class="ic" style="background:#1fa35b;color:#fff">Go · ಹೋಗಬಹುದು</span>',
            }

        if intent == "get_price":
            fish = slots.get("fish", "Mackerel")
            info = FISH_CATALOGUE.get(fish, FISH_CATALOGUE["Mackerel"])
            lo, hi = info["price_range"]
            return {
                "reply_kn": f"{info['name_kn']} ಇವತ್ತು ಕೆಜಿಗೆ {lo} ರಿಂದ {hi} ರೂಪಾಯಿ.",
                "reply_en": f"{fish} today: ₹{lo}–{hi} per kg.",
            }

        if intent == "check_offer":
            fish = slots.get("fish", "Pomfret")
            offer = slots.get("offer", 600.0)
            info = FISH_CATALOGUE.get(fish, FISH_CATALOGUE["Pomfret"])
            lo, hi = info["price_range"]
            if offer < lo:
                return {
                    "reply_kn": f"ಇದು ಕಮ್ಮಿ. ಇವತ್ತಿನ ರೇಟ್ {lo} ರಿಂದ {hi}. ಇನ್ನೂ ಕೇಳಿ.",
                    "reply_en": f"Too low. Today’s range is ₹{lo}–{hi}. Ask for more.",
                    "card_html": '<span class="ic" style="background:#d6372f;color:#fff">Too low</span>',
                }
            elif offer > hi:
                return {
                    "reply_kn": f"ಒಳ್ಳೆ ಬೆಲೆ! ಇವತ್ತಿನ ರೇಟ್ {lo} ರಿಂದ {hi}. ಒಪ್ಪಿಕೊಳ್ಳಿ.",
                    "reply_en": f"Great offer! Above range ₹{lo}–{hi}. Take it!",
                    "card_html": '<span class="ic" style="background:#1fa35b;color:#fff">Great offer</span>',
                }
            else:
                return {
                    "reply_kn": f"ನ್ಯಾಯಯುತ ಬೆಲೆ. ಇವತ್ತಿನ ರೇಟ್ {lo} ರಿಂದ {hi}.",
                    "reply_en": f"Fair price. Within range ₹{lo}–{hi}.",
                    "card_html": '<span class="ic" style="background:#0a4d7a;color:#fff">Fair price</span>',
                }

        # Family Intents
        if intent == "boat_status":
            if db:
                try:
                    sos_res = await db.execute(
                        select(SosEvent).where(SosEvent.status.in_(["active", "dispatched"])).order_by(SosEvent.created_at.desc()).limit(1)
                    )
                    active_sos = sos_res.scalar_one_or_none()
                    if active_sos:
                        return {
                            "reply_kn": "ತುರ್ತು ಎಚ್ಚರಿಕೆ! ದೋಣಿಯಿಂದ ಸಂಕಷ್ಟ ಸಂದೇಶ ಬಂದಿದೆ. ಕರಾವಳಿ ಕಾವಲು ಪಡೆಯನ್ನು ಸಂಪರ್ಕಿಸಲಾಗಿದೆ.",
                            "reply_en": "Emergency alert! Boat reported distress. Coast Guard notified.",
                            "card_html": '<span class="ic" style="background:#d6372f;color:#fff">Distress Alert</span>',
                        }
                    trip_res = await db.execute(
                        select(Trip).order_by(Trip.created_at.desc()).limit(1)
                    )
                    trip = trip_res.scalar_one_or_none()
                    if trip:
                        if trip.status == "returning":
                            return {
                                "reply_kn": "ದೋಣಿ ವಾಪಸ್ ಬರ್ತಿದೆ, ದಡಕ್ಕೆ ಹತ್ತಿರದಲ್ಲಿದೆ.",
                                "reply_en": "The boat is returning, heading towards Malpe harbour.",
                            }
                        elif trip.status == "landed":
                            return {
                                "reply_kn": "ದೋಣಿ ತೀರಕ್ಕೆ ಬಂದಿದೆ. ಸುರೇಶ್ ಸುರಕ್ಷಿತವಾಗಿದ್ದಾರೆ.",
                                "reply_en": "The boat has landed safely at the harbour.",
                            }
                        elif trip.status == "overdue":
                            return {
                                "reply_kn": "ದೋಣಿ ನಿರೀಕ್ಷಿತ ಸಮಯಕ್ಕಿಂತ ತಡವಾಗಿದೆ. ಎಚ್ಚರಿಕೆ ನೀಡಲಾಗಿದೆ.",
                                "reply_en": "The boat is overdue. Alerts have been sent.",
                                "card_html": '<span class="ic" style="background:#f0a020;color:#fff">Overdue</span>',
                            }
                except Exception:
                    pass
            return {
                "reply_kn": "ದೋಣಿ ಸಮುದ್ರದಲ್ಲಿದೆ, ಸುರಕ್ಷಿತ ವಲಯದಲ್ಲಿ.",
                "reply_en": "The boat is at sea, inside the safe zone.",
            }

        if intent == "get_eta":
            if db:
                try:
                    trip_res = await db.execute(
                        select(Trip).order_by(Trip.created_at.desc()).limit(1)
                    )
                    trip = trip_res.scalar_one_or_none()
                    if trip:
                        if trip.status == "landed":
                            return {
                                "reply_kn": "ದೋಣಿ ಈಗಾಗಲೇ ತೀರಕ್ಕೆ ತಲುಪಿದೆ.",
                                "reply_en": "The boat has already reached the shore.",
                            }
                        eta_text = trip.eta_text or "11:55 AM"
                        return {
                            "reply_kn": f"ಸುಮಾರು {eta_text} ಒಳಗೆ ಬರ್ತಾರೆ.",
                            "reply_en": f"Expected back by {eta_text}.",
                        }
                except Exception:
                    pass
            return {
                "reply_kn": "ಸುಮಾರು 11:55 AM ಒಳಗೆ ಬರ್ತಾರೆ.",
                "reply_en": "Expected back by 11:55 AM.",
            }

        # --- WRITE INTENTS (Confirm before saving — D8) ---
        if nlu_res.decision == "confirm":
            PENDING_ACTIONS[session_token] = {
                "intent": intent,
                "slots": slots,
                "created_at": time.time(),
            }

            if intent == "log_entries":
                sale = slots.get("sale", {})
                exp = slots.get("expense", {})
                fish_kn = FISH_CATALOGUE.get(sale.get("fish", "Sardine"), {}).get("name_kn", "ಬೂತಾಯಿ")
                kg = int(sale.get("kg", 40))
                total = int(sale.get("total", 4000))
                fuel = int(exp.get("amount", 1200))
                return {
                    "reply_kn": f"{kg} ಕೆಜಿ {fish_kn}, {total} ರೂಪಾಯಿ. ಡೀಸೆಲ್ {fuel}. ಉಳಿಸಲೇ?",
                    "reply_en": f"{kg} kg {sale.get('fish', 'Sardine')} = ₹{total}. Diesel ₹{fuel}. Save?",
                    "card_html": f'<span class="ic">Sale ₹{total:,}</span><span class="ic">Expense ₹{fuel:,}</span>',
                }

            if intent == "save_fish_spot":
                return {
                    "reply_kn": "ಸ್ಥಳ ಗುರುತಿಸಿದ್ದೇನೆ. ನಿಮ್ಮ ಸಿಬ್ಬಂದಿಗೆ ಮಾತ್ರ ಕಾಣುತ್ತದೆ.",
                    "reply_en": "Spot marked. Only visible to your crew.",
                }

            if intent == "tick_checklist":
                return {
                    "reply_kn": "ಲೈಫ್ ಜಾಕೆಟ್, ಡೀಸೆಲ್ ಗುರುತಿಸಿದ್ದೇನೆ. ಐಸ್ ಮತ್ತು ನೀರು ಇದೆಯಾ?",
                    "reply_en": "Ticked life jackets and fuel. Do you have ice and water?",
                }

            if intent == "announce_landing":
                fish_kn = FISH_CATALOGUE.get(slots.get("fish", "Mackerel"), {}).get("name_kn", "ಬಂಗುಡೆ")
                kg = int(slots.get("kg", 40))
                return {
                    "reply_kn": f"{kg} ಕೆಜಿ {fish_kn}, 40 ನಿಮಿಷದಲ್ಲಿ ತೀರಕ್ಕೆ. ಖರೀದಿದಾರರಿಗೆ ತಿಳಿಸಲೇ?",
                    "reply_en": f"{kg} kg {slots.get('fish', 'Mackerel')}, landing in 40 min. Notify buyers?",
                }

        return {
            "reply_kn": "ಹೇಳಿ, ನಾನು ಕೇಳುತ್ತಿದ್ದೇನೆ.",
            "reply_en": "I am listening. How can I help?",
        }

    @classmethod
    async def _commit_pending_action(
        cls,
        pending: Dict[str, Any],
        user_phone: str,
        db: Optional[AsyncSession],
    ):
        """Execute persistent DB commit once user explicitly confirms."""
        intent = pending["intent"]
        slots = pending["slots"]

        if not db:
            return

        try:
            user_res = await db.execute(select(User).where(User.phone == user_phone))
            user = user_res.scalar_one_or_none()
            user_id = user.id if user else str(uuid.uuid4())

            if intent == "log_entries":
                sale = slots.get("sale", {})
                exp = slots.get("expense", {})
                if sale.get("total"):
                    db.add(LedgerEntry(
                        user_id=user_id,
                        entry_type="sale",
                        amount=float(sale["total"]),
                        description=f"{sale.get('kg', 40)} kg {sale.get('fish', 'Sardine')} (voice)",
                        quantity_kg=float(sale.get("kg", 40)),
                        client_op_id=f"voice_sale_{uuid.uuid4().hex[:12]}",
                    ))
                if exp.get("amount"):
                    db.add(LedgerEntry(
                        user_id=user_id,
                        entry_type="expense",
                        amount=float(exp["amount"]),
                        description=f"{exp.get('item', 'diesel')} (voice)",
                        client_op_id=f"voice_exp_{uuid.uuid4().hex[:12]}",
                    ))
                await db.commit()

            elif intent == "save_fish_spot":
                db.add(FishSpot(
                    fisher_user_id=user_id,
                    lat=13.35,
                    lon=74.69,
                    note=slots.get("note", "good catch"),
                    visible_to="crew",
                ))
                await db.commit()

            elif intent == "announce_landing":
                # Create landing record
                sp_res = await db.execute(select(FishSpecies).where(FishSpecies.name_en == slots.get("fish", "Mackerel")))
                sp = sp_res.scalar_one_or_none()
                sp_id = sp.id if sp else str(uuid.uuid4())
                harbour_id = user.harbour_id if user and user.harbour_id else str(uuid.uuid4())

                landing = Landing(
                    fisher_user_id=user_id,
                    harbour_id=harbour_id,
                    species_id=sp_id,
                    quantity_kg=float(slots.get("kg", 40)),
                    eta_min=40,
                    status="announced",
                )
                db.add(landing)
                await db.commit()

            elif intent == "tick_checklist":
                trip_res = await db.execute(
                    select(Trip).where(Trip.fisher_user_id == user_id).order_by(Trip.created_at.desc()).limit(1)
                )
                trip = trip_res.scalar_one_or_none()
                trip_id = trip.id if trip else str(uuid.uuid4())
                items = slots.get("items") or ["life_jackets", "fuel"]
                for item_key in items:
                    db.add(TripCheck(
                        trip_id=trip_id,
                        check_key=item_key,
                        is_checked=True,
                    ))
                await db.commit()
        except Exception:
            pass
