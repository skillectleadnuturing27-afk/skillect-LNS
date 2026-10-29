from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


# =========================================================
# CONFIGURATION
# =========================================================

INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")

DEFAULT_MAX_AGE_DAYS = 30


# =========================================================
# TRUSTED OFFICIAL SOURCES
# =========================================================

TRUSTED_SOURCES = {
    "AWS Cloud Engineering": {
        "aws.amazon.com",
    },

    "Azure Cloud Engineering": {
        "azure.microsoft.com",
        "learn.microsoft.com",
    },
}


# =========================================================
# SUPPORTED LIVE CONTENT
# =========================================================

LIVE_CONTENT_TYPES = {
    "industry_update",
    "newsletter",
}


# =========================================================
# CURRENT TIME
# =========================================================

def get_current_time() -> datetime:
    return datetime.now(INDIA_TIMEZONE)


# =========================================================
# NORMALIZE SOURCE DOMAIN
# =========================================================

def get_source_domain(
    source_url: Optional[str],
) -> Optional[str]:

    if not source_url:
        return None

    try:
        parsed = urlparse(source_url.strip())

        if parsed.scheme not in {"http", "https"}:
            return None

        hostname = parsed.hostname
        if not hostname:
            return None

        domain = hostname.encode("idna").decode("ascii").lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain or None

    except (TypeError, ValueError, UnicodeError):
        return None


# =========================================================
# CHECK TRUSTED SOURCE
# =========================================================

def is_trusted_source(
    topic: Optional[str],
    source_url: Optional[str],
) -> bool:

    if not topic or not source_url:
        return False

    domain = get_source_domain(source_url)

    if not domain:
        return False

    allowed_domains = TRUSTED_SOURCES.get(
        topic,
        set(),
    )

    for allowed_domain in allowed_domains:

        if (
            domain == allowed_domain
            or domain.endswith("." + allowed_domain)
        ):
            return True

    return False


# =========================================================
# NORMALIZE DATETIME
# =========================================================

def ensure_timezone(
    value: Optional[datetime],
) -> Optional[datetime]:

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=INDIA_TIMEZONE
        )

    return value


# =========================================================
# CHECK CONTENT FRESHNESS
# =========================================================

def is_content_fresh(
    published_at: Optional[datetime],
    current_time: Optional[datetime] = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> bool:

    if published_at is None:
        return False

    if current_time is None:
        current_time = get_current_time()

    published_at = ensure_timezone(
        published_at
    )

    current_time = ensure_timezone(
        current_time
    )

    # Future-dated content is invalid
    if published_at > current_time:
        return False

    oldest_allowed = (
        current_time
        - timedelta(days=max_age_days)
    )

    return published_at >= oldest_allowed


# =========================================================
# GENERIC VERIFIED CONTENT VALIDATOR
# =========================================================

def validate_verified_content(
    content_type: Optional[str],
    topic: Optional[str],
    title: Optional[str],
    summary: Optional[str],
    source_url: Optional[str],
    published_at: Optional[datetime],
    current_time: Optional[datetime] = None,
) -> Dict[str, Any]:

    # -----------------------------------------------------
    # CONTENT TYPE
    # -----------------------------------------------------

    if not content_type:
        return {
            "verified": False,
            "reason": "content_type_missing",
        }

    content_type = content_type.lower().strip()

    if content_type not in LIVE_CONTENT_TYPES:
        return {
            "verified": False,
            "reason": "unsupported_live_content_type",
            "content_type": content_type,
        }

    # -----------------------------------------------------
    # REQUIRED DATA
    # -----------------------------------------------------

    if not topic:
        return {
            "verified": False,
            "reason": "topic_missing",
        }

    if not title or not title.strip():
        return {
            "verified": False,
            "reason": "title_missing",
        }

    if not summary or not summary.strip():
        return {
            "verified": False,
            "reason": "summary_missing",
        }

    if not source_url:
        return {
            "verified": False,
            "reason": "source_url_missing",
        }

    if published_at is None:
        return {
            "verified": False,
            "reason": "published_date_missing",
        }

    # -----------------------------------------------------
    # TRUSTED SOURCE
    # -----------------------------------------------------

    if not is_trusted_source(
        topic,
        source_url,
    ):
        return {
            "verified": False,
            "reason": "untrusted_source",
            "content_type": content_type,
            "topic": topic,
            "source_url": source_url,
        }

    # -----------------------------------------------------
    # FRESHNESS
    # -----------------------------------------------------

    if not is_content_fresh(
        published_at,
        current_time,
    ):
        return {
            "verified": False,
            "reason": "content_not_fresh",
            "content_type": content_type,
            "topic": topic,
            "source_url": source_url,
        }

    # -----------------------------------------------------
    # VERIFIED CONTENT
    # -----------------------------------------------------

    return {
        "verified": True,
        "reason": "verified_content",
        "content_type": content_type,
        "topic": topic,
        "title": title.strip(),
        "summary": summary.strip(),

        # IMPORTANT:
        # Original official source is preserved.
        "source_url": source_url.strip(),

        "published_at": ensure_timezone(
            published_at
        ),
    }


# =========================================================
# INDUSTRY UPDATE WRAPPER
# =========================================================

def validate_industry_content(
    topic: Optional[str],
    title: Optional[str],
    message: Optional[str],
    source_url: Optional[str],
    published_at: Optional[datetime],
    current_time: Optional[datetime] = None,
) -> Dict[str, Any]:

    return validate_verified_content(
        content_type="industry_update",
        topic=topic,
        title=title,
        summary=message,
        source_url=source_url,
        published_at=published_at,
        current_time=current_time,
    )


# =========================================================
# NEWSLETTER WRAPPER
# =========================================================

def validate_newsletter_content(
    topic: Optional[str],
    title: Optional[str],
    summary: Optional[str],
    source_url: Optional[str],
    published_at: Optional[datetime],
    current_time: Optional[datetime] = None,
) -> Dict[str, Any]:

    return validate_verified_content(
        content_type="newsletter",
        topic=topic,
        title=title,
        summary=summary,
        source_url=source_url,
        published_at=published_at,
        current_time=current_time,
    )