# SPEC_DIGEST.md — Ale Voice Condensed Specification
> Quick-reference for all models. Consult `graphify query` for connections.

## 1. HARBOURS & GEOGRAPHY
| Harbour | Lat | Lon | Code |
|---|---|---|---|
| Malpe | 13.3496 | 74.7039 | MALPE |
| Mangaluru | 12.8654 | 74.8426 | MANG |
| Gangolli | 13.6235 | 74.6498 | GANG |
| Honnavar | 14.2816 | 74.4444 | HONN |

## 2. DEMO PERSONAS (Seed Data)
| Name | Phone | Role | OTP | Details |
|---|---|---|---|---|
| Suresh Poojary | 9876500021 | fisher | 4821 | Boat Ale-Malpe-07, Malpe |
| Lakshmi | 9876500012 | family | 4821 | Wife of Suresh |
| Rafiq | 9876500031 | buyer | 4821 | Fish Mart Udupi, Malpe |
| Insp. Naik | 9876500041 | guard | 4821 | Malpe Coast Guard, CG-0412 |

## 3. FISH SPECIES & ALIASES
| English | Kannada | Emoji | Price Range (₹/kg) | Aliases |
|---|---|---|---|---|
| Sardine | ಬೂತಾಯಿ | 🐟 | 90–110 | boothaayi, butai, mathi |
| Mackerel | ಬಂಗುಡೆ | 🐠 | 140–170 | bangude, ayala |
| Pomfret | ಮಾಂಜಿ | 🐡 | 620–760 | maanji, paplet |
| Prawns | ಸಿಗಡಿ | 🦐 | 380–450 | sigadi, shrimp, jhinga |

## 4. FISHER INTENTS (7)
| Intent | Type | Conf≥ | Slots | Screen |
|---|---|---|---|---|
| `check_weather` | read | 0.80 | — | #s0 Dawn |
| `get_price` | read | 0.80 | fish | #s2 Prices |
| `check_offer` | read | 0.80 | fish, offer | #s2 Prices |
| `log_entries` | **write** | confirm | sale{fish,kg,price}, expense{item,amt} | #s4 Diary |
| `save_fish_spot` | **write** | confirm | species, note, gps | #s1 Sea |
| `tick_checklist` | **write** | confirm | items[] | #s8 Trip |
| `announce_landing` | **write** | confirm | fish, kg, eta_min | #s5 Landing |

## 5. FAMILY INTENTS (3) + CONTROL
| Intent | Type | Slots |
|---|---|---|
| `boat_status` | read | — |
| `check_weather` | read | — |
| `get_eta` | read | — |
| `outbound_alert` | system | trigger(overdue/sos) |

## 6. CONTROL INTENTS
| Intent | Rule |
|---|---|
| `confirm_yes` | ಹೌದು / yes / haan — commits pending_action |
| `confirm_no` | ಇಲ್ಲ / no / beda — cancels pending_action |
| `repair_select` | picks from disambiguation options |
| `sos` | 2-second hold ONLY, never voice-triggered |

## 7. CONFIDENCE FORMULA (D7, D8, D9)
```
confidence = 0.6 * intent_score + 0.3 * slot_score + 0.1 * stt_hint
```
- Read intents: act at ≥ 0.80; repair if top-2 within 0.1 or conf < 0.60
- Write intents: ALWAYS return `decision="confirm"` with `pending_action` (20s expiry)
- SOS: physical 2s hold only; voice NEVER triggers SOS or deletes data

## 8. VOICE PIPELINE STAGES
```
Mic(16kHz mono) → Gnani STT(Prisma v3) → Normalise → NLU(intent+slots)
→ Action(DB/API) → Template(Kannada) → Gnani TTS(Timbre v3) → Speaker
```
Timing fields: `stt_ms`, `nlu_ms`, `action_ms`, `tts_ms`, `total_ms`

## 9. GNANI API SPECS
### STT
- `POST https://api.vachana.ai/stt/v3`
- Header: `X-API-Key-ID: <key>`
- Form: `audio_file`(WAV 16kHz), `model=prisma-v3.0`, `language_code=kn-IN,en-IN`, `preferred_language=kn-IN`, `format=codemix`, `keyterms=ಬೂತಾಯಿ,ಬಂಗುಡೆ,ಮಾಂಜಿ,ಸಿಗಡಿ,...`

