import importlib
import os
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from io import BytesIO
from unittest.mock import patch

os.environ.setdefault("DB_USERNAME", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ai.article_feed import (
    ArticleFeedError,
    get_configured_feed_urls,
    load_approved_article_candidates,
)
from ai.content_dedup import get_content_identities
from ai.verified_content import is_trusted_source
from ai.nurture_service import get_current_time, prepare_nurture_for_lead
from database import Base
from models import Lead, NurtureContentIdentity, NurtureMessage


TOPIC = "AWS Cloud Engineering"
FEED_ENV = "RSS_FEEDS_AWS_CLOUD_ENGINEERING"


def make_rss_feed(items: list[dict[str, str]]) -> bytes:
    entries = []
    for item in items:
        entries.append(
            "<item>"
            f"<title>{item.get('title', 'AWS update')}</title>"
            f"<link>{item.get('url', 'https://aws.amazon.com/blogs/aws/story')}</link>"
            f"<guid>{item.get('id', 'story-1')}</guid>"
            f"<pubDate>{item.get('date', format_datetime(datetime.now(timezone.utc)))}</pubDate>"
            f"<description><![CDATA[{item.get('summary', 'Approved AWS update')}]]></description>"
            "</item>"
        )
    return (
        "<rss version='2.0'><channel>"
        + "".join(entries)
        + "</channel></rss>"
    ).encode("utf-8")


class ArticleFeedTests(unittest.TestCase):
    def test_feed_fetch_and_validation_accepts_fresh_trusted_rss_items(self):
        feed = make_rss_feed(
            [
                {
                    "id": "aws-story-1",
                    "url": "https://aws.amazon.com/blogs/aws/story",
                    "summary": "A current AWS article.",
                }
            ]
        )

        with (
            patch.dict(os.environ, {FEED_ENV: "https://aws.amazon.com/feed.xml"}),
            patch("ai.article_feed.urlopen", return_value=BytesIO(feed)),
        ):
            candidates = load_approved_article_candidates(
                "industry_update",
                TOPIC,
            )

        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0]["verified"])
        self.assertEqual(candidates[0]["content_id"], "aws-story-1")
        self.assertEqual(
            candidates[0]["source_url"],
            "https://aws.amazon.com/blogs/aws/story",
        )

    def test_untrusted_and_stale_entries_are_not_approved(self):
        now = datetime.now(timezone.utc)
        stale_date = format_datetime(
            now.replace(year=now.year - 1)
        )
        feed = make_rss_feed(
            [
                {
                    "id": "untrusted",
                    "url": "https://example.org/article",
                    "summary": "Untrusted source.",
                },
                {
                    "id": "stale",
                    "url": "https://aws.amazon.com/blogs/aws/old",
                    "date": stale_date,
                    "summary": "Stale article.",
                },
            ]
        )

        with (
            patch.dict(os.environ, {FEED_ENV: "https://aws.amazon.com/feed.xml"}),
            patch("ai.article_feed.urlopen", return_value=BytesIO(feed)),
        ):
            candidates = load_approved_article_candidates(
                "newsletter",
                TOPIC,
                now,
            )

        self.assertEqual(candidates, [])

    def test_trusted_domains_are_normalized_for_port_and_www_urls(self):
        self.assertTrue(
            is_trusted_source(
                TOPIC,
                "https://www.aws.amazon.com:443/blogs/aws/test?utm_source=feed",
            )
        )
        self.assertTrue(
            is_trusted_source(
                "Azure Cloud Engineering",
                "https://www.learn.microsoft.com:443/en-us/azure/architecture/",
            )
        )

    def test_canonical_url_and_text_hash_deduplicate_feed_entries(self):
        feed = make_rss_feed(
            [
                {
                    "id": "story-primary",
                    "url": "https://aws.amazon.com/blogs/aws/story?utm_source=rss",
                    "summary": "Repeated exact content.",
                },
                {
                    "id": "story-duplicate",
                    "url": "https://www.aws.amazon.com/blogs/aws/story/",
                    "summary": "Repeated exact content.",
                },
                {
                    "id": "story-new",
                    "url": "https://aws.amazon.com/blogs/aws/another",
                    "summary": "Different article content.",
                },
            ]
        )

        with (
            patch.dict(os.environ, {FEED_ENV: "https://aws.amazon.com/feed.xml"}),
            patch("ai.article_feed.urlopen", return_value=BytesIO(feed)),
        ):
            candidates = load_approved_article_candidates(
                "industry_update",
                TOPIC,
            )

        self.assertEqual(len(candidates), 2)
        first_identity_set = get_content_identities(
            "industry_update",
            candidates[0],
        )
        second_identity_set = get_content_identities(
            "industry_update",
            candidates[1],
        )
        self.assertTrue(first_identity_set.isdisjoint(second_identity_set))

    def test_unconfigured_feed_returns_no_candidates(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_configured_feed_urls(TOPIC), [])
            self.assertEqual(
                load_approved_article_candidates(
                    "industry_update",
                    TOPIC,
                ),
                [],
            )

    def test_untrusted_feed_url_is_rejected_before_fetch(self):
        with (
            patch.dict(os.environ, {FEED_ENV: "https://example.org/rss.xml"}),
            patch("ai.article_feed.urlopen") as fetch,
        ):
            with self.assertRaises(ArticleFeedError):
                load_approved_article_candidates(
                    "industry_update",
                    TOPIC,
                )
        fetch.assert_not_called()

    def test_invalid_xml_and_feed_fetch_errors_are_explicit(self):
        with patch(
            "ai.article_feed.urlopen",
            return_value=BytesIO(b"<rss><broken></rss>"),
        ):
            with self.assertRaises(ArticleFeedError):
                from ai.article_feed import fetch_feed_entries

                fetch_feed_entries("https://aws.amazon.com/feed.xml")

        with patch(
            "ai.article_feed.urlopen",
            side_effect=OSError("network unavailable"),
        ):
            with self.assertRaises(ArticleFeedError):
                fetch_feed_entries("https://aws.amazon.com/feed.xml")


class ArticleNurtureApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(Base.metadata, "create_all"):
            cls.api = importlib.import_module("ai.main")

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        with self.session_factory() as session:
            lead = Lead(
                name="Test Lead",
                phone="1234567890",
                email="article-test@example.com",
                source="Website",
                status="new",
                ai_temperature="cold",
                interest=TOPIC,
            )
            session.add(lead)
            session.commit()
            self.lead_id = lead.id

        def override_get_db():
            with self.session_factory() as session:
                yield session

        self.api.app.dependency_overrides[self.api.get_db] = override_get_db
        self.client = TestClient(self.api.app)
        self.addCleanup(self.client.close)
        self.addCleanup(
            lambda: self.api.app.dependency_overrides.pop(
                self.api.get_db,
                None,
            )
        )
        self.addCleanup(self.engine.dispose)

    def test_nurture_api_fetches_article_and_persists_identities(self):
        feed = make_rss_feed(
            [
                {
                    "id": "api-article-1",
                    "url": "https://aws.amazon.com/blogs/aws/api-story",
                    "summary": "Approved article body for API test.",
                }
            ]
        )

        with (
            patch.dict(os.environ, {FEED_ENV: "https://aws.amazon.com/feed.xml"}),
            patch("ai.article_feed.urlopen", return_value=BytesIO(feed)),
            patch(
                "ai.nurture_service.decide_engagement",
                return_value={
                    "eligible": True,
                    "reason": "engagement_allowed",
                    "content_type": "industry_update",
                    "topic": TOPIC,
                },
            ),
        ):
            response = self.client.post(
                f"/ai/nurture/{self.lead_id}"
            )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result["ready_to_send"])
        self.assertIn("AWS update", result["message"])
        self.assertIn("Approved article body for API test.", result["message"])
        self.assertIn(
            "https://aws.amazon.com/blogs/aws/api-story",
            result["message"],
        )

        with self.session_factory() as session:
            persisted = {
                row.identity
                for row in session.query(NurtureContentIdentity)
                .filter(
                    NurtureContentIdentity.nurture_id
                    == result["nurture_id"]
                )
                .all()
            }

        self.assertIn(
            "article:url:https://aws.amazon.com/blogs/aws/api-story",
            persisted,
        )
        self.assertIn("article:id:api-article-1", persisted)
        self.assertIn(
            next(
                identity
                for identity in get_content_identities(
                    "industry_update",
                    {
                        "summary": "Approved article body for API test."
                    },
                )
                if identity.startswith("text:sha256:")
            ),
            persisted,
        )

    def test_nurture_api_reports_feed_outage_as_service_unavailable(self):
        with (
            patch.dict(os.environ, {FEED_ENV: "https://aws.amazon.com/feed.xml"}),
            patch(
                "ai.article_feed.urlopen",
                side_effect=OSError("network unavailable"),
            ),
            patch(
                "ai.nurture_service.decide_engagement",
                return_value={
                    "eligible": True,
                    "reason": "engagement_allowed",
                    "content_type": "industry_update",
                    "topic": TOPIC,
                },
            ),
        ):
            response = self.client.post(
                f"/ai/nurture/{self.lead_id}"
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Approved article feed is temporarily unavailable",
        )

    def test_nurture_api_does_not_fallback_when_article_feed_is_unconfigured(self):
        with (
            patch.dict(os.environ, {FEED_ENV: ""}),
            patch(
                "ai.nurture_service.decide_engagement",
                return_value={
                    "eligible": True,
                    "reason": "engagement_allowed",
                    "content_type": "industry_update",
                    "topic": TOPIC,
                },
            ),
        ):
            response = self.client.post(
                f"/ai/nurture/{self.lead_id}"
            )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result["eligible"])
        self.assertFalse(result["ready_to_send"])
        self.assertEqual(result["reason"], "verified_content_required")
        self.assertIsNone(result.get("message"))

    def test_nurture_api_rejects_second_same_day_request(self):
        decision = {
            "eligible": True,
            "reason": "engagement_allowed",
            "content_type": "educational",
            "topic": TOPIC,
        }
        with patch(
            "ai.nurture_service.decide_engagement",
            return_value=decision,
        ):
            first = self.client.post(
                f"/ai/nurture/{self.lead_id}"
            )
            second = self.client.post(
                f"/ai/nurture/{self.lead_id}"
            )

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["ready_to_send"])
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["eligible"])
        self.assertEqual(
            second.json()["reason"],
            "already_generated_today",
        )
        with self.session_factory() as session:
            self.assertEqual(
                session.query(NurtureMessage)
                .filter(NurtureMessage.lead_id == self.lead_id)
                .count(),
                1,
            )

    def test_nurture_api_rolls_back_and_reports_database_commit_failure(self):
        with (
            patch(
                "ai.nurture_service.decide_engagement",
                return_value={
                    "eligible": True,
                    "reason": "engagement_allowed",
                    "content_type": "educational",
                    "topic": TOPIC,
                },
            ),
            patch.object(
                Session,
                "commit",
                side_effect=OperationalError(
                    "COMMIT",
                    {},
                    RuntimeError("simulated isolated test failure"),
                ),
            ),
        ):
            response = self.client.post(
                f"/ai/nurture/{self.lead_id}"
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json()["detail"],
            "Unable to prepare nurture message",
        )
        with self.session_factory() as session:
            self.assertEqual(
                session.query(NurtureMessage)
                .filter(NurtureMessage.lead_id == self.lead_id)
                .count(),
                0,
            )
            self.assertEqual(
                session.query(NurtureContentIdentity)
                .filter(NurtureContentIdentity.lead_id == self.lead_id)
                .count(),
                0,
            )

    def test_nurture_skips_previously_used_article_and_persists_next_identity(self):
        now = get_current_time()
        with self.session_factory() as session:
            previous = NurtureMessage(
                lead_id=self.lead_id,
                message="Previously approved article",
                content_type="industry_update",
                topic=TOPIC,
                stage=1,
                status="sent",
                created_at=now - timedelta(days=40),
                sent_at=now - timedelta(days=40),
            )
            session.add(previous)
            session.flush()
            session.add(
                NurtureContentIdentity(
                    lead_id=self.lead_id,
                    nurture_id=previous.id,
                    identity=(
                        "article:url:"
                        "https://aws.amazon.com/blogs/aws/used-story"
                    ),
                )
            )
            session.commit()

            feed = make_rss_feed(
                [
                    {
                        "id": "used-article",
                        "url": "https://aws.amazon.com/blogs/aws/used-story",
                        "summary": "Previously approved article",
                    },
                    {
                        "id": "new-article",
                        "url": "https://aws.amazon.com/blogs/aws/new-story",
                        "summary": "New approved article",
                    },
                ]
            )

            with (
                patch.dict(
                    os.environ,
                    {FEED_ENV: "https://aws.amazon.com/feed.xml"},
                ),
                patch("ai.article_feed.urlopen", return_value=BytesIO(feed)),
                patch(
                    "ai.nurture_service.decide_engagement",
                    return_value={
                        "eligible": True,
                        "reason": "engagement_allowed",
                        "content_type": "industry_update",
                        "topic": TOPIC,
                    },
                ),
            ):
                result = prepare_nurture_for_lead(
                    db=session,
                    lead_id=self.lead_id,
                    current_time=now,
                )

            self.assertTrue(result["ready_to_send"])
            self.assertIn("New approved article", result["message"])
            self.assertIn("new-story", result["message"])
            self.assertNotIn("used-story", result["message"])
            saved = {
                row.identity
                for row in session.query(NurtureContentIdentity)
                .filter(
                    NurtureContentIdentity.nurture_id
                    == result["nurture_id"]
                )
                .all()
            }
            self.assertIn(
                "article:url:https://aws.amazon.com/blogs/aws/new-story",
                saved,
            )
