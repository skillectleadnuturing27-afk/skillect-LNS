import hashlib
import json
import os
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any, Optional

from ai.content_dedup import get_content_identities


DEFAULT_BATCH_MANIFEST = Path(__file__).with_name("approved_batches.json")
BATCH_MANIFEST_ENV = "APPROVED_BATCH_MANIFEST"


class ApprovedBatchSourceError(RuntimeError):
    """Configured approved batch source is invalid or unavailable."""


def generate_batch_id(
    topic: str,
    batch_name: str,
    start_date: str,
) -> str:
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("Batch topic must be a non-empty string")
    if not isinstance(batch_name, str) or not batch_name.strip():
        raise ValueError("Batch name must be a non-empty string")
    if not isinstance(start_date, str) or not start_date.strip():
        raise ValueError("Batch start date must be a non-empty string")

    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_date.strip()):
            raise ValueError("Invalid batch start date format")
        normalized_date = date.fromisoformat(start_date.strip()).isoformat()
    except ValueError as error:
        raise ValueError("Batch start date must use YYYY-MM-DD format") from error

    stable_key = {
        "topic": " ".join(topic.split()).casefold(),
        "batch_name": " ".join(batch_name.split()).casefold(),
        "start_date": normalized_date,
    }
    encoded_key = json.dumps(
        stable_key,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(encoded_key).hexdigest()
    return f"generated-{digest}"


def _manifest_path() -> Path:
    configured_path = os.getenv(BATCH_MANIFEST_ENV)
    if not configured_path:
        return DEFAULT_BATCH_MANIFEST
    return Path(configured_path).expanduser().resolve()


def _read_manifest(path: Path) -> list[Any]:
    if not path.exists():
        if path == DEFAULT_BATCH_MANIFEST:
            return []
        raise ApprovedBatchSourceError(
            "Configured approved batch manifest does not exist"
        )

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ApprovedBatchSourceError(
            "Unable to read configured approved batch manifest"
        ) from error

    if not isinstance(manifest, list):
        raise ApprovedBatchSourceError(
            "Approved batch manifest must contain a JSON array"
        )
    return manifest


def _validate_batch(
    batch: Any,
) -> Optional[dict[str, Any]]:
    if not isinstance(batch, Mapping):
        raise ApprovedBatchSourceError(
            "Each approved batch entry must be a JSON object"
        )

    approved = batch.get("approved")
    if not isinstance(approved, bool):
        raise ApprovedBatchSourceError(
            "Batch approval status must be a boolean"
        )
    if not approved:
        return None

    topic = batch.get("topic")
    source = batch.get("source")
    if not isinstance(topic, str) or not topic.strip():
        raise ApprovedBatchSourceError(
            "Approved batches require a topic"
        )
    if not isinstance(source, str) or not source.strip():
        raise ApprovedBatchSourceError(
            "Approved batches require a source"
        )

    message = next(
        (
            batch.get(field)
            for field in ("message", "summary", "text")
            if isinstance(batch.get(field), str)
            and batch.get(field).strip()
        ),
        None,
    )
    if message is None:
        raise ApprovedBatchSourceError(
            "Approved batches require a non-empty message, summary, or text"
        )

    batch_id = batch.get("batch_id")
    if batch_id is not None:
        if not isinstance(batch_id, str) or not batch_id.strip():
            raise ApprovedBatchSourceError(
                "Batch ID must be a non-empty string when provided"
            )
        batch_id = batch_id.strip()
    else:
        batch_name = batch.get("batch_name")
        start_date = batch.get("start_date")
        if not isinstance(batch_name, str) or not batch_name.strip():
            raise ApprovedBatchSourceError(
                "Batches without an ID require a batch name"
            )
        if not isinstance(start_date, str) or not start_date.strip():
            raise ApprovedBatchSourceError(
                "Batches without an ID require a start date"
            )
        try:
            batch_id = generate_batch_id(
                topic,
                batch_name,
                start_date,
            )
        except ValueError as error:
            raise ApprovedBatchSourceError(
                "Batch identity fields are invalid"
            ) from error

    return {
        "batch_id": batch_id,
        "topic": topic.strip(),
        "source": source.strip(),
        "approved": True,
        "message": message.strip(),
    }


def load_approved_batch_candidates(
    topic: Optional[str],
) -> list[dict[str, Any]]:
    if not topic:
        return []

    path = _manifest_path()
    manifest = _read_manifest(path)
    candidates = []
    seen_identities: set[str] = set()

    for entry in manifest:
        batch = _validate_batch(entry)
        if not batch or batch["topic"] != topic:
            continue

        identities = get_content_identities("batch_update", batch)
        if identities.isdisjoint(seen_identities):
            seen_identities.update(identities)
            candidates.append(batch)

    return candidates
