"""
Cross-Border Pollution Alert System
=====================================
Tracks how pollution (esp. from agricultural burning in Punjab/Haryana)
drifts across state lines and compounds air quality in NCR cities.

Data sources (all free/public):
  - CPCB live station data via data.gov.in
  - NASA FIRMS satellite active-fire detection
  - Gemini API for cross-city advisory generation

Run locally:
  export DATA_GOV_IN_KEY=...
  export FIRMS_MAP_KEY=...
  export GEMINI_API_KEY=...
  python app.py
"""

import os
import re
import time
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_GOV_IN_KEY = os.environ.get("DATA_GOV_IN_KEY", "")
FIRMS_MAP_KEY = os.environ.get("FIRMS_MAP_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# "gemini-flash-latest" is Google's alias for the current Flash model, so the
# app keeps working when older model versions are retired. Override to pin one.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
# Tried if the primary model is overloaded (503) or rate-limited (429).
GEMINI_BACKUP_MODEL = os.environ.get("GEMINI_BACKUP_MODEL", "gemini-flash-lite-latest")

# CPCB "Real Time Air Quality Index" resource on data.gov.in
CPCB_RESOURCE_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
CPCB_URL = f"https://api.data.gov.in/resource/{CPCB_RESOURCE_ID}"

# NASA FIRMS active fire API (VIIRS, near real-time)
FIRMS_URL_TEMPLATE = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{bbox}/{days}"
)

# The cross-border corridor we track: Delhi-NCR cities + the Punjab/Haryana
# burning belt whose smoke plumes drift southeast into NCR during Oct-Nov.
CITIES = [
    {"name": "Delhi", "state": "Delhi", "lat": 28.6139, "lon": 77.2090},
    {"name": "Gurugram", "state": "Haryana", "lat": 28.4595, "lon": 77.0266},
    {"name": "Noida", "state": "Uttar Pradesh", "lat": 28.5355, "lon": 77.3910},
    {"name": "Faridabad", "state": "Haryana", "lat": 28.4089, "lon": 77.3178},
    {"name": "Ghaziabad", "state": "Uttar Pradesh", "lat": 28.6692, "lon": 77.4538},
    {"name": "Meerut", "state": "Uttar Pradesh", "lat": 28.9845, "lon": 77.7064},
]

# Bounding box covering Punjab + Haryana burning belt + NCR
# format for FIRMS: west,south,east,north
BURNING_BELT_BBOX = "73.5,27.5,78.5,32.5"

_cache = {"aqi": None, "aqi_ts": 0, "fires": None, "fires_ts": 0,
          "advisory": None, "advisory_ts": 0}
CACHE_TTL = 600  # 10 minutes — respects rate limits, keeps demo responsive


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------

def fetch_cpcb_aqi():
    """Fetch live station-level AQI from CPCB via data.gov.in.
    Falls back to realistic sample data if no key is configured yet,
    so the prototype is demoable before credentials are wired in."""
    now = time.time()
    if _cache["aqi"] and now - _cache["aqi_ts"] < CACHE_TTL:
        return _cache["aqi"]

    if not DATA_GOV_IN_KEY:
        return _sample_aqi()

    try:
        results = []
        for city in CITIES:
            params = {
                "api-key": DATA_GOV_IN_KEY,
                "format": "json",
                "filters[city]": city["name"],
                "limit": 20,
            }
            resp = requests.get(CPCB_URL, params=params, timeout=10)
            resp.raise_for_status()
            records = resp.json().get("records", [])
            if not records:
                results.append(_sample_city_aqi(city))
                continue

            values = []
            for r in records:
                try:
                    values.append(float(r.get("avg_value", 0)))
                except (TypeError, ValueError):
                    continue
            avg_aqi = round(sum(values) / len(values)) if values else None

            results.append({
                **city,
                "aqi": avg_aqi if avg_aqi is not None else _sample_city_aqi(city)["aqi"],
                "station_count": len(records),
                "source": "cpcb_live",
            })

        _cache["aqi"] = results
        _cache["aqi_ts"] = now
        return results
    except Exception as e:
        app.logger.warning(f"CPCB fetch failed, using sample data: {e}")
        return _sample_aqi()


