import hashlib
import ipaddress
import re
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}


def normalize_text_content(content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("Content must be a string")

    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError("Content must not be empty")

    return normalized


def hash_text_content(content: str) -> str:
    normalized = normalize_text_content(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def canonicalize_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string")

    try:
        parsed = urlsplit(url.strip())
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise ValueError("URL is invalid") from error

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("URL must be an absolute HTTP(S) URL without credentials")

    try:
        hostname = str(ipaddress.ip_address(hostname))
    except ValueError:
        try:
            hostname = hostname.encode("idna").decode("ascii").lower()
        except UnicodeError as error:
            raise ValueError("URL hostname is invalid") from error

    if ":" not in hostname and hostname.startswith("www."):
        hostname = hostname[4:]

    if not hostname:
        raise ValueError("URL hostname is invalid")

    default_port = 80 if parsed.scheme.lower() == "http" else 443
    if port is not None and port != default_port:
        netloc = (
            f"[{hostname}]:{port}"
            if ":" in hostname
            else f"{hostname}:{port}"
        )
    else:
        netloc = f"[{hostname}]" if ":" in hostname else hostname

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"

    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_KEYS
        and not key.lower().startswith("utm_")
    ]
    query.sort()

    return urlunsplit(
        (
            "https",
            netloc,
            path,
            urlencode(query, doseq=True),
            "",
        )
    )


def get_content_identities(
    content_type: str,
    item: str | Mapping[str, Any],
) -> set[str]:
    if not isinstance(content_type, str) or not content_type.strip():
        raise ValueError("Content type must be a non-empty string")

    normalized_type = content_type.strip().lower()
    if isinstance(item, str):
        return {f"text:sha256:{hash_text_content(item)}"}

    if not isinstance(item, Mapping):
        raise TypeError("Content item must be a string or mapping")

    identities: set[str] = set()

    if normalized_type in {"industry_update", "newsletter", "article"}:
        content_id = item.get("content_id") or item.get("id")
        if content_id is not None:
            value = str(content_id).strip()
            if value:
                identities.add(f"article:id:{value}")

        source_url = (
            item.get("source_url")
            or item.get("article_url")
            or item.get("url")
        )
        if source_url is not None:
            identities.add(
                f"article:url:{canonicalize_url(source_url)}"
            )

        text = item.get("summary") or item.get("text") or item.get("message")
        if text is not None:
            identities.add(f"text:sha256:{hash_text_content(text)}")

    elif normalized_type == "image":
        image_id = item.get("image_id") or item.get("content_id") or item.get("id")
        if image_id is not None:
            value = str(image_id).strip()
            if value:
                identities.add(f"image:id:{value}")

        image_url = (
            item.get("image_url")
            or item.get("url")
            or item.get("canonical_url")
        )
        if image_url is not None:
            identities.add(f"image:url:{canonicalize_url(image_url)}")

        content_hash = item.get("content_hash") or item.get("sha256")
        if content_hash is not None:
            value = str(content_hash).strip().lower()
            if value:
                identities.add(f"image:sha256:{value}")

    elif normalized_type == "batch_update":
        batch_id = item.get("batch_id") or item.get("content_id") or item.get("id")
        if batch_id is None or not str(batch_id).strip():
            raise ValueError(
                "Batch updates require a stable batch identifier"
            )

        identities.add(f"batch:id:{str(batch_id).strip()}")

        text = item.get("message") or item.get("text")
        if text is not None:
            identities.add(f"text:sha256:{hash_text_content(text)}")

    else:
        text = item.get("message") or item.get("text") or item.get("content")
        if text is not None:
            identities.add(f"text:sha256:{hash_text_content(text)}")

    if not identities:
        raise ValueError(
            f"Content item for {normalized_type!r} has no usable identity"
        )

    return identities


def select_content_item(
    content_type: str,
    items: Iterable[str | Mapping[str, Any]],
    previously_used: Iterable[str] = (),
) -> tuple[str | Mapping[str, Any] | None, set[str]]:
    selected, identities, _ = select_content_item_with_report(
        content_type,
        items,
        previously_used,
    )
    return selected, identities


def select_content_item_with_report(
    content_type: str,
    items: Iterable[str | Mapping[str, Any]],
    previously_used: Iterable[str] = (),
) -> tuple[
    str | Mapping[str, Any] | None,
    set[str],
    dict[str, Any],
]:
    candidates = list(items)
    if not candidates:
        return None, set(), {
            "candidate_count": 0,
            "skipped_duplicates": [],
            "selected_identities": [],
            "selected_previously_used": False,
        }

    used = set(previously_used)
    identified_candidates = [
        (item, get_content_identities(content_type, item))
        for item in candidates
    ]

    skipped_duplicates = [
        {
            "identities": sorted(identities),
            "matched_identities": sorted(identities.intersection(used)),
        }
        for _, identities in identified_candidates
        if not identities.isdisjoint(used)
    ]

    for item, identities in identified_candidates:
        if identities.isdisjoint(used):
            return item, identities, {
                "candidate_count": len(candidates),
                "skipped_duplicates": skipped_duplicates,
                "selected_identities": sorted(identities),
                "selected_previously_used": False,
            }

    selected, identities = identified_candidates[0]
    return selected, identities, {
        "candidate_count": len(candidates),
        "skipped_duplicates": skipped_duplicates,
        "selected_identities": sorted(identities),
        "selected_previously_used": True,
    }


def extract_urls(text: str) -> set[str]:
    urls = re.findall(r"https?://[^\s<>\"']+", text)
    identities = set()
    for url in urls:
        cleaned_url = url.rstrip(".,;:!?)\\]")
        try:
            identities.add(canonicalize_url(cleaned_url))
        except ValueError:
            continue
    return identities
