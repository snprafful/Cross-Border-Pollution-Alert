# Cross-Border Pollution Alert

**Live demo:** https://pollution-alert-362757633662.asia-south1.run.app

Built for Hack2skill's Code for Communities 2 hackathon, Track 2: Clean Air
and Climate Resilience.

A web dashboard that combines city air-quality readings with satellite fire
detections from upwind regions, and uses Gemini to generate an advisory for
officials: which city is at highest risk and what cross-state action to take.

**Scope:** The current implementation monitors the **Delhi-NCR corridor**
(6 cities across Delhi, Haryana and Uttar Pradesh) as a working example. The
broader goal is a general model: given any city's AQI, estimate how that
pollution spreads to and affects surrounding cities, for any city pair in
India — see [Proposed dispersion model](#proposed-dispersion-model-not-yet-built)
(not yet built).

## The problem

Delhi-NCR's air quality is heavily affected by pollution from outside its
borders, especially crop-residue burning in Punjab and Haryana during
October–November. The NCR itself spans three states (Delhi, Haryana and Uttar
Pradesh). Each state monitors and acts on its own air quality, but the source
of the pollution and the people affected by it are often in different states,
and there's no single view connecting the two.

## What it does

- Fetches AQI for 6 NCR cities (Delhi, Gurugram, Noida, Faridabad, Ghaziabad,
  Meerut) from CPCB via data.gov.in
- Fetches satellite fire detections from the last 24 hours for Punjab,
  Haryana, Delhi-NCR and northern Rajasthan from NASA FIRMS
- Sends both to Gemini, which writes a short advisory: a headline risk
  assessment, the city at highest near-term risk, and a recommended
  cross-state action
- Shows it all on a map, with cities coloured by AQI band and fire detections
  as red dots, next to the advisory and a city list

## Live vs. sample data

| Source | Status |
|---|---|
| NASA FIRMS fire detections | Live |
| Gemini advisory | Live |
| CPCB city AQI | **Sample data.** data.gov.in API key registration wasn't working while the project was being built. The live integration is implemented and switches on automatically when `DATA_GOV_IN_KEY` is set. |

Sample values are marked with a **SAMPLE** tag in the UI, and Gemini is told
which inputs are sample data so it caveats its advisory accordingly. It's also
instructed not to state unconfirmed fire sources or wind conditions as fact.
If Gemini is unavailable, the advisory is clearly marked as a template.

## Architecture

```
CPCB (data.gov.in) ──┐
                     ├──> Flask backend ──> Gemini ──> advisory ──┐
NASA FIRMS ──────────┘        │                                   ├──> Browser (map + sidebar)
                              └─────────── AQI + fire data ───────┘
```

| Endpoint | Returns |
|---|---|
| `GET /` | Dashboard page |
| `GET /api/aqi` | AQI per city, with its data source |
| `GET /api/fires` | Fire detections, with their data source |
| `GET /api/advisory` | Gemini advisory for the current data |
| `GET /api/health` | Which data sources and Gemini model are configured |

Notes:

- All external API calls are made server-side, so API keys never reach the
  browser.
- Data and advisories are cached for 10 minutes to stay within API rate
  limits and keep the page fast.
- If Gemini's main model is overloaded, the app retries and then falls back
  to a lighter model (`gemini-flash-lite-latest`).

## How it scales

Nothing in the pipeline is specific to Delhi. A region is defined by two
settings at the top of `app.py`:

```python
CITIES = [...]                            # downwind cities to monitor
BURNING_BELT_BBOX = "73.5,27.5,78.5,32.5" # upwind area to watch (west,south,east,north)
```

CPCB publishes monitoring data for cities across India through the same API,
and NASA FIRMS covers the whole globe, so another corridor can be set up by
changing the city list and bounding box. Examples:

- **Punjab/Haryana → Delhi-NCR** (this deployment)
- **Singrauli–Sonbhadra**, the coal and thermal-power cluster on the Madhya
  Pradesh–Uttar Pradesh border. Industrial emissions like these come mostly
  from smokestacks rather than open fires, so this corridor would swap FIRMS
  for satellite emissions data (e.g. Sentinel-5P NO₂/SO₂); the rest of the
  pipeline stays the same.

Each corridor can run as its own Cloud Run service, which scales to zero when
idle.

## Tech stack

| Tool | Used for |
|---|---|
| Python + Flask | Backend and JSON API |
| Leaflet.js + Esri World Dark Gray tiles | Interactive map; no API key required, with an automatic OpenStreetMap fallback if Esri tiles fail |
| Google Gemini (`google-genai` SDK) | Advisory generation |
| gunicorn | Production web server |
| Docker + Google Cloud Run | Deployment (serverless, Mumbai region) |

**Data sources**

- **CPCB via data.gov.in** — official ground-station air-quality readings
- **NASA FIRMS (VIIRS, near real-time)** — satellite detection of active
  fires and heat sources
- **Google Gemini API** — reasoning over the combined data

## Run locally

Requires Python 3.9+.

```bash
git clone https://github.com/snprafful/Cross-Border-Pollution-Alert.git
cd Cross-Border-Pollution-Alert
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
python app.py
```

Open http://localhost:8080. The app runs without any keys, using sample data.

### API keys (all free)

| Variable | Get it from |
|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com |
| `FIRMS_MAP_KEY` | https://firms.modaps.eosdis.nasa.gov/api/map_key/ |
| `DATA_GOV_IN_KEY` | https://data.gov.in (register, then find the key in your profile) |

## Deploy to Cloud Run

1. Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install),
   run `gcloud auth login`, and pick a project with billing enabled.
