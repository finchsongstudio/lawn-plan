# KC Lawn Care App — Project Roadmap

## What This Is

A notification app that monitors soil temperatures and weather conditions for a Kansas City (Zone 6a) Kentucky Bluegrass lawn, then sends push alerts when it's time to apply products. Built around a structured JSON schedule of 24 seasonal applications spanning March–December.

## Background Context

The application schedule is a hybrid of two programs:
- **The Andersons Elite Calendar** — granular fertilizer, pre-emergent (Barricade), post-emergent (Surge), insecticide (GrubOut), and soil amendments (Humic DG, BioChar DG)
- **GCI Turf Academy** — liquid biostimulant monthly cadence (Air8, RGS, Humic12, Cal-Tide, Microgreene) and fungicide rotation (Azoxystrobin + Propiconazole on 25-day intervals, May–August)

All timing has been adapted from generic cool-season guides to KC-specific soil temps, heat patterns, and transition zone considerations. The canonical data lives in `kc-lawn-care-plan-2026.json`.

There is also a `kc-lawn-care-plan-2026.docx` — a human-readable narrative version of the same plan with KC-specific notes, temperature restrictions, and a product quick reference. The docx is for printing/reference; the JSON is the app's data source.

## Core Data Model

### Trigger Types (from JSON)
| Type | Description | Example |
|------|-------------|---------|
| `soil_temp` | Soil temp at depth hits threshold for N consecutive days | Pre-emergent: 55°F at 4", rising, 2 days |
| `soil_temp_falling` | Soil temp dropping through threshold | Fall overseed: 70°F at 4", falling |
| `days_after` | Calendar days after a referenced application fires | Fungicide 2: 23–25 days after Fungicide 1 |
| `calendar_window` | Fixed date range with optional conditions | July iron push: July 1–15 |
| `same_as` | Bundle with another application | March fertilizer fires with March pre-emergent |

### Dependency Chain
Applications reference each other by `id`. The schedule forms a DAG:
- `round1_preemergent` (soil temp trigger) → `round1_fertilizer` + `bio1_soil_amendment` (same_as)
- `round1_fertilizer` → `round2_fertilizer` (30–45 days after)
- `bio1_soil_amendment` → `bio2_rooting` (25–35 days after) → `bio3_calcium` → `bio4_humic` → `bio5_humic` → `bio6_fall_rooting` → `bio7_fall_calcium`
- `fungicide1` (soil temp trigger) → `fungicide2` → `fungicide3` → `fungicide4` (each 23–25 days)
- `fall_renovation` (soil temp falling trigger) blocks `fall_preemergent`

### Condition Guards
Each application can have conditions that gate execution:
- Air temperature min/max (e.g., Propiconazole hard cap at 85°F, Surge 60–85°F)
- `skip_if_extended_heat_dome` — suppress nitrogen in 95°F+ sustained heat
- `skip_if` / `blocked_by` — overseed/pre-emergent mutual exclusion
- `reduce_rate_if_air_temp_above_f` — auto-suggest lower rate in heat

## Features — Prioritized

### Phase 1: Core Notification Engine
- [ ] Ingest `kc-lawn-care-plan-2026.json` as the schedule source
- [ ] Soil temperature data feed (source TBD — see Data Sources below)
- [ ] Walk the trigger dependency chain and compute projected application dates
- [ ] Send push notification N days before projected application date (`alert_days_before` field)
- [ ] Mark applications as "done" with actual date — this shifts all downstream `days_after` triggers
- [ ] Basic UI: timeline view of upcoming and completed applications

### Phase 2: Weather-Aware Guards
- [ ] Pull air temperature forecast (7-day minimum)
- [ ] Flag condition conflicts: "Surge is due but forecast shows 88°F Thursday"
- [ ] Suggest reschedule windows: "Next day under 85°F is Monday"
- [ ] Heat dome detection: suppress nitrogen apps, suggest iron-only alternative
- [ ] Propiconazole auto-suppress above 85°F, surface Azoxy-only fallback