def fetch_firms_fires():
    """Fetch active fire detections in the Punjab/Haryana burning belt
    from NASA FIRMS. Falls back to sample data without a key."""
    now = time.time()
    if _cache["fires"] and now - _cache["fires_ts"] < CACHE_TTL:
        return _cache["fires"]

    if not FIRMS_MAP_KEY:
        return _sample_fires()

    try:
        url = FIRMS_URL_TEMPLATE.format(
            key=FIRMS_MAP_KEY, bbox=BURNING_BELT_BBOX, days=1
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        lines = resp.text.strip().split("\n")
        header = lines[0].split(",")
        if "latitude" not in header:
            # Not a CSV of detections — FIRMS can return plain-text error
            # messages instead of CSV. A header-only CSV means zero fires,
            # which is valid and shouldn't fall back to sample data.
            raise ValueError(f"Unexpected FIRMS response: {resp.text[:200]}")

        lat_idx = header.index("latitude")
        lon_idx = header.index("longitude")
        conf_idx = header.index("confidence") if "confidence" in header else None

        fires = []
        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) <= max(lat_idx, lon_idx):
                continue
            fires.append({
                "lat": float(parts[lat_idx]),
                "lon": float(parts[lon_idx]),
                "confidence": parts[conf_idx] if conf_idx is not None else "n/a",
            })

        result = {"count": len(fires), "points": fires[:500], "source": "nasa_firms_live"}
        _cache["fires"] = result
        _cache["fires_ts"] = now
        return result
    except Exception as e:
        app.logger.warning(f"FIRMS fetch failed, using sample data: {e}")
        return _sample_fires()


def _sample_city_aqi(city):
    """Deterministic-but-varied sample AQI so the demo looks realistic
    before live keys are configured."""
    base = {"Delhi": 312, "Gurugram": 268, "Noida": 295, "Faridabad": 274,
            "Ghaziabad": 341, "Meerut": 288}
    return {**city, "aqi": base.get(city["name"], 280), "station_count": 4,
            "source": "sample_fallback"}


def _sample_aqi():
    return [_sample_city_aqi(c) for c in CITIES]


def _sample_fires():
    # Representative cluster pattern for Punjab/Haryana burning season
    import random
    random.seed(42)
    points = []
    for _ in range(180):
        points.append({
            "lat": 30.5 + random.uniform(-1.2, 1.2),
            "lon": 75.5 + random.uniform(-1.5, 1.5),
            "confidence": random.choice(["high", "nominal", "high"]),
        })
    return {"count": len(points), "points": points, "source": "sample_fallback"}


# ---------------------------------------------------------------------------
# Gemini-powered advisory
# ---------------------------------------------------------------------------

def generate_advisory(aqi_data, fire_data):
    """Ask Gemini to reason over the combined cross-city AQI + fire data
    and produce a prioritized, plain-language advisory for officials."""
    if not GEMINI_API_KEY:
        return _fallback_advisory(aqi_data, fire_data, "GEMINI_API_KEY not set")

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)

        city_summary = "\n".join(
            f"- {c['name']} ({c['state']}): AQI {c['aqi']} "
            + ("[LIVE CPCB reading]" if c["source"] == "cpcb_live"
               else "[SAMPLE/ESTIMATED value, NOT a live reading]")
            for c in aqi_data
        )
        any_sample_aqi = any(c["source"] != "cpcb_live" for c in aqi_data)
        fires_live = fire_data["source"] == "nasa_firms_live"
        fire_line = (
            f"{fire_data['count']} thermal-anomaly detections in the last 24h "
            + ("[LIVE NASA FIRMS VIIRS data]" if fires_live
               else "[SAMPLE data, NOT live detections]")
        )

        caveat_rule = (
            "- Some or all AQI values are SAMPLE/ESTIMATED, not live. Begin the "
            "advisory with a line stating it is based partly on sample data. Do "
            "not state risk levels for sample-data cities as current fact; phrase "
            "them conditionally (e.g. 'if current levels are near these "
            "estimates...').\n"
            if any_sample_aqi or not fires_live else ""
        )

        prompt = f"""You are an air-quality advisory system for Indian disaster
management officials coordinating across Delhi-NCR states. Write a SHORT
prioritized advisory (max 130 words) from the data below.

City AQI values:
{city_summary}

Satellite fire detections in a box covering Punjab, Haryana, Delhi-NCR and
northern Rajasthan (upwind of NCR): {fire_line}

Rules for honesty — follow strictly:
{caveat_rule}- The fire detections are satellite thermal anomalies. Their source is NOT
  confirmed: they may include agricultural/stubble burning, but also
  industrial sites, flares or other heat sources. Do not call them farm
  fires as fact; say e.g. "likely includes agricultural burning, though
  source attribution isn't confirmed".
- You have NO wind or weather data. Do not state wind direction, plume
  movement or arrival times as fact. If you mention transport, say it
  depends on wind conditions, which should be verified with IMD forecasts.
- Do not invent numbers that are not in the data above.

Structure your response as:
1. One-line headline risk assessment
2. Which specific city is at highest near-term risk and why
3. One concrete cross-state coordination action (e.g. which state/district
   should verify and act on fire detections, which city should issue
   health advisories)

Be specific and actionable, not generic. Output PLAIN TEXT only: no
Markdown, no asterisks, no # headings. Use "1.", "2.", "3." for the
sections."""

        text, model_used = _generate_with_backup(client, prompt)
        return {"text": _strip_markdown(text), "source": "gemini_live",
                "model": model_used}
    except Exception as e:
        app.logger.warning(f"Gemini call failed, using fallback: {e}")
        return _fallback_advisory(aqi_data, fire_data, f"Gemini call failed: {e}")