### TTS
- `POST https://api.vachana.ai/api/v1/tts/inference`
- Header: `X-API-Key-ID: <key>`
- JSON: `{text, voice:"Lakshmi", model:"timbre-v3.0", language:"kn-IN", audio_config:{encoding:"linear_pcm", container:"wav", sample_rate:24000, num_channels:1, sample_width:2}}`
- Cache key: `SHA-256(text + voice + model + format)`

### Concurrency Lock
- Gnani enforces 1 active request per API key (429 RATE_LIMITED)
- Global `asyncio.Semaphore(1)` with 1 retry + jitter

## 10. WEATHER SOURCES
- Marine: `https://marine-api.open-meteo.com/v1/marine?latitude=13.3496&longitude=74.7039&current=wave_height,swell_wave_period`
- Forecast: `https://api.open-meteo.com/v1/forecast?latitude=13.3496&longitude=74.7039&current=wind_speed_10m,wind_gusts_10m`
- Verdicts: Go(green) / Be careful(amber) / Don't go(red)

## 11. KANNADA REPLY TEMPLATES
| Intent | Kannada Template |
|---|---|
| check_weather(go) | ಹೋಗಬಹುದು. ಗಾಳಿ {wind} ಕಿಲೋಮೀಟರ್, ಅಲೆ {wave} ಮೀಟರ್ ಒಳಗೆ. |
| check_weather(caution) | ಜಾಗರೂಕರಾಗಿರಿ. ಗಾಳಿ {wind}, ಅಲೆ {wave} ಮೀಟರ್ ಹತ್ತಿರ. |
| check_weather(no_go) | ಹೋಗಬೇಡಿ. ಗಾಳಿ {wind}, ಅಲೆ {wave} ಮೀಟರ್. |
| get_price | {fish_kn} ಇವತ್ತು ಕೆಜಿಗೆ {lo} ರಿಂದ {hi} ರೂಪಾಯಿ. |
| check_offer(low) | ಇದು ಕಮ್ಮಿ. ಇವತ್ತಿನ ರೇಟ್ {lo} ರಿಂದ {hi}. ಇನ್ನೂ ಕೇಳಿ. |
| check_offer(fair) | ನ್ಯಾಯಯುತ ಬೆಲೆ. |
| check_offer(great) | ಒಳ್ಳೆ ಬೆಲೆ! ಒಪ್ಪಿಕೊಳ್ಳಿ. |
| log_entries(confirm) | {kg} ಕೆಜಿ {fish_kn}, {total} ರೂಪಾಯಿ. {expense} ಖರ್ಚು. ಉಳಿಸಲೇ? |
| save_fish_spot | ಸ್ಥಳ ಗುರುತಿಸಿದ್ದೇನೆ. ನಿಮ್ಮ ಸಿಬ್ಬಂದಿಗೆ ಮಾತ್ರ ಕಾಣುತ್ತದೆ. |
| tick_checklist | {items} ಗುರುತಿಸಿದ್ದೇನೆ. {remaining}? |
| announce_landing(confirm) | {kg} ಕೆಜಿ {fish_kn}, {eta} ನಿಮಿಷದಲ್ಲಿ ತೀರಕ್ಕೆ. ಖರೀದಿದಾರರಿಗೆ ತಿಳಿಸಲೇ? |
| boat_status | ದೋಣಿ {status_kn}. |
| get_eta | ಸುಮಾರು {eta} ಒಳಗೆ ಬರ್ತಾರೆ. |
| confirm_yes | (saved/done template) |
| confirm_no | ಸರಿ, ಮಾಡಿಲ್ಲ. |
| repair | {option1}ನಾ ಅಥವಾ {option2}ನಾ? |

## 12. KANNADA NUMBER WORDS (Normaliser)
| Word | Value | | Word | Value |
|---|---|---|---|---|
| ಒಂದು | 1 | | ಹತ್ತು | 10 |
| ಎರಡು | 2 | | ಇಪ್ಪತ್ತು | 20 |
| ಮೂರು | 3 | | ಮೂವತ್ತು | 30 |
| ನಾಲ್ಕು | 4 | | ನಲವತ್ತು | 40 |
| ಐದು | 5 | | ಐವತ್ತು | 50 |
| ಆರು | 6 | | ಅರವತ್ತು | 60 |
| ಏಳು | 7 | | ಎಪ್ಪತ್ತು | 70 |
| ಎಂಟು | 8 | | ಎಂಬತ್ತು | 80 |
| ಒಂಬತ್ತು | 9 | | ತೊಂಬತ್ತು | 90 |
| ನೂರು | 100 | | ಸಾವಿರ | 1000 |

