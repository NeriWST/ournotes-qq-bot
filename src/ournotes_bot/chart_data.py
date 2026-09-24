"""Fetch the public release score JSON referenced by MasterLiveMusicScore."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

from .data import Chart


CHART_BASE = "https://storage.bdon.moe/moenotes/Live/MusicScore"
CHART_CACHE_TTL = 6 * 3600
MAX_CHART_BYTES = 2_000_000


class ChartDataError(RuntimeError):
    pass


def chart_url(chart: Chart) -> str:
    if not re.fullmatch(r"[0-9]{4}/[0-9]{4}_[0-9]{2}", chart.chart_file):
        raise ChartDataError("Invalid score asset name")
    name = chart.chart_file.rsplit("/", 1)[1]
    return f"{CHART_BASE}/{chart.chart_file}/{name}.json"


def _parse_score(raw: bytes) -> dict:
    if len(raw) > MAX_CHART_BYTES:
        raise ChartDataError("Score asset is too large")
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("score"), dict):
            raise ValueError("Unexpected score schema")
        score = payload["score"]
        notes = score["notes"]
        meta = payload.get("meta")
        if not isinstance(meta, dict) or meta.get("version") != 100 or not isinstance(notes, list) or not notes:
            raise ValueError("Unexpected score schema")
        if len(notes) > 20_000 or not isinstance(score.get("events"), dict):
            raise ValueError("Unexpected score size or events")
        return score
    except (TypeError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise ChartDataError("Unrecognized score asset") from exc


def load_chart_score(chart: Chart, cache_dir: Path | None = None) -> dict:
    """Return validated score data; use a stale cache if the network is unavailable."""
    url = chart_url(chart)
    cache = cache_dir or Path(__file__).resolve().parents[2] / "data" / "chart-cache"
    name = chart.chart_file.replace("/", "_") + ".json"
    path = cache / name
    cached: dict | None = None
    if path.exists():
        try:
            cached = _parse_score(path.read_bytes())
            if time.time() - path.stat().st_mtime < CHART_CACHE_TTL:
                return cached
        except (OSError, ChartDataError):
            cached = None
    try:
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=12) as response:
            raw = response.read(MAX_CHART_BYTES + 1)
        score = _parse_score(raw)
        try:
            cache.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
            try:
                temporary.write_bytes(raw)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        except OSError:
            # A read-only cache must not hide a chart that was fetched successfully.
            pass
        return score
    except (OSError, ValueError, ChartDataError) as exc:
        if cached is not None:
            return cached
        raise ChartDataError(f"Score asset unavailable: {chart.chart_file}") from exc
