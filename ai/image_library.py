import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Optional

from ai.content_dedup import (
    canonicalize_url,
    get_content_identities,
)


DEFAULT_IMAGE_MANIFEST = Path(__file__).with_name("approved_images.json")
IMAGE_MANIFEST_ENV = "APPROVED_IMAGE_MANIFEST"
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")

# Kept as a compatibility hook for deployments that populate the approved
# image mapping in code. New entries must include the same metadata as manifest
# entries to be accepted.
APPROVED_IMAGES: dict[str, list[dict[str, Any]]] = {}


class ApprovedImageSourceError(RuntimeError):
    """Configured approved image source is invalid or unavailable."""


def _manifest_path() -> Path:
    configured_path = os.getenv(IMAGE_MANIFEST_ENV)
    if not configured_path:
        return DEFAULT_IMAGE_MANIFEST
    return Path(configured_path).expanduser().resolve()


def _read_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        if path == DEFAULT_IMAGE_MANIFEST:
            return []
        raise ApprovedImageSourceError(
            "Configured approved image manifest does not exist"
        )

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ApprovedImageSourceError(
            "Unable to read configured approved image manifest"
        ) from error

    if not isinstance(manifest, list):
        raise ApprovedImageSourceError(
            "Approved image manifest must contain a JSON array"
        )

    return manifest


def _validate_image_metadata(
    image: Any,
    manifest_directory: Path,
) -> Optional[dict[str, Any]]:
    if not isinstance(image, Mapping):
        raise ApprovedImageSourceError(
            "Each approved image entry must be a JSON object"
        )

    image_id = image.get("image_id")
    topic = image.get("topic")
    source = image.get("source")
    approved = image.get("approved")
    image_url = (
        image.get("image_url")
        or image.get("url")
        or image.get("canonical_url")
    )
    file_path = image.get("file_path")
    content_hash = image.get("content_hash")

    if not isinstance(approved, bool):
        raise ApprovedImageSourceError(
            "Image approval status must be a boolean"
        )
    if not approved:
        return None
    if not isinstance(topic, str) or not topic.strip():
        raise ApprovedImageSourceError(
            "Approved images require a topic"
        )
    if not isinstance(source, str) or not source.strip():
        raise ApprovedImageSourceError(
            "Approved images require a source"
        )
    if image_id is not None and (
        not isinstance(image_id, str) or not image_id.strip()
    ):
        raise ApprovedImageSourceError(
            "Image ID must be a non-empty string when provided"
        )
    if image_url is not None:
        if not isinstance(image_url, str):
            raise ApprovedImageSourceError(
                "Image URL must be a string"
            )
        try:
            canonical_url = canonicalize_url(image_url)
        except (TypeError, ValueError) as error:
            raise ApprovedImageSourceError(
                "Approved image URL must be an absolute HTTP(S) URL"
            ) from error
    else:
        canonical_url = None

    if content_hash is not None and (
        not isinstance(content_hash, str)
        or not SHA256_PATTERN.fullmatch(content_hash)
    ):
        raise ApprovedImageSourceError(
            "Image content hash must be a 64-character SHA-256 hex digest"
        )

    if file_path is not None:
        if not isinstance(file_path, str) or not file_path.strip():
            raise ApprovedImageSourceError(
                "Image file path must be a non-empty string"
            )
        resolved_path = (manifest_directory / file_path).resolve()
        if not resolved_path.is_relative_to(manifest_directory.resolve()):
            raise ApprovedImageSourceError(
                "Image file path must remain inside the manifest directory"
            )
        try:
            file_bytes = resolved_path.read_bytes()
        except OSError as error:
            raise ApprovedImageSourceError(
                "Unable to read approved image file"
            ) from error
        computed_hash = hashlib.sha256(file_bytes).hexdigest()
        if content_hash and content_hash.lower() != computed_hash:
            raise ApprovedImageSourceError(
                "Image content hash does not match the image file"
            )
        content_hash = computed_hash

    if content_hash is not None:
        content_hash = content_hash.lower()

    if not image_id and not canonical_url:
        raise ApprovedImageSourceError(
            "Approved images require a stable image ID or canonicalizable URL"
        )

    return {
        "image_id": image_id.strip() if image_id else None,
        "topic": topic.strip(),
        "source": source.strip(),
        "approved": True,
        "image_url": image_url.strip() if image_url else None,
        "canonical_url": canonical_url,
        "content_hash": content_hash,
    }


def get_approved_images(
    topic: Optional[str],
) -> list[dict[str, Any]]:
    if not topic:
        return []

    path = _manifest_path()
    manifest = _read_manifest(path)
    manifest.extend(
        image
        for images in APPROVED_IMAGES.values()
        for image in images
    )

    approved_images = []
    for image in manifest:
        validated = _validate_image_metadata(image, path.parent)
        if validated and validated["topic"] == topic:
            approved_images.append(validated)
    return approved_images


def get_image_content(
    topic: Optional[str],
    previously_sent: Optional[list[str]] = None,
    previously_used_identities: Optional[Iterable[str]] = None,
    approved_items: Optional[Iterable[Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    if not topic:
        return {
            "ready": False,
            "reason": "topic_missing",
            "topic": None,
            "image_url": None,
        }

    if approved_items is None:
        images = get_approved_images(topic)
    else:
        images = [
            image
            for item in approved_items
            if (
                image := _validate_image_metadata(
                    item,
                    DEFAULT_IMAGE_MANIFEST.parent,
                )
            )
            and image["topic"] == topic
        ]
    if not images:
        return {
            "ready": False,
            "reason": "approved_image_not_found",
            "topic": topic,
            "image_url": None,
            "deduplication": {
                "candidate_count": 0,
                "skipped_duplicates": [],
                "selected_identities": [],
                "selected_previously_used": False,
            },
        }

    previously_used = set(previously_used_identities or [])
    for previous_image in previously_sent or []:
        if previous_image.startswith(("http://", "https://")):
            previously_used.update(
                get_content_identities(
                    "image",
                    {"image_url": previous_image},
                )
            )
        else:
            previously_used.add(f"image:id:{previous_image.strip()}")

    skipped_duplicates = []
    for image in images:
        identities = get_content_identities("image", image)
        if identities.isdisjoint(previously_used):
            return {
                "ready": True,
                "reason": "approved_image_found",
                **image,
                "content_identities": identities,
                "deduplication": {
                    "candidate_count": len(images),
                    "skipped_duplicates": skipped_duplicates,
                    "selected_identities": sorted(identities),
                    "selected_previously_used": False,
                },
            }
        skipped_duplicates.append(
            {
                "identities": sorted(identities),
                "matched_identities": sorted(
                    identities.intersection(previously_used)
                ),
            }
        )

    return {
        "ready": False,
        "reason": "no_unused_approved_image",
        "topic": topic,
        "image_url": None,
        "deduplication": {
            "candidate_count": len(images),
            "skipped_duplicates": skipped_duplicates,
            "selected_identities": [],
            "selected_previously_used": False,
        },
    }