def _generate_with_backup(client, prompt):
    """Call the primary model; on overload/rate-limit, retry once, then try
    the backup model. Other errors (e.g. invalid key) are raised at once."""
    from google.genai import errors

    attempts = [GEMINI_MODEL, GEMINI_MODEL, GEMINI_BACKUP_MODEL]
    for i, model in enumerate(attempts):
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            if not response.text:
                raise ValueError(f"{model} returned an empty response")
            return response.text, model
        except errors.APIError as e:
            if e.code not in (429, 503) or i == len(attempts) - 1:
                raise
            app.logger.warning(f"{model} unavailable ({e.code}), retrying")
            time.sleep(2)


def _strip_markdown(text):
    """Gemini is asked for plain text, but strip common Markdown anyway since
    the UI renders the advisory as plain text."""
    text = re.sub(r"\*\*|__", "", text)
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.M)
    text = re.sub(r"^(\s*)[*•]\s+", r"\1- ", text, flags=re.M)
    return text.strip()


def _fallback_advisory(aqi_data, fire_data, reason):
    worst = max(aqi_data, key=lambda c: c["aqi"])
    aqi_live = worst["source"] == "cpcb_live"
    fires_live = fire_data["source"] == "nasa_firms_live"
    return {
        "fallback_reason": reason[:300],
        "text": (
            f"HEADLINE: {fire_data['count']} satellite fire detections upwind "
            f"of NCR in the last 24h"
            f"{'' if fires_live else ' (sample data, not live)'} — likely "
            f"includes agricultural burning, though source attribution isn't "
            f"confirmed. Smoke transport into NCR depends on wind conditions; "
            f"verify with IMD forecasts.\n\n"
            f"HIGHEST RISK: {worst['name']} ({worst['state']}) has the highest "
            f"AQI in the tracked corridor ({worst['aqi']}"
            f"{'' if aqi_live else ', sample/estimated value'}).\n\n"
            f"RECOMMENDED ACTION: Share fire detections with Punjab and Haryana "
            f"pollution control boards for ground verification; prepare "
            f"outdoor-activity health advisories for {worst['name']} if "
            f"elevated levels are confirmed.\n\n"
            f"[Note: this is a template fallback, not a Gemini-generated "
            f"advisory — see fallback_reason in /api/advisory.]"
        ),
        "source": "template_fallback",
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/aqi")
def api_aqi():
    return jsonify(fetch_cpcb_aqi())


@app.route("/api/fires")
def api_fires():
    return jsonify(fetch_firms_fires())


@app.route("/api/advisory")
def api_advisory():
    # Cache successful Gemini advisories so repeated page loads don't burn
    # through Gemini free-tier rate limits. Fallbacks aren't cached, so the
    # next request retries Gemini.
    now = time.time()
    if _cache["advisory"] and now - _cache["advisory_ts"] < CACHE_TTL:
        return jsonify(_cache["advisory"])

    aqi_data = fetch_cpcb_aqi()
    fire_data = fetch_firms_fires()
    advisory = generate_advisory(aqi_data, fire_data)
    result = {
        "advisory": advisory,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "cities_tracked": len(aqi_data),
        "fires_detected": fire_data["count"],
    }
    if advisory["source"] == "gemini_live":
        _cache["advisory"] = result
        _cache["advisory_ts"] = now
    return jsonify(result)


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "data_gov_in_configured": bool(DATA_GOV_IN_KEY),
        "firms_configured": bool(FIRMS_MAP_KEY),
        "gemini_configured": bool(GEMINI_API_KEY),
        "gemini_model": GEMINI_MODEL,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