2. On newer projects, give the default compute service account build
   permissions:
   ```bash
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
     --role="roles/run.builder"
   ```
3. Put your keys in a YAML file outside the project folder (e.g. `env.yaml`
   with `GEMINI_API_KEY: "..."` lines), then deploy:
   ```bash
   gcloud run deploy pollution-alert --source . --project PROJECT_ID \
     --region asia-south1 --allow-unauthenticated --env-vars-file env.yaml
   ```

## Project structure

```
app.py                 Flask backend: data fetching, caching, Gemini calls, API routes
templates/index.html   Frontend: map, advisory panel and city list
requirements.txt       Python dependencies
Dockerfile             Container setup for Cloud Run
.env.example           Template for API keys
```

## Known limitations and next steps

- City AQI is currently an average of all pollutant readings; it should use
  the CPCB method (highest pollutant sub-index). This will be fixed once live
  CPCB data is available to test against.
- No wind or weather data yet. Adding forecasts (IMD or Open-Meteo) would
  show which fires are actually upwind of each city and allow spike
  forecasting — see the proposed dispersion model below.
- Planned: citizen photo reports classified by Gemini, automated alerts to
  state pollution control boards, and advisories in regional languages.

### Proposed dispersion model (not yet built)

> **Status: proposal only.** Nothing in this section is implemented yet.

The current app shows AQI and fire data side by side. The next step is a
quantitative estimate of how much one city's pollution affects another. The
proposed approach is a simplified wind-weighted exponential decay model, a
computationally light stand-in for full Gaussian plume dispersion:

```
Impact(B | A) = AQI(A) × Alignment(A→B, wind) × Decay(distance(A, B))
```

**Alignment** — how directly city B lies downwind of city A:

```
Alignment(A→B, wind) = max(0, cos θ)^n
```

- θ = angle between the direction the wind is blowing *toward* and the
  compass bearing from A to B. Weather APIs report wind direction as where
  the wind comes *from* (a 315° north-westerly wind carries pollution toward
  135°), so the "toward" direction is the reported direction + 180°.
- n = sharpness exponent (e.g. n = 2). Cities roughly downwind get high
  weight, cities directly downwind get the maximum, and cities crosswind or
  upwind get zero.

**Decay** — how pollution thins out with distance:

```
Decay(d) = exp(−d / L)
```

- d = great-circle distance between A and B, via the haversine formula
  (computable from the latitude/longitude already in the codebase).
- L = characteristic decay length in km, to be calibrated against known real
  events — e.g. how far Punjab stubble-burning smoke has historically
  correlated with AQI spikes in Delhi, Haryana and western UP. A natural
  extension is to scale L with wind speed, since faster winds carry
  pollution further.

**Data needed** (all free, none integrated yet):

- Wind speed and direction: [Open-Meteo](https://open-meteo.com/) API (no
  key required)
- Distance and bearing between any two cities: haversine formula (pure math,
  no external dependency)

**Limitations:** This is a simplified proxy, **not** a full atmospheric
transport model. A rigorous Gaussian plume model would also need emission
rates and atmospheric stability class data, which can't be derived from AQI
or fire-detection data alone. This model is meant to give a directionally
correct, calibratable estimate of *relative* impact — good enough to rank
which neighbouring cities are most at risk from a given source — not a
certified air-quality forecast.
