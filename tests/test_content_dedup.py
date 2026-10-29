import os
import unittest
from datetime import timedelta
from unittest.mock import patch

os.environ.setdefault("DB_USERNAME", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ai.content_dedup import (
    canonicalize_url,
    get_content_identities,
    hash_text_content,
    select_content_item,
)
from ai.content_library import get_content
from ai.image_library import get_image_content
from ai.nurture_service import get_current_time, prepare_nurture_for_lead
from database import Base
from models import Lead, NurtureContentIdentity, NurtureMessage


class ContentDedupTests(unittest.TestCase):
    def test_text_hash_normalizes_line_endings_and_outer_whitespace(self):
        self.assertEqual(
            hash_text_content("  First line\r\nSecond line \r\n"),
            hash_text_content("First line\nSecond line"),
        )
        self.assertNotEqual(
            hash_text_content("First line\nSecond line"),
            hash_text_content("First line Second line"),
        )

    def test_invalid_text_and_url_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            hash_text_content(" \r\n ")
        with self.assertRaises(TypeError):
            hash_text_content(None)
        with self.assertRaises(ValueError):
            canonicalize_url("file:///tmp/article")
        with self.assertRaises(ValueError):
            canonicalize_url("https://")
        with self.assertRaises(ValueError):
            get_content_identities(
                "batch_update",
                {"message": "A batch announcement without a batch ID"},
            )

    def test_url_canonicalization_removes_tracking_and_normalizes_host(self):
        self.assertEqual(
            canonicalize_url(
                "HTTP://www.Example.com/article/?utm_source=email&b=2&a=1#section"
            ),
            "https://example.com/article?a=1&b=2",
        )
        self.assertNotEqual(
            canonicalize_url("https://example.com/article?edition=1"),
            canonicalize_url("https://example.com/article?edition=2"),
        )
        self.assertNotEqual(
            canonicalize_url("https://example.com:80/article"),
            canonicalize_url("https://example.com/article"),
        )

    def test_article_identity_matches_url_or_content_identifier(self):
        first = get_content_identities(
            "industry_update",
            {
                "content_id": "source-17",
                "source_url": "https://www.example.com/story?utm_campaign=spring",
                "summary": "A verified article",
            },
        )
        same_url = get_content_identities(
            "newsletter",
            {"source_url": "http://example.com/story/"},
        )
        same_id = get_content_identities(
            "article",
            {"content_id": "source-17", "summary": "Different summary"},
        )
        different = get_content_identities(
            "article",
            {"content_id": "source-18", "source_url": "https://example.com/other"},
        )

        self.assertTrue(first.intersection(same_url))
        self.assertTrue(first.intersection(same_id))
        self.assertTrue(first.isdisjoint(different))

    def test_image_and_batch_identity_options(self):
        image_by_url = get_content_identities(
            "image",
            {"image_url": "https://www.example.com/image.png?utm_source=x"},
        )
        image_by_id = get_content_identities(
            "image",
            {"image_id": "img-1", "content_hash": "ABC123"},
        )
        image_matching_id = get_content_identities(
            "image",
            {"id": "img-1"},
        )
        batch = get_content_identities(
            "batch_update",
            {"batch_id": "batch-2026-10", "message": "New batch starts soon"},
        )

        self.assertIn(
            "image:url:https://example.com/image.png",
            image_by_url,
        )
        self.assertIn("image:sha256:abc123", image_by_id)
        self.assertTrue(image_by_id.intersection(image_matching_id))
        self.assertIn("batch:id:batch-2026-10", batch)

    def test_content_selection_prefers_unused_candidate_and_falls_back(self):
        used = get_content_identities("educational", "Already used")
        selected, selected_ids = select_content_item(
            "educational",
            ["Already used", "Unused alternative"],
            used,
        )
        self.assertEqual(selected, "Unused alternative")
        self.assertTrue(selected_ids.isdisjoint(used))

        fallback, _ = select_content_item(
            "educational",
            ["Already used"],
            used,
        )
        self.assertEqual(fallback, "Already used")

    def test_image_library_uses_canonical_url_identity(self):
        from ai import image_library

        with patch.dict(
            image_library.APPROVED_IMAGES,
            {
                "Test topic": [
                    {
                        "image_id": "first",
                        "image_url": "https://www.example.com/first.png",
                        "topic": "Test topic",
                        "source": "approved catalog",
                        "approved": True,
                    },
                    {
                        "image_id": "second",
                        "image_url": "https://example.com/second.png",
                        "topic": "Test topic",
                        "source": "approved catalog",
                        "approved": True,
                    },
                ]
            },
        ):
            result = get_image_content(
                "Test topic",
                previously_sent=[
                    "http://example.com/first.png?utm_medium=email"
                ],
            )

        self.assertTrue(result["ready"])
        self.assertEqual(
            result["image_url"],
            "https://example.com/second.png",
        )

    def test_content_library_uses_unused_approved_text(self):
        used = get_content_identities("educational", "Previously approved")
        result = get_content(
            "educational",
            "AWS Cloud Engineering",
            previously_used_identities=used,
            approved_items=[
                {"message": "Previously approved"},
                {"message": "Alternative approved text"},
            ],
        )

        self.assertTrue(result["ready"])
        self.assertEqual(result["message"], "Alternative approved text")

    def test_content_library_uses_unused_article_image_and_batch(self):
        cases = [
            (
                "industry_update",
                [
                    {
                        "verified": True,
                        "content_id": "article-1",
                        "source_url": "https://example.com/used",
                        "summary": "Used article",
                    },
                    {
                        "verified": True,
                        "content_id": "article-2",
                        "source_url": "https://example.com/new",
                        "summary": "New article",
                    },
                ],
                get_content_identities(
                    "industry_update",
                    {
                        "content_id": "article-1",
                        "source_url": "https://example.com/used",
                        "summary": "Used article",
                    },
                ),
                "New article",
            ),
            (
                "batch_update",
                [
                    {"batch_id": "batch-1", "message": "Used batch"},
                    {"batch_id": "batch-2", "message": "New batch"},
                ],
                get_content_identities(
                    "batch_update",
                    {"batch_id": "batch-1", "message": "Used batch"},
                ),
                "New batch",
            ),
        ]

        for content_type, candidates, used, expected_message in cases:
            with self.subTest(content_type=content_type):
                result = get_content(
                    content_type,
                    "AWS Cloud Engineering",
                    previously_used_identities=used,
                    approved_items=candidates,
                )
                self.assertTrue(result["ready"])
                self.assertEqual(result["message"], expected_message)

    def test_content_library_uses_unused_approved_image(self):
        from ai import image_library

        with patch.dict(
            image_library.APPROVED_IMAGES,
            {
                "AWS Cloud Engineering": [
                    {
                        "image_id": "image-1",
                        "image_url": "https://example.com/used.png",
                        "topic": "AWS Cloud Engineering",
                        "source": "approved catalog",
                        "approved": True,
                    },
                    {
                        "image_id": "image-2",
                        "image_url": "https://example.com/new.png",
                        "topic": "AWS Cloud Engineering",
                        "source": "approved catalog",
                        "approved": True,
                    },
                ]
            },
        ):
            result = get_content(
                "image",
                "AWS Cloud Engineering",
                previously_used_identities=get_content_identities(
                    "image",
                    {"image_id": "image-1"},
                ),
            )

        self.assertTrue(result["ready"])
        self.assertEqual(
            result["message"],
            "https://example.com/new.png",
        )

    def test_articles_require_verified_content(self):
        result = get_content(
            "industry_update",
            "AWS Cloud Engineering",
            approved_items=[
                {
                    "verified": False,
                    "source_url": "https://example.com/article",
                    "summary": "Unverified article",
                }
            ],
        )

        self.assertFalse(result["ready"])
        self.assertEqual(result["reason"], "verified_content_required")


class NurtureWorkflowDedupTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)

    def test_prepare_nurture_skips_used_text_and_persists_selected_identity(self):
        now = get_current_time()
        previous_message = "Previously approved"
        lead = Lead(
            name="Test Lead",
            phone="1234567890",
            email="test@example.com",
            source="Website",
            status="new",
            ai_temperature="cold",
            interest="AWS Cloud Engineering",
        )
        self.session.add(lead)
        self.session.flush()

        previous_nurture = NurtureMessage(
            lead_id=lead.id,
            message=previous_message,
            content_type="educational",
            topic="AWS Cloud Engineering",
            stage=1,
            status="sent",
            created_at=now - timedelta(days=40),
            sent_at=now - timedelta(days=40),
        )
        self.session.add(previous_nurture)
        self.session.flush()
        self.session.add(
            NurtureContentIdentity(
                lead_id=lead.id,
                nurture_id=previous_nurture.id,
                identity=next(
                    iter(
                        get_content_identities(
                            "educational",
                            previous_message,
                        )
                    )
                ),
            )
        )
        self.session.commit()

        with patch(
            "ai.nurture_service.decide_engagement",
            return_value={
                "eligible": True,
                "reason": "engagement_allowed",
                "content_type": "educational",
                "topic": "AWS Cloud Engineering",
            },
        ):
            result = prepare_nurture_for_lead(
                db=self.session,
                lead_id=lead.id,
                current_time=now,
                approved_content={
                    "educational": [
                        {"message": previous_message},
                        {"message": "New approved alternative"},
                    ]
                },
            )

        self.assertTrue(result["ready_to_send"])
        self.assertEqual(result["message"], "New approved alternative")
        persisted_identities = {
            row.identity
            for row in self.session.query(NurtureContentIdentity)
            .filter(NurtureContentIdentity.nurture_id == result["nurture_id"])
            .all()
        }
        self.assertEqual(
            persisted_identities,
            get_content_identities(
                "educational",
                "New approved alternative",
            ),
        )

    def test_identity_conflict_rolls_back_partial_nurture(self):
        now = get_current_time()
        lead = Lead(
            name="Conflict Test Lead",
            phone="1234567890",
            email="conflict-test@example.com",
            source="Website",
            status="new",
            ai_temperature="cold",
            interest="AWS Cloud Engineering",
        )
        self.session.add(lead)
        self.session.flush()
        message = "Previously used approved text"
        previous = NurtureMessage(
            lead_id=lead.id,
            message=message,
            content_type="educational",
            topic="AWS Cloud Engineering",
            stage=1,
            status="sent",
            created_at=now - timedelta(days=40),
            sent_at=now - timedelta(days=40),
        )
        self.session.add(previous)
        self.session.flush()
        self.session.add(
            NurtureContentIdentity(
                lead_id=lead.id,
                nurture_id=previous.id,
                identity=next(
                    iter(get_content_identities("educational", message))
                ),
            )
        )
        self.session.commit()

        with (
            patch(
                "ai.nurture_service.decide_engagement",
                return_value={
                    "eligible": True,
                    "reason": "engagement_allowed",
                    "content_type": "educational",
                    "topic": "AWS Cloud Engineering",
                },
            ),
            patch(
                "ai.nurture_service.get_previous_content_identities",
                return_value=set(),
            ),
        ):
            result = prepare_nurture_for_lead(
                db=self.session,
                lead_id=lead.id,
                current_time=now,
                approved_content={
                    "educational": [{"message": message}]
                },
            )

        self.assertFalse(result["ready_to_send"])
        self.assertEqual(result["reason"], "duplicate_content_conflict")
        self.assertFalse(self.session.in_transaction())
        self.assertEqual(
            self.session.query(NurtureMessage)
            .filter(NurtureMessage.lead_id == lead.id)
            .count(),
            1,
        )


if __name__ == "__main__":
    unittest.main()
