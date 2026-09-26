# Cross-Border Pollution Alert — Delhi-NCR Corridor

### 🔗 Live prototype: https://pollution-alert-362757633662.asia-south1.run.app

**Hackathon:** Code for Communities 2 (Hack2skill) · **Track 2:** Clean Air and Climate Resilience

Delhi-NCR's worst air-quality spikes are not only a Delhi problem: smoke from
fires in Punjab, Haryana and beyond drifts across state lines into the NCR,
where it lands on cities governed by three different state governments. This
prototype connects the **upwind cause** (live NASA satellite fire detections)
with the **downwind effect** (air quality in six NCR cities across Delhi,
Haryana and Uttar Pradesh), and uses **Gemini** to turn the combined picture
into a prioritized, plain-language advisory that tells officials which city is
most at risk and which cross-state action to take.

### What makes this different

- **Cross-border by design.** Existing dashboards show one city's AQI. This
  links pollution sources in one state to their impact in another, and
  recommends action to the authorities on *both* sides of the border.
- **AI that reasons, not decorates.** Gemini weighs AQI across cities against
  satellite fire activity and produces a specific, prioritized recommendation
  — not a generic summary.
- **Honest under uncertainty.** Every number on screen is labelled live or
  sample, Gemini is instructed to caveat its advice when inputs are estimates,
  and it never states unverified causes (e.g. "these are farm fires") or
  unmeasured weather as fact. The system is designed to fail gracefully and
  transparently rather than fabricate.