Compounds: ಸಾವಿರದ ಇನ್ನೂರು = 1200, ನಾಲ್ಕು ಸಾವಿರ = 4000

## 13. SCREEN IDS (from v4 prototype)
| ID | Screen | Role | Tab |
|---|---|---|---|
| #s0 | Dawn (weather verdict) | fisher | 🌅 |
| #s1 | Sea (map, SOS, spots) | fisher | 🧭 |
| #s2 | Prices (fair price board) | fisher/buyer | 🐟 |
| #s3 | Family view (boat status) | family | 👩 |
| #s4 | Diary (earnings) | fisher/family | 📒 |
| #s5 | Landing alert | fisher | ⚓ |
| #s6 | Incoming boats (buyer) | buyer | 🛒 |
| #s7 | Coast Guard watch | guard | 🛟 |
| #s8 | Trip check-in | fisher | 📋 |
| #s9 | Profile/Settings | all | 👤 |
| #auth | Sign-in + Onboarding | all | — |
| #vs | Voice Sheet (VOX) | fisher/family | 🎙 |

## 14. API ENDPOINTS (Protected Core)
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/auth/send-otp` | Send demo OTP |
| POST | `/api/v1/auth/verify-otp` | Verify & issue session |
| POST | `/api/v1/voice/turn` | Main voice pipeline |
| POST | `/api/v1/voice/confirm` | Confirm pending write |
| POST | `/api/v1/voice/repair` | Disambiguation selection |
| GET | `/api/v1/weather/dawn` | Dawn weather verdict |
| POST | `/api/v1/trips/start` | Start trip with checklist |
| POST | `/api/v1/trips/{id}/end` | End trip |
| POST | `/api/v1/sos` | SOS (idempotent) |
| GET | `/api/v1/prices` | Current fish prices |
| POST | `/api/v1/landings` | Announce landing |
| POST | `/api/v1/landings/{id}/bids` | Place bid |
| GET | `/api/v1/diary` | Ledger entries |
| POST | `/api/v1/diary` | Add ledger entry |
| GET | `/api/v1/family/status` | Boat status for family |
| GET | `/api/v1/guard/watch` | Coast guard overview |
| POST | `/api/v1/guard/broadcast` | Storm broadcast |
| POST | `/api/v1/sync/outbox` | Offline outbox sync |
| GET | `/health` | Health check |

## 15. PROTECTED CORE DB TABLES (Key subset)
`harbours`, `users`, `fisher_profiles`, `boats`, `fish_species`, `fish_aliases`,
`market_prices`, `weather_rules`, `weather_snapshots`, `trips`, `trip_checks`,
`fish_spots`, `landings`, `bids`, `ledger_entries`, `sos_events`, `incident_events`,
`alerts`, `voice_sessions`, `voice_turns`, `tts_cache`, `outbox_ops`, `audit_log`

## 16. DESIGN TOKENS (from v4 prototype)
```css
--page: #e9eef3  --ink: #0b2540  --sub: #54708a  --card: #fff
--bg: #f4f8fb  --sea: #0a4d7a  --sun: #ff8a2b  --line: #dbe6ee
--st: #1fa35b (Go green)  Warn: #f0a020  Danger: #d6372f
Font: Segoe UI / Noto Sans Kannada, 14-38px
```

## 17. DECISIONS LOG (D1-D16 Summary)
- **D1:** PWA + FastAPI + SQLAlchemy + PostgreSQL/SQLite fallback
- **D7:** Confidence formula: 0.6×intent + 0.3×slot + 0.1×stt_hint
- **D8:** Write intents ALWAYS confirm before DB commit
- **D9:** SOS = physical 2s hold only, never voice
- **D10:** Gnani Semaphore(1) for rate limiting
- **D11:** tts_cache by SHA-256 hash
- **D12:** Offline outbox with client_op_id idempotency
- **D13:** Open-Meteo for weather, seeded fallback
- **D14:** Kannada-first templates with English fallback
- **D15:** Fish lexicon with fuzzy matching
- **D16:** Mock providers toggle for development

