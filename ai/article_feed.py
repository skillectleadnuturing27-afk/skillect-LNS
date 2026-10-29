import os
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Mapping, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from ai.content_dedup import get_content_identities
from ai.verified_content import (
    validate_industry_content,
    validate_newsletter_content,
    is_trusted_source,
)


FEED_TIMEOUT_SECONDS = 8
MAX_FEED_BYTES = 2_000_000
MAX_FEED_ITEMS = 100


class ArticleFeedError(RuntimeError):
    """A configured article feed could not be fetched or parsed."""


def get_configured_feed_urls(topic: str) -> list[str]:
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("Topic must be a non-empty string")

    topic_key = re.sub(r"[^A-Za-z0-9]+", "_", topic.strip()).strip("_").upper()
    configured = os.getenv(f"RSS_FEEDS_{topic_key}", "")
    return [
        feed_url.strip()
        for feed_url in configured.split(";")
        if feed_url.strip()
    ]


def _local_name(tag: str) -> str:
    # RSS and Atom feeds may use different XML namespaces for the same elements.
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element: ElementTree.Element, *names: str) -> Optional[str]:
    wanted = {name.lower() for name in names}
    children = [
        child for child in element
        if _local_name(child.tag) in wanted
    ]
    if "link" in wanted:
        # Prefer the canonical/alternate Atom link over related links.
        children.sort(
            key=lambda child: (
                child.attrib.get("rel", "alternate") != "alternate"
            )
        )

    for child in children:
        href = child.attrib.get("href")
        value = href or "".join(child.itertext())
        if value and value.strip():
            return value.strip()
    return None


def _parse_published_at(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            return datetime.fromisoformat(
                value.strip().replace("Z", "+00:00")
            )
        except ValueError:
            return None


def _parse_feed_entries(feed_xml: bytes) -> list[dict[str, Any]]:
    try:
        root = ElementTree.fromstring(feed_xml)
    except ElementTree.ParseError as error:
        raise ArticleFeedError("Configured RSS feed returned invalid XML") from error

    entries = [
        element
        for element in root.iter()
        if _local_name(element.tag) in {"item", "entry"}
    ]
    parsed_entries = []

    for entry in entries[:MAX_FEED_ITEMS]:
        title = _child_text(entry, "title")
        source_url = _child_text(entry, "link")
        summary = _child_text(
            entry,
            "description",
            "summary",
            "encoded",
            "content",
        )
        published_at = _parse_published_at(
            _child_text(
                entry,
                "pubdate",
                "published",
                "updated",
                "date",
            )
        )
        content_id = _child_text(entry, "guid", "id")

        parsed_entries.append(
            {
                "title": title,
                "source_url": source_url,
                "summary": summary,
                "published_at": published_at,
                "content_id": content_id,
            }
        )

    return parsed_entries


def fetch_feed_entries(feed_url: str) -> list[dict[str, Any]]:
    if not isinstance(feed_url, str) or not feed_url.strip():
        raise ValueError("Feed URL must be a non-empty string")

    request = Request(
        feed_url.strip(),
        headers={"User-Agent": "SkillectNurture/1.0"},
    )
    try:
        with urlopen(request, timeout=FEED_TIMEOUT_SECONDS) as response:
            # Read one byte beyond the limit so oversized feeds are detected.
            feed_xml = response.read(MAX_FEED_BYTES + 1)
    except (URLError, TimeoutError, OSError) as error:
        raise ArticleFeedError("Unable to fetch configured RSS feed") from error

    if len(feed_xml) > MAX_FEED_BYTES:
        raise ArticleFeedError("Configured RSS feed exceeds the size limit")

    return _parse_feed_entries(feed_xml)


def _validate_entry(
    content_type: str,
    topic: str,
    entry: Mapping[str, Any],
    current_time: Optional[datetime] = None,
) -> Optional[dict[str, Any]]:
    validator = (
        validate_industry_content
        if content_type == "industry_update"
        else validate_newsletter_content
    )

    validation_args = {
        "topic": topic,
        "title": entry.get("title"),
        "source_url": entry.get("source_url"),
        "published_at": entry.get("published_at"),
        "current_time": current_time,
    }
    if content_type == "industry_update":
        validation_args["message"] = entry.get("summary")
    else:
        validation_args["summary"] = entry.get("summary")

    validated = validator(**validation_args)
    if not validated.get("verified"):
        return None

    validated["content_id"] = entry.get("content_id")
    validated["message"] = validated["summary"]
    validated["share_message"] = (
        f"{validated['title']}\n"
        f"{validated['summary']}\n"
        f"{validated['source_url']}"
    )
    return validated


def load_approved_article_candidates(
    content_type: str,
    topic: str,
    current_time: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    if content_type not in {"industry_update", "newsletter"}:
        raise ValueError("Unsupported article content type")

    candidates: list[dict[str, Any]] = []
    seen_identities: set[str] = set()

    for feed_url in get_configured_feed_urls(topic):
        # Validate the configured feed itself before making a network request.
        if not is_trusted_source(topic, feed_url):
            raise ArticleFeedError(
                f"Configured feed is not trusted for topic {topic!r}"
            )

        entries = fetch_feed_entries(feed_url)
        for entry in entries:
            validated = _validate_entry(
                content_type,
                topic,
                entry,
                current_time,
            )
            if not validated:
                continue

            identities = get_content_identities(
                content_type,
                validated,
            )
            # Feeds can overlap; retain only the first validated copy of each item.
            if identities.isdisjoint(seen_identities):
                seen_identities.update(identities)
                candidates.append(validated)

    return candidates