### Phase 3: Product & Rate Management
- [ ] Set `area_sqft` once → auto-calculate total product quantities for every application
- [ ] Shopping list generator: aggregate all products needed for a date range
- [ ] Track product inventory (bought X bags, used Y per app, Z remaining)
- [ ] Spreader setting lookup (if data available per product)

### Phase 4: Intelligence Layer
- [ ] Curative protocol cards: surface brown patch / grub / grey leaf spot playbooks when user reports symptoms
- [ ] Seasonal nitrogen budget tracker: running total of lbs N/1,000 applied vs. 3.5–4.5 target
- [ ] Historical log: what was applied when, actual vs. planned dates, conditions at time of application
- [ ] Year-over-year comparison (2026 → 2027)

### Phase 5: Nice-to-Haves
- [ ] Back yard EcoGrass simple schedule (water reminders, dormancy timing)
- [ ] Birdhouse camera integration alerts (just kidding... unless?)
- [ ] Photo journal: snap lawn condition at each application for visual tracking
- [ ] Export season summary

## Data Sources to Evaluate

### Soil Temperature
| Source | Notes |
|--------|-------|
| **Yard Mastery app API** | Drew already plans to use this. Check if it has an API or just push notifications. If no API, may need to scrape or use as manual input. |
| **Greencast (Syngenta)** | Historical soil temp averages for KC. Web-based, likely no public API. Good for baseline projections. |
| **NOAA / NWS soil temp stations** | Government data, likely available via API. May not be hyperlocal. |
| **Personal sensor (Raspberry Pi)** | Optional future enhancement. A soil temp probe could report to the Windows app via local network or file share. |

### Weather / Air Temperature
| Source | Notes |
|--------|-------|
| **OpenWeatherMap API** | Free tier, 7-day forecast, good enough for condition guards |
| **NWS API (api.weather.gov)** | Free, no key needed, KC-specific forecast |
| **Weather Underground** | Personal weather station network, hyperlocal |

## Technical Decisions (Open)

1. **Platform**: ~~Mobile app / PWA / Raspberry Pi~~ → **Windows scheduled task + Pushover/Ntfy**
2. **Backend**: Does this need a server, or can it run entirely on-device with a local JSON schedule + weather API calls?
3. **Soil temp input**: Automated sensor vs. manual entry vs. third-party API pull?
4. **Notification service**: Native push (requires app store) vs. Pushover/Ntfy (works from any backend) vs. SMS (Twilio)?
5. **State management**: Where does "I completed this application on DATE" live? Local storage? Simple database?
6. **Multi-year**: Is the JSON regenerated each year with updated dates, or does the app handle year-to-year rollover?

## Constraints

- Drew describes his coding proficiency as "understanding but not speaking" — has built Python and JS projects with Claude's help (markdown-to-print converter, D&D Beyond web scraper, Final Surge data extraction)
- No commercial intent — this is a personal tool
- Should be low-maintenance once running; runs via Windows Task Scheduler on local machine
- KC-specific: no need to generalize for other zones/locations (unless it's trivial to do so)

## Files

| File | Description |
|------|-------------|
| `kc-lawn-care-plan-2026.json` | Canonical structured schedule — 24 applications, trigger logic, condition guards, product catalog, curative protocols |
| `kc-lawn-care-plan-2026.docx` | Human-readable narrative version with KC-specific notes, temperature restrictions, product quick reference |
| `roadmap.md` | This file |

## Getting Started

The simplest useful v0 might be:
1. A script that reads the JSON
2. Pulls current soil temp from an API or manual input
3. Walks the dependency chain to compute "next 3 upcoming applications"
4. Sends a notification via Pushover or Ntfy
5. Runs daily via Windows Task Scheduler

That gives immediate value with minimal infrastructure, and everything else layers on top.
