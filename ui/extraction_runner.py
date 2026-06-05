"""
Bridge between Streamlit (synchronous) and the async backend scraper.

Pattern: threading.Thread + asyncio.new_event_loop() so the Playwright-based
scraper can run without blocking Streamlit's main thread. Progress is
communicated via queue.Queue objects that are polled on each Streamlit rerun.
"""

import asyncio
import json
import queue
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# Ensure the project root is importable from any working directory
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from filters.professional_filter import ProfessionalFilter
from filters.quality_scorer import QualityScorer
from scraper.browser_manager import BrowserManager
from scraper.doctoralia_scraper import DoctoraliaScraper

try:
    import portalocker as _pl
    _HAS_LOCK = True
except ImportError:
    _HAS_LOCK = False

_DATA_DIR = _ROOT / "data"
DB_PATH = _DATA_DIR / "leads_database.json"
HISTORY_PATH = _DATA_DIR / "searches_history.json"
SETTINGS_PATH = _DATA_DIR / "settings.json"
_MAX_LEADS = 10_000


class ExtractionRunner:
    """Manages async lead extraction and the JSON persistence layer."""

    def __init__(self) -> None:
        self._ensure_data_files()

    # ------------------------------------------------------------------ #
    # Bootstrap                                                            #
    # ------------------------------------------------------------------ #

    def _ensure_data_files(self) -> None:
        _DATA_DIR.mkdir(exist_ok=True)
        if not DB_PATH.exists():
            _write_json(DB_PATH, {"leads": [], "version": "1.0"})
        if not HISTORY_PATH.exists():
            _write_json(HISTORY_PATH, {"searches": []})
        if not SETTINGS_PATH.exists():
            _write_json(SETTINGS_PATH, _default_settings())

    # ------------------------------------------------------------------ #
    # Extraction API                                                       #
    # ------------------------------------------------------------------ #

    def run_extraction(
        self,
        especialidade: str,
        cidade: str,
        estado: str,
        max_paginas: int,
        min_score: int,
        progress_queue: queue.Queue,
        result_queue: queue.Queue,
        stop_event: threading.Event,
        headless: bool = True,
    ) -> threading.Thread:
        """
        Start extraction in a daemon thread with a fresh asyncio event loop.
        Returns the Thread object immediately (non-blocking).
        """

        def _body() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self._async_extract(
                        especialidade=especialidade,
                        cidade=cidade,
                        estado=estado,
                        max_paginas=max_paginas,
                        min_score=min_score,
                        progress_queue=progress_queue,
                        result_queue=result_queue,
                        stop_event=stop_event,
                        headless=headless,
                    )
                )
            except Exception as exc:
                result_queue.put({"error": str(exc), "leads": [], "discarded": [], "elapsed": 0})
            finally:
                loop.close()

        t = threading.Thread(target=_body, daemon=True)
        t.start()
        return t

    async def _async_extract(
        self,
        especialidade: str,
        cidade: str,
        estado: str,
        max_paginas: int,
        min_score: int,
        progress_queue: queue.Queue,
        result_queue: queue.Queue,
        stop_event: threading.Event,
        headless: bool,
    ) -> None:
        start = time.monotonic()
        leads_raw: list = []

        progress_queue.put({"type": "status", "message": "Iniciando browser…"})

        try:
            async with BrowserManager(headless=headless) as browser:
                scraper = DoctoraliaScraper(browser, max_pages=max_paginas)

                # Inject progress tracking without modifying the backend class
                _orig = scraper._safe_get_profile

                async def _tracked(lead):
                    if stop_event.is_set():
                        return lead
                    progress_queue.put({
                        "type": "progress",
                        "message": f"Analisando: {lead.nome}",
                        "leads_found": len(scraper._leads_collected),
                    })
                    return await _orig(lead)

                scraper._safe_get_profile = _tracked

                progress_queue.put({
                    "type": "status",
                    "message": f"Buscando {especialidade} em {cidade}…",
                })

                leads_raw = await scraper.search(especialidade, cidade)
                if stop_event.is_set():
                    leads_raw = list(scraper._leads_collected)

        except Exception as exc:
            progress_queue.put({"type": "error", "message": str(exc)})
            result_queue.put({
                "error": str(exc),
                "leads": [],
                "discarded": [],
                "elapsed": 0,
                "especialidade": especialidade,
                "cidade": cidade,
                "estado": estado,
            })
            return

        progress_queue.put({"type": "status", "message": "Filtrando e pontuando leads…"})

        approved, discarded = ProfessionalFilter().filter_list(leads_raw)
        approved = QualityScorer().score_all(approved)

        if min_score > 0:
            approved = [l for l in approved if l.score_qualidade >= min_score]

        elapsed = time.monotonic() - start
        progress_queue.put({"type": "done"})

        result_queue.put({
            "leads": [_serialize(l.model_dump()) for l in approved],
            "discarded": [_serialize(l.model_dump()) for l in discarded],
            "elapsed": round(elapsed, 1),
            "especialidade": especialidade,
            "cidade": cidade,
            "estado": estado,
        })

    # ------------------------------------------------------------------ #
    # Persistence                                                          #
    # ------------------------------------------------------------------ #

    def save_leads(self, leads: list[dict], metadata: dict) -> int:
        """Append new (non-duplicate) leads and log the search. Returns count added."""
        self._ensure_data_files()
        data = _read_json(DB_PATH)
        existing_urls: set[str] = {l.get("doctoralia_url", "") for l in data.get("leads", [])}

        new_leads = []
        for lead in leads:
            url = lead.get("doctoralia_url", "")
            if url and url not in existing_urls:
                lead = dict(lead)
                lead["id"] = str(uuid.uuid4())
                new_leads.append(lead)
                existing_urls.add(url)

        data.setdefault("leads", []).extend(new_leads)
        if len(data["leads"]) > _MAX_LEADS:
            data["leads"] = data["leads"][-_MAX_LEADS:]

        _write_json(DB_PATH, data)

        history = _read_json(HISTORY_PATH)
        history.setdefault("searches", []).append({
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "especialidade": metadata.get("especialidade", ""),
            "cidade": metadata.get("cidade", ""),
            "estado": metadata.get("estado", ""),
            "total_leads": len(new_leads),
            "total_discarded": metadata.get("total_discarded", 0),
            "elapsed_seconds": round(float(metadata.get("elapsed", 0)), 1),
        })
        _write_json(HISTORY_PATH, history)

        return len(new_leads)

    def load_leads(self, filters: Optional[dict] = None) -> list[dict]:
        """Return leads from the database, with optional filtering."""
        self._ensure_data_files()
        leads = _read_json(DB_PATH).get("leads", [])

        if not filters:
            return leads

        if specs := filters.get("especialidades"):
            leads = [l for l in leads if l.get("especialidade") in specs]
        if cities := filters.get("cidades"):
            leads = [l for l in leads if l.get("cidade") in cities]
        if (s := filters.get("score_min")) is not None:
            leads = [l for l in leads if l.get("score_qualidade", 0) >= s]
        if filters.get("apenas_sem_site"):
            leads = [l for l in leads if not l.get("tem_site", False)]
        if filters.get("apenas_com_telefone"):
            leads = [l for l in leads if l.get("telefone_1")]
        if q := filters.get("nome_busca", "").lower():
            leads = [l for l in leads if q in l.get("nome", "").lower()]

        return leads

    def get_stats(self) -> dict:
        """Aggregate statistics for the sidebar."""
        self._ensure_data_files()
        leads = _read_json(DB_PATH).get("leads", [])
        searches = _read_json(HISTORY_PATH).get("searches", [])

        specs: dict[str, int] = {}
        cities: dict[str, int] = {}
        for l in leads:
            k = l.get("especialidade", "?")
            specs[k] = specs.get(k, 0) + 1
            k = l.get("cidade", "?")
            cities[k] = cities.get(k, 0) + 1

        total = len(leads)
        return {
            "total_leads": total,
            "total_searches": len(searches),
            "hot_leads": sum(1 for l in leads if l.get("score_qualidade", 0) >= 80),
            "qualified_leads": sum(1 for l in leads if 60 <= l.get("score_qualidade", 0) < 80),
            "with_phone": sum(1 for l in leads if l.get("telefone_1")),
            "without_site": sum(1 for l in leads if not l.get("tem_site", False)),
            "avg_score": round(
                sum(l.get("score_qualidade", 0) for l in leads) / max(total, 1), 1
            ),
            "top_specialties": sorted(specs.items(), key=lambda x: -x[1])[:5],
            "top_cities": sorted(cities.items(), key=lambda x: -x[1])[:5],
        }

    def load_history(self) -> list[dict]:
        return _read_json(HISTORY_PATH).get("searches", [])

    def delete_search(self, search_id: str) -> None:
        history = _read_json(HISTORY_PATH)
        history["searches"] = [s for s in history.get("searches", []) if s.get("id") != search_id]
        _write_json(HISTORY_PATH, history)

    def delete_leads(self, lead_ids: list[str]) -> int:
        data = _read_json(DB_PATH)
        ids = set(lead_ids)
        before = len(data.get("leads", []))
        data["leads"] = [l for l in data.get("leads", []) if l.get("id") not in ids]
        _write_json(DB_PATH, data)
        return before - len(data["leads"])

    def clear_all_leads(self) -> None:
        _write_json(DB_PATH, {"leads": [], "version": "1.0"})

    def get_db_size_kb(self) -> float:
        return round(DB_PATH.stat().st_size / 1024, 1) if DB_PATH.exists() else 0.0

    def load_settings(self) -> dict:
        self._ensure_data_files()
        return {**_default_settings(), **_read_json(SETTINGS_PATH)}

    def save_settings(self, settings: dict) -> None:
        _write_json(SETTINGS_PATH, settings)


# ------------------------------------------------------------------ #
# Module-level JSON helpers                                           #
# ------------------------------------------------------------------ #

def _read_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            if _HAS_LOCK:
                _pl.lock(f, _pl.LOCK_SH)
            data = json.load(f)
            if _HAS_LOCK:
                _pl.unlock(f)
            return data
    except (json.JSONDecodeError, FileNotFoundError, OSError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        if _HAS_LOCK:
            _pl.lock(f, _pl.LOCK_EX)
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        if _HAS_LOCK:
            _pl.unlock(f)


def _serialize(d: dict) -> dict:
    """Convert non-JSON-serializable values (datetime, etc.) to strings."""
    out = {}
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        elif isinstance(v, list):
            out[k] = [i.isoformat() if hasattr(i, "isoformat") else i for i in v]
        else:
            out[k] = v
    return out


def _default_settings() -> dict:
    return {
        "request_delay_min": 2.0,
        "request_delay_max": 5.0,
        "max_pages_default": 10,
        "headless_default": True,
        "min_score_default": 0,
        "csv_separator": ",",
        "output_dir": "output",
        "custom_palavras_clinica": [],
        "custom_titulos_profissional": [],
    }
