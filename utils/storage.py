"""Loading pitches and persisting experiment records as JSON and CSV."""

from __future__ import annotations

import csv
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import config


@dataclass(frozen=True)
class Pitch:
    """A business pitch in the evaluation dataset."""

    pitch_id: str
    title: str
    pitch_text: str
    # Optional: id of the base pitch this one is a modified variant of (sensitivity study).
    variant_of: str | None = None
    notes: str = ""


def load_pitches(path: Path | None = None) -> list[Pitch]:
    """Load pitches from ``data/pitches`` (all ``*.json`` and ``*.csv`` files).

    JSON files may contain one pitch object or a list of them. CSV files need
    the columns ``pitch_id, title, pitch_text`` and may include ``variant_of``.
    Pitches are returned sorted by ``pitch_id``; duplicate ids raise an error.
    """
    directory = path or config.PITCHES_DIR
    pitches: dict[str, Pitch] = {}

    def _add(record: dict[str, Any], source: Path) -> None:
        try:
            pitch = Pitch(
                pitch_id=str(record["pitch_id"]).strip(),
                title=str(record.get("title", "")).strip(),
                pitch_text=str(record["pitch_text"]).strip(),
                variant_of=(str(record["variant_of"]).strip() or None)
                if record.get("variant_of")
                else None,
                notes=str(record.get("notes", "") or ""),
            )
        except KeyError as exc:
            raise ValueError(f"{source}: missing required field {exc}") from exc
        if pitch.pitch_id in pitches:
            raise ValueError(f"Duplicate pitch_id '{pitch.pitch_id}' in {source}")
        pitches[pitch.pitch_id] = pitch

    for file in sorted(directory.glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        for record in data if isinstance(data, list) else [data]:
            _add(record, file)
    for file in sorted(directory.glob("*.csv")):
        with file.open(newline="", encoding="utf-8") as fh:
            for record in csv.DictReader(fh):
                _add(record, file)
    return [pitches[k] for k in sorted(pitches)]


def get_pitch(pitch_id: str) -> Pitch:
    """Return the pitch with ``pitch_id`` or raise ``KeyError``."""
    for pitch in load_pitches():
        if pitch.pitch_id == pitch_id:
            return pitch
    raise KeyError(f"Unknown pitch_id '{pitch_id}'")


def new_run_id() -> str:
    """Short unique run identifier."""
    return uuid.uuid4().hex[:12]


def utc_timestamp() -> str:
    """ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Columns written to the flat CSV (nested outputs stay in JSON only).
CSV_COLUMNS: tuple[str, ...] = (
    "run_id",
    "pitch_id",
    "system_type",
    "run_number",
    "experiment",
    "model",
    "temperature",
    "max_output_tokens",
    "target_output_words",
    "timestamp",
    "latency_seconds",
    "sequential_latency_seconds",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "estimated_cost_usd",
    "word_count",
    "token_count",
    "within_length_budget",
    "missing_sections",
    "llm_calls",
    "final_length_correction_calls",
    "json_path",
)


def save_run(record: dict[str, Any], subdir: str = "runs") -> Path:
    """Persist one run record as JSON and append a flat row to ``runs.csv``.

    Returns the path of the JSON file.
    """
    out_dir = config.OUTPUTS_DIR / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = (
        f"{record['pitch_id']}_{record['system_type']}_r{record['run_number']:02d}_"
        f"{record['run_id']}.json"
    )
    json_path = out_dir / filename
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    row = {col: record.get(col, "") for col in CSV_COLUMNS}
    row["json_path"] = str(json_path.relative_to(config.PROJECT_ROOT))
    row["missing_sections"] = "|".join(record.get("missing_sections", []))
    append_csv_row(config.RUNS_CSV, row, CSV_COLUMNS)
    return json_path


def append_csv_row(path: Path, row: dict[str, Any], columns: Iterable[str]) -> None:
    """Append ``row`` to a CSV file, writing the header if the file is new."""
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns))
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def load_run_json(path: Path) -> dict[str, Any]:
    """Load one saved run record."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_all_runs(subdir: str | None = None) -> list[dict[str, Any]]:
    """Load every saved run JSON (optionally restricted to one output subdir)."""
    base = config.OUTPUTS_DIR / subdir if subdir else config.OUTPUTS_DIR
    return [load_run_json(p) for p in sorted(base.rglob("*.json"))]
