# ALE VOICE — BUILD STATUS & GRAPHIFY HANDOFF TRACKER
**Last Updated:** 2026-11-08T12:57:00+05:30
**Current Milestone:** Milestone 5 — Pytest Verification Suite & Quality Gates G1–G4 (COMPLETED)
**Active Work Package:** All Core Work Packages WP-0.5 through WP-7.1 (COMPLETED)
**Graphify State:** `graphify-out/graph.json` (FRESH — All M0–M5 complete, 431 nodes, 860 edges, 20 communities)

## 1. IMMEDIATE HANDOFF BRIEF (READ FIRST)
- **Status:** Complete production-grade vertical slice implemented, seeded, tested, and verified end-to-end.
- **Relevant Graphify Nodes to Query:** `VoiceOrchestrator`, `NluEngine`, `FishLexicon`, `GnaniStt`, `GnaniTts`, `SosEvent`, `LedgerEntry`, `OutboxOp`
- **Useful Graphify Command for Next Turn:** `graphify query "How does VoiceOrchestrator coordinate STT, NLU, Action, and TTS stages?"`
- **What Works End-to-End Right Now:**
  1. Full Voice Pipeline: MediaRecorder / Phrase chips -> Kannada/English Normaliser -> Fish Lexicon -> NLU (7+3 intents with D7 confidence formula) -> Action -> Kannada Template -> Gnani TTS -> Speaker + Live Stage Timings Inspector.
  2. Safety Rules: Zero unconfirmed voice writes (D8), physical 2-second hold SOS (D9), Gnani Semaphore(1) rate-limit guard (D10), SHA-256 audio cache (D11).
  3. REST APIs: Auth (OTP 4821), Dawn Weather (Open-Meteo with fallback), Trips, SOS, Prices, Landings & Bids, Diary, Family Status, Coast Guard Watch/Broadcast, and Outbox Sync.
  4. PWA Frontend: `apps/web/index.html` mounted directly onto FastAPI at `http://localhost:8000`.
  5. Automated Verification: Quality Gates G1, G2, G3, G4 all 100% passing (`tests/run_quality_gates.py`).
- **How to Run Local Dev Server:**
  `uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload`
- **Environment State:** `MOCK_PROVIDERS=true` (set to `false` with `GNANI_API_KEY_ID` for live Gnani), DB=SQLite (`ale_voice.db`) with automatic Postgres fallback.

## 2. MILESTONE CHECKLIST
- [x] **M0:** Graphify init (`graphify-out/`), `SPEC_DIGEST.md`, `STATUS.md`, repo scaffolding (`WP-0.5`, `WP-0.6`)
- [x] **M1:** Database schema & Malpe seed data (`WP-1.1`, `WP-1.6`) + `graphify . --update`
- [x] **M2:** Normaliser, Fish Lexicon, 7 Intents, Dialogue Manager, Gnani/Mock STT+TTS (`WP-2.1` to `WP-2.6`) + `graphify . --update`
- [x] **M3:** Core REST APIs + Open-Meteo Dawn + Confirm Writes + SOS & Trips (`WP-1.7`, `WP-2.7`, `WP-3.1` to `WP-4.7`) + `graphify . --update`
- [x] **M4:** PWA (`v4.html` wired to live API + `MediaRecorder` mic + Inspector timings + Offline Outbox) (`WP-2.2`, `WP-2.8`, `WP-6.1` to `WP-6.6`) + `graphify . --update`
- [x] **M5:** Pytest suite & Quality Gates G1–G4 (`WP-3.7`, `WP-7.1`)

## 3. KEY MODULE & GRAPH SYMBOL MAP
| File Path | Key AST Symbols / Nodes | Linked Requirements (`# WHY:`) | Status |
|---|---|---|---|
| `apps/api/models/schema.py` | 23 Protected Core tables | `D1, D4, D8, D11, D12, TR-DATA-01` | COMPLETED |
| `apps/api/core/seed.py` | `seed_database()` | `D3, FR-AUTH-01, FR-GEO-01` | COMPLETED |
| `apps/api/services/normaliser.py` | `normalise_kannada_text`, `parse_kannada_number_words` | `TR-NLU-03, D14` | COMPLETED |
| `apps/api/services/lexicon.py` | `FishLexicon`, `match_fish` | `TR-NLU-02, D15` | COMPLETED |
| `apps/api/services/nlu.py` | `NluEngine`, `calculate_confidence` | `TR-NLU-01, D7, D8, D9` | COMPLETED |
| `apps/api/providers/gnani.py` | `GnaniStt`, `GnaniTts`, `MockStt`, `MockTts` | `TR-VOX-05, TR-VOX-06, D10, D11` | COMPLETED |
| `apps/api/services/orchestrator.py`| `VoiceOrchestrator` | `TR-VOX-01, TR-VOX-07, G1, G2` | COMPLETED |
| `apps/api/routers/voice.py` | `/turn, /confirm, /repair` | `TR-VOX-08, FR-VOX-01` | COMPLETED |
| `apps/api/routers/auth.py` | `/auth/send-otp, /auth/verify-otp` | `FR-AUTH-01, TR-AUTH-01` | COMPLETED |
| `apps/api/routers/weather.py` | `/weather/dawn` | `FR-WTH-01, FR-WTH-02, D13` | COMPLETED |
| `apps/api/routers/trips.py` | `/trips/start, /trips/{id}/end, /sos` | `FR-TRP-01, FR-SOS-01, D9, G3` | COMPLETED |
| `apps/api/routers/market.py` | `/prices, /offer-check, /landings, /bids`| `FR-PRC-01, FR-LND-01, FR-BID-01`| COMPLETED |
| `apps/api/routers/diary.py` | `/diary/summary, /diary/entries` | `FR-DIR-01, FR-VOX-04, G4` | COMPLETED |
| `apps/api/routers/family.py` | `/family/status` | `FR-FAM-01, TR-FAM-01` | COMPLETED |
| `apps/api/routers/guard.py` | `/guard/watch, /guard/broadcast` | `FR-CG-01, TR-CG-01` | COMPLETED |
| `apps/api/routers/sync.py` | `/sync/outbox` | `TR-SYNC-01, D12, G4` | COMPLETED |
| `apps/web/index.html` | UI prototype (10 screens, VOX sheet) | `TR-PWA-01, FR-PWA-01` | COMPLETED |
| `apps/web/app.js` | MediaRecorder mic, API client, Inspector | `TR-VOX-05, TR-VOX-06, G1, G2` | COMPLETED |
| `tests/run_quality_gates.py` | Automated G1–G4 test verification | `G1, G2, G3, G4, TR-TEST-01` | COMPLETED |

## 4. PROTECTED CORE QUALITY GATES (ALL PASSED)
- [x] **G1:** Read-only Kannada intents (`check_weather`, `get_price`, `check_offer`) + stage latency measured
- [x] **G2:** Zero unconfirmed voice writes (`log_entries`, `save_fish_spot`, `tick_checklist`, `announce_landing`)
- [x] **G3:** Multi-role safety flow (Trip Start -> Overdue/SOS -> Family Alert -> Coast Guard Dispatch -> Resolved)
- [x] **G4:** Offline outbox (`client_op_id`) syncs with zero duplicates