- **One pipeline, any corridor in India.** The same code serves any
  upwind/downwind region by changing a city list and a map bounding box —
  see [How this scales across India](#how-this-scales-across-india).

---

## Contents

1. [The problem](#the-problem)
2. [How this maps to the problem statement](#how-this-maps-to-the-problem-statement)
3. [What an official sees and does](#what-an-official-sees-and-does)
4. [How this scales across India](#how-this-scales-across-india)
5. [Architecture](#architecture)
6. [What's live vs. sample data](#whats-live-vs-sample-data)
7. [Tech stack and why](#tech-stack-and-why)
8. [Key technical decisions and lessons learned](#key-technical-decisions-and-lessons-learned)
9. [Run it locally](#run-it-locally)
10. [Deploy to Google Cloud Run](#deploy-to-google-cloud-run)
11. [Project files](#project-files)
12. [Roadmap](#roadmap)

---

## The problem

Every October–November, Delhi-NCR's air quality collapses into the "Very
Poor" and "Severe" bands. A major contributor is crop-residue (stubble)
burning in Punjab and Haryana, whose smoke is carried south-east into the NCR
by prevailing winds. The NCR itself spans Delhi, Haryana and Uttar Pradesh.

This creates a coordination gap:

- **The source and the impact are in different states.** Fires in one state
  harm residents of another, but each state monitors and acts within its own
  borders.
- **City monitoring is reactive.** CPCB stations report what the air is like
  *now*, in *one place*. They don't show where the pollution is coming from
  or which neighbouring city is next.
- **The data exists but isn't joined up.** Satellite fire detections (NASA
  FIRMS) and ground AQI (CPCB) are both public, but nobody combines them into
  a single, actionable view for decision-makers.

## How this maps to the problem statement

> *Track 2 challenge: Build an AI-powered, federated climate action platform
> that combines citizen-sourced data with satellite imagery and
> meteorological data, detects hidden pollution hotspots, forecasts air
> quality spikes across major economic corridors, and alerts relevant
> authorities — designed for interoperability so Indian cities and states can
> share models and coordinate resources.*

| Problem statement asks for | What this prototype does | Status |
|---|---|---|
| AI-powered platform | Gemini reasons over combined AQI + fire data to prioritize risk and recommend a cross-state action | ✅ Built |
| Satellite data | NASA FIRMS VIIRS near-real-time fire detections, refreshed every 10 minutes | ✅ Built |
| Detect pollution hotspots | Fire detections mapped across Punjab, Haryana, NCR and northern Rajasthan | ✅ Built (detection); source attribution is future work |
| Economic corridors / interoperability across states | Covers 3 states in one corridor; region is configuration, not code | ✅ Built |
| Alert relevant authorities | Advisory names the state/district authorities who should act | ⚠️ Recommendation only — automated alert delivery is on the roadmap |
| Meteorological data & spike forecasting | Not yet; the advisory explicitly defers to IMD wind forecasts rather than guessing | 🔜 Roadmap |
| Citizen-sourced data (photos, sensors) | Not yet; planned as Gemini multimodal photo classification | 🔜 Roadmap |

We prioritized a working, honest end-to-end flow over a wider set of
half-built features. The roadmap items plug into the same pipeline as extra
inputs to the Gemini step.

## What an official sees and does

Opening the live URL shows a single screen:

- **Map (left).** Six NCR cities as coloured circles (green → red by AQI
  band, sized by severity), and red dots for every satellite fire detection
  in the last 24 hours. Clicking a city shows its AQI and whether that value
  is live or sample data.
- **AI advisory (top right).** A Gemini-generated advisory in three parts:
  1. a one-line headline risk assessment,
  2. the city at highest near-term risk and why,
  3. one concrete cross-state coordination action (e.g. which state's
     authorities should ground-verify fire detections, which city should
     issue health advisories).
- **City list (right).** AQI per city with its state, colour-coded, with a
  **SAMPLE** tag on any value that is not a live reading.
- **Status bar (top).** How many cities and fire detections are shown, and
  whether each data source is live or sample.

**How it's used:** a state disaster-management or pollution-control official
opens the page, reads the advisory to see where risk is concentrated and who
needs to act, checks the map to see where the fire activity is, and uses the
recommendation to coordinate with counterparts in neighbouring states. It is
a decision-support view: it recommends actions, and people take them.

## How this scales across India

The pipeline has no Delhi-specific logic. A deployment is defined by two
pieces of configuration at the top of [`app.py`](app.py):

```python
# 1. The downwind cities to monitor (any city with CPCB stations)
CITIES = [
    {"name": "Delhi",    "state": "Delhi",   "lat": 28.6139, "lon": 77.2090},
    {"name": "Gurugram", "state": "Haryana", "lat": 28.4595, "lon": 77.0266},
    ...
]

# 2. The upwind source region to watch for fires (west,south,east,north)
BURNING_BELT_BBOX = "73.5,27.5,78.5,32.5"
```

Everything else — fetching AQI, fetching fires, the Gemini reasoning, the
map — works unchanged for any region, because:

- **CPCB** runs continuous monitoring stations in cities across every major
  state, all published through the same data.gov.in API.
- **NASA FIRMS** covers the entire globe with the same API, so any bounding
  box in India works.
- **Gemini** receives city names, states and data sources as input, so its
  advisory names the right states and authorities for whichever corridor is
  configured.

**Examples of corridors the same pipeline could serve:**

| Upwind source region | Downwind cities | Cross-border relationship |
|---|---|---|
| Punjab / Haryana crop-burning belt | Delhi-NCR (this deployment) | Punjab + Haryana → Delhi, Haryana, UP |
| Singrauli–Sonbhadra coal and thermal-power cluster | Singrauli (Madhya Pradesh) and Sonbhadra (Uttar Pradesh) towns | A documented industrial pollution hotspot straddling the MP–UP border |
| Any region with recurring fire activity | Cities downwind of it | Any upwind/downwind state pair |

For fire-driven corridors, the pipeline works as-is. Industrial clusters like
Singrauli–Sonbhadra emit mostly through smokestacks rather than open fires,
which FIRMS largely doesn't capture, so they would swap the upwind data
source for satellite emissions data (e.g. Sentinel-5P NO₂/SO₂). The CPCB,
Gemini and map layers stay the same.

**Deployment cost per region is minimal:** each corridor is one Cloud Run
service, which scales to zero when idle and runs within the free tier at
pilot scale. A state could pilot its own corridor in days: pick cities, draw
a bounding box, deploy.

**Next step for national scale:** move the city list and bounding box from
code into a config file (or a database), so one deployment can serve many
corridors and states can add their own without code changes.

## Architecture

### Data flow

```
   ┌──────────────────────────┐        ┌──────────────────────────────┐
   │ CPCB via data.gov.in     │        │ NASA FIRMS (VIIRS NRT)        │
   │ Ground-station AQI for   │        │ Satellite fire detections,    │
   │ 6 NCR cities, 3 states   │        │ last 24h, upwind region       │
   └────────────┬─────────────┘        └───────────────┬──────────────┘
                │  fetch_cpcb_aqi()                     │  fetch_firms_fires()
                │  (10-min cache, sample fallback)      │  (10-min cache, sample fallback)
                ▼                                       ▼
        ┌─────────────────────────────────────────────────────────┐
        │  Flask backend (app.py) on Google Cloud Run             │
        │  Labels every value as LIVE or SAMPLE                   │
        └──────────────┬──────────────────────────┬───────────────┘
                       │                          │
                       ▼                          │
        ┌─────────────────────────────┐           │
        │ Gemini (google-genai SDK)   │           │
        │ gemini-flash-latest         │           │
        │  └ retry → backup model     │           │
        │ Prompt includes data labels │           │
        │ + honesty rules             │           │
        └──────────────┬──────────────┘           │
                       │ advisory (10-min cache)  │ AQI + fires
                       ▼                          ▼
        ┌─────────────────────────────────────────────────────────┐
        │  Browser: Leaflet map + advisory sidebar                │
        │  (templates/index.html)                                 │
        └─────────────────────────────────────────────────────────┘
```

### API endpoints

| Endpoint | Returns |
|---|---|
| `GET /` | The dashboard page |
| `GET /api/aqi` | Per-city AQI, with `source` = `cpcb_live` or `sample_fallback` |
| `GET /api/fires` | Fire detection count and points, with `source` = `nasa_firms_live` or `sample_fallback` |
| `GET /api/advisory` | The advisory text, which model produced it (or `fallback_reason` if Gemini wasn't used), timestamp and counts |
| `GET /api/health` | Which data sources and which Gemini model are configured |

All external API calls happen server-side, so API keys never reach the
browser.

## What's live vs. sample data

| Source | Status | Detail |
|---|---|---|
| **NASA FIRMS** fire detections | ✅ **Live** | Real VIIRS detections from the last 24 hours, refreshed every 10 minutes. Zero detections is shown as zero, not replaced with sample data — expected outside the Oct–Nov burning season. |
| **Gemini** advisory | ✅ **Live** | Generated from the current data on each refresh. |
| **CPCB** city AQI | ⚠️ **Sample data** | data.gov.in's API key registration was not working during the build period, so AQI currently uses realistic sample values. The live CPCB integration is implemented and turns on automatically once `DATA_GOV_IN_KEY` is set — no code change needed. |

**How the system handles this — by design:**

- **Every value is labelled.** The UI shows a **SAMPLE** tag next to any AQI
  value that isn't a live reading, and the status bar says which sources are
  live.
- **Gemini is told what's real.** Each input in the prompt is marked
  `[LIVE ...]` or `[SAMPLE/ESTIMATED ...]`. When any input is sample data,
  Gemini must open with a caveat and phrase risk conditionally ("if current
  levels are near these estimates…") rather than as fact.
- **No over-claiming.** Satellite heat detections can be crop burning,
  industrial sites or flares, so Gemini is instructed to say they "likely
  include agricultural burning, though source attribution isn't confirmed".
  The prototype has no wind data, so Gemini may not state wind direction or
  smoke arrival times, and refers officials to IMD forecasts instead.
- **Failures are visible.** If a data source fails, the app keeps running on
  labelled sample data. If Gemini fails, the sidebar changes to "Advisory
  (template — Gemini not used)" with the reason shown.

For a tool whose output could inform public-health decisions, a system that
says "I'm not sure" is more valuable than one that is confidently wrong.

## Tech stack and why

### Technologies

| Technology | Role | Why we chose it |
|---|---|---|
| **Python + Flask** | Backend web server and JSON API | Lightweight and quick to build with; a small API needs nothing heavier. |
| **Leaflet.js** (+ CARTO dark basemap) | Interactive map | Open source, free, no API key or billing needed, and handles hundreds of markers smoothly. |
| **google-genai SDK** | Calls the Gemini API | Google's current official Python SDK for Gemini (replaces the deprecated `google-generativeai`). |
| **Gemini** (`gemini-flash-latest`, backup `gemini-flash-lite-latest`) | Advisory generation | Fast, low-cost reasoning over structured data. The `-latest` aliases track Google's current models, so the app doesn't break when a model version is retired. |
| **requests** | HTTP calls to CPCB and FIRMS | Simple, reliable, standard. |
| **python-dotenv** | Loads API keys from `.env` locally | Keeps keys out of source code. |
| **gunicorn** | Production web server in the container | Flask's built-in server is for development only; gunicorn is the standard production server. |
| **Docker** | Packages the app | One reproducible build that runs the same locally and in the cloud. |
| **Google Cloud Run** | Hosting | Serverless: scales to zero when idle and up automatically under load, pay-per-use with a generous free tier, deploys straight from source, and has an Indian region (`asia-south1`, Mumbai). |

### Data sources

| Source | What it provides | Why it matters here |
|---|---|---|
| **CPCB via data.gov.in** | Station-level readings from CPCB's continuous ambient air quality monitoring network | The official Government of India ground truth for air quality — the *downwind effect*. |
| **NASA FIRMS** (VIIRS S-NPP, near real-time) | Locations of active fires / thermal anomalies detected by satellite, within hours of the satellite pass | Shows *upwind causes* across state borders, where no ground monitoring exists. Free, global and open. |
| **Google Gemini API** | Language-model reasoning | Turns two separate datasets into a single prioritized judgement and recommended action that an official can read in seconds. |

## Key technical decisions and lessons learned

**1. Fail transparently, never silently.**
The first version fell back to sample data or a template advisory without
telling anyone, so the app could look fully live while showing nothing real.
Every fallback now carries a `source` label that is shown in the UI, and
`/api/advisory` includes a `fallback_reason`.

**2. Gemini reliability: retry, then fall back to a second model.**
During testing Gemini's main model returned `503 — model experiencing high
demand` several times. The app now retries once after a short pause, then
switches to `gemini-flash-lite-latest`, which has separate capacity. On the
first cloud deployment, this backup is what produced the advisory.
Non-temporary errors (e.g. an invalid key) fail immediately rather than
retrying.

**3. Use model aliases, not pinned versions.**
The prototype originally used `gemini-2.0-flash`, which has since been
retired and no longer appears in the API's model list. Using the
`gemini-flash-latest` alias (configurable via `GEMINI_MODEL`) avoids the demo
breaking when Google retires a version.

**4. Caching for rate limits and speed.**
AQI, fire data and successful Gemini advisories are cached for 10 minutes.
Upstream data doesn't change faster than that, the free tiers of all three
APIs have rate limits, and the first Gemini call takes 10–20 seconds — after
that, the page loads instantly. Failed results are deliberately *not*
cached, so the next request retries. The container runs a single process
with multiple threads so all requests share one cache.

**5. Prompting for honesty, not just output.**
Early advisories stated sample AQI as a "CRITICAL ALERT", called every
satellite detection a "farm fire", and asserted wind directions that came
from our own prompt. The prompt now labels each input's source and sets
explicit rules against stating unverified causes or unmeasured conditions
as fact. It also asks for plain text, since the UI displays it directly.

**6. Zero is a valid answer.**
Outside the burning season FIRMS can legitimately return no fires. The
original parser treated an empty result as a failure and showed 180 sample
fires. It now distinguishes "no fires detected" (shown as 0, live) from "the
API returned an error" (sample fallback, labelled).

**7. A real bug from an unverified endpoint.**
The FIRMS API URL originally pointed to a hostname that doesn't exist, so
live fire data could never have loaded. Lesson: test every external
integration against the real service, not only the fallback path.

**8. AQI must be the maximum sub-index, not an average — identified, pending
live data.**
Under CPCB's National AQI method, a location's AQI is the *highest*
sub-index among its pollutants (PM2.5, PM10, NO₂, SO₂, CO, O₃, NH₃, Pb), so
the worst pollutant determines the health category. The current code
averages all readings for a city, which would understate AQI whenever one
pollutant dominates — typically PM2.5 during smog episodes. The fix depends
on confirming whether the data.gov.in feed reports concentrations or
sub-indices, which requires live API access. It will be corrected once CPCB
data is connected; until then, AQI shown is sample data and is labelled as
such.

**9. Keeping secrets out of the build.**
`gcloud run deploy --source .` uploads the whole folder. `.gcloudignore` and
`.dockerignore` exclude `.env`, key files and the local virtual environment,
and keys are passed to Cloud Run as environment variables from a file
outside the project.

## Run it locally

Requires Python 3.9+ (3.11 recommended).

```bash
git clone <this-repo-url>
cd pollution
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
# add your API keys to .env (see below) — optional
python app.py
```

Open http://localhost:8080. **No keys are required to try it** — every data
source falls back to clearly labelled sample data.

### API keys (all free)

| Variable | Where to get it | Without it |
|---|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com → "Get API key" | Template advisory, clearly marked |
| `FIRMS_MAP_KEY` | https://firms.modaps.eosdis.nasa.gov/api/map_key/ (sent by email) | Sample fire data, labelled |
| `DATA_GOV_IN_KEY` | https://data.gov.in → register → API key in your profile | Sample AQI, labelled |

Optional: `GEMINI_MODEL` and `GEMINI_BACKUP_MODEL` override the default
models.

## Deploy to Google Cloud Run

1. Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
   and log in:
   ```bash
   gcloud auth login
   ```
2. Choose a Google Cloud project with **billing enabled** (required by Cloud
   Run; pilot-scale traffic fits in the free tier).
   *Tip:* if your Gemini key was created in AI Studio, deploy to a
   *different* project — enabling billing on the key's own project moves the
   key to Gemini's paid tier.
3. On newer projects, allow the default compute service account to run
   source builds (otherwise the build fails with `PERMISSION_DENIED`):
   ```bash
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
     --role="roles/run.builder"
   ```
4. Put your keys in a YAML file **outside the project folder**, e.g.
   `~/env.yaml`:
   ```yaml
   GEMINI_API_KEY: "your_key"
   FIRMS_MAP_KEY: "your_key"
   DATA_GOV_IN_KEY: "your_key"
   ```
5. Deploy from the project folder:
   ```bash
   gcloud run deploy pollution-alert \
     --source . \
     --project PROJECT_ID \
     --region asia-south1 \
     --allow-unauthenticated \
     --env-vars-file ~/env.yaml
   ```
   The first build takes about 3–5 minutes; gcloud prints the service URL
   when done.

## Project files

| File | What it does |
|---|---|
| [`app.py`](app.py) | The Flask backend. Defines the monitored cities and fire region, fetches and caches CPCB AQI and NASA FIRMS data (with labelled sample fallbacks), builds the Gemini prompt and calls Gemini with retry and backup-model logic, and serves the JSON API and the page. |
| [`templates/index.html`](templates/index.html) | The whole frontend in one file: a Leaflet map of cities and fire detections, the advisory sidebar and city list, and the live/sample labels. Plain HTML, CSS and JavaScript — no build step. |
| [`requirements.txt`](requirements.txt) | Pinned Python dependencies (Flask, requests, python-dotenv, google-genai, gunicorn), so local and cloud builds install identical versions. |
| [`Dockerfile`](Dockerfile) | Builds the container Cloud Run runs: Python 3.11, the dependencies, and gunicorn listening on Cloud Run's `$PORT` with a 90-second timeout for slow upstream calls. |
| [`.env.example`](.env.example) | Template listing every environment variable the app reads, with links to get each key. Copy it to `.env` for local runs. |
| [`.gcloudignore`](.gcloudignore) | Files excluded when uploading source to Cloud Build — keeps API keys and the local virtual environment out of the cloud. |
| [`.dockerignore`](.dockerignore) | The same exclusions for the container image itself. |
| [`.gitignore`](.gitignore) | Keeps keys, the virtual environment and logs out of version control. |

## Roadmap

- **Correct AQI calculation** — maximum sub-index per CPCB's National AQI
  method, once live CPCB data is connected (see decision 8).
- **Meteorological data** — wind forecasts (e.g. IMD or Open-Meteo) so the
  system knows which fires are actually upwind of each city and can
  **forecast spikes** instead of only reporting current levels.
- **Citizen reports** — residents upload photos; Gemini's multimodal model
  classifies them (crop burning, garbage fire, industrial smoke, dust) and
  places them on the map as hyper-local hotspots satellites can miss.
- **Automated alerts** — send the advisory to the relevant state pollution
  control board or district authority (email/SMS) when risk crosses a
  threshold.
- **Multi-corridor configuration** — load cities and regions from a config
  file so one deployment serves many corridors and states.
- **Multilingual advisories** — Hindi, Punjabi and other regional languages
  for district-level officials and the public.
