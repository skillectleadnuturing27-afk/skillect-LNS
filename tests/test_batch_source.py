import importlib
import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DB_USERNAME", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ai.batch_library import (
    ApprovedBatchSourceError,
    generate_batch_id,
    load_approved_batch_candidates,
)
from ai.content_dedup import get_content_identities
from ai.nurture_service import get_current_time
from database import Base
from models import Lead, NurtureContentIdentity, NurtureMessage


TOPIC = "AWS Cloud Engineering"
BATCH_ENV = "APPROVED_BATCH_MANIFEST"


class BatchSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.manifest = self.root / "approved-batches.json"

    def write_manifest(self, entries):
        self.manifest.write_text(
            json.dumps(entries),
            encoding="utf-8",
        )
        return str(self.manifest)

    def batch(self, **overrides):
        record = {
            "batch_name": "AWS October Cohort",
            "start_date": "2026-10-30",
            "topic": TOPIC,
            "source": "Approved internal batch catalog",
            "approved": True,
            "message": "The AWS October cohort is accepting learners.",
        }
        record.update(overrides)
        return record

    def test_generated_batch_id_is_stable_and_normalizes_identity_fields(self):
        first = generate_batch_id(
            TOPIC,
            " AWS   October Cohort ",
            "2026-10-30",
        )
        same_batch = generate_batch_id(
            TOPIC.lower().replace("aws", "AWS"),
            "AWS October Cohort",
            "2026-10-30",
        )
        different_batch = generate_batch_id(
            TOPIC,
            "AWS November Cohort",
            "2026-10-30",
        )

        self.assertEqual(first, same_batch)
        self.assertTrue(first.startswith("generated-"))
        self.assertNotEqual(first, different_batch)
        with self.assertRaises(ValueError):
            generate_batch_id(TOPIC, "AWS Cohort", "30-10-2026")

    def test_manifest_validates_records_and_ignores_unapproved_items(self):
        manifest = self.write_manifest(
            [
                self.batch(),
                self.batch(
                    batch_id="not-approved",
                    approved=False,
                    topic=None,
                ),
                self.batch(
                    topic="Azure Cloud Engineering",
                    batch_id="azure-1",
                ),
            ]
        )

        with patch.dict(os.environ, {BATCH_ENV: manifest}):
            batches = load_approved_batch_candidates(TOPIC)

        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0]["source"], "Approved internal batch catalog")
        self.assertEqual(
            batches[0]["batch_id"],
            generate_batch_id(TOPIC, "AWS October Cohort", "2026-10-30"),
        )

    def test_invalid_approved_records_and_unavailable_manifest_are_reported(self):
        invalid_records = [
            self.batch(source=" "),
            self.batch(approved="yes"),
            self.batch(message=" "),
            self.batch(batch_name=None),
            self.batch(start_date="not-a-date"),
            self.batch(batch_id=123),
        ]
        for record in invalid_records:
            with self.subTest(record=record):
                manifest = self.write_manifest([record])
                with patch.dict(os.environ, {BATCH_ENV: manifest}):
                    with self.assertRaises(ApprovedBatchSourceError):
                        load_approved_batch_candidates(TOPIC)

        with patch.dict(
            os.environ,
            {BATCH_ENV: str(self.root / "missing.json")},
        ):
            with self.assertRaises(ApprovedBatchSourceError):
                load_approved_batch_candidates(TOPIC)

    def test_loader_generates_stable_ids_and_collapses_repeated_batches(self):
        manifest = self.write_manifest(
            [
                self.batch(),
                self.batch(message="Updated message for the same batch."),
            ]
        )

        with patch.dict(os.environ, {BATCH_ENV: manifest}):
            first_load = load_approved_batch_candidates(TOPIC)
            second_load = load_approved_batch_candidates(TOPIC)

        self.assertEqual(len(first_load), 1)
        self.assertEqual(
            first_load[0]["batch_id"],
            second_load[0]["batch_id"],
        )
        self.assertEqual(
            get_content_identities("batch_update", first_load[0]),
            get_content_identities("batch_update", second_load[0]),
        )


class BatchNurtureApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(Base.metadata, "create_all"):
            cls.api = importlib.import_module("ai.main")

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.manifest_path = Path(self.temp_dir.name) / "batches.json"
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
                name="Batch Test Lead",
                phone="1234567890",
                email="batch-test@example.com",
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

    def write_manifest(self, entries):
        self.manifest_path.write_text(
            json.dumps(entries),
            encoding="utf-8",
        )

    def batch(self, name, message, batch_id=None):
        record = {
            "batch_name": name,
            "start_date": "2026-10-30",
            "topic": TOPIC,
            "source": "Approved internal batch catalog",
            "approved": True,
            "message": message,
        }
        if batch_id:
            record["batch_id"] = batch_id
        return record

    def test_nurture_api_selects_unused_batch_and_persists_its_identity(self):
        used_id = generate_batch_id(
            TOPIC,
            "AWS October Cohort",
            "2026-10-30",
        )
        self.write_manifest(
            [
                self.batch(
                    "AWS October Cohort",
                    "The AWS October cohort is accepting learners.",
                ),
                self.batch(
                    "AWS November Cohort",
                    "The AWS November cohort is accepting learners.",
                    "aws-november-2026",
                ),
            ]
        )
        now = get_current_time()
        with self.session_factory() as session:
            previous = NurtureMessage(
                lead_id=self.lead_id,
                message="Previously announced AWS October cohort.",
                content_type="batch_update",
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
                    identity=f"batch:id:{used_id}",
                )
            )
            session.commit()

        self.write_manifest(
            [
                self.batch(
                    "AWS October Cohort",
                    "The AWS October cohort is accepting learners.",
                ),
                self.batch(
                    "AWS November Cohort",
                    "The AWS November cohort is accepting learners.",
                    "aws-november-2026",
                ),
            ]
        )

        def choose_batch(**kwargs):
            self.assertTrue(kwargs["batch_available"])
            return {
                "eligible": True,
                "reason": "engagement_allowed",
                "content_type": "batch_update",
                "topic": TOPIC,
            }

        with (
            patch.dict(
                os.environ,
                {BATCH_ENV: str(self.manifest_path)},
            ),
            patch(
                "ai.nurture_service.decide_engagement",
                side_effect=choose_batch,
            ),
        ):
            response = self.client.post(
                f"/ai/nurture/{self.lead_id}"
            )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result["ready_to_send"])
        self.assertEqual(
            result["message"],
            "The AWS November cohort is accepting learners.",
        )

        with self.session_factory() as session:
            identities = {
                row.identity
                for row in session.query(NurtureContentIdentity)
                .filter(
                    NurtureContentIdentity.nurture_id
                    == result["nurture_id"]
                )
                .all()
            }

        self.assertIn("batch:id:aws-november-2026", identities)
        self.assertIn(
            next(
                identity
                for identity in get_content_identities(
                    "batch_update",
                    {
                        "batch_id": "aws-november-2026",
                        "message": "The AWS November cohort is accepting learners.",
                    },
                )
                if identity.startswith("text:sha256:")
            ),
            identities,
        )
        self.assertNotIn(f"batch:id:{used_id}", identities)

    def test_nurture_api_returns_service_unavailable_for_invalid_batch_source(self):
        self.manifest_path.write_text("{", encoding="utf-8")

        with (
            patch.dict(
                os.environ,
                {BATCH_ENV: str(self.manifest_path)},
            ),
            patch(
                "ai.nurture_service.decide_engagement",
                return_value={
                    "eligible": True,
                    "reason": "engagement_allowed",
                    "content_type": "batch_update",
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
            "Approved batch source is temporarily unavailable",
        )

    def test_nurture_api_does_not_fallback_when_batch_manifest_is_empty(self):
        self.write_manifest([])

        with (
            patch.dict(
                os.environ,
                {BATCH_ENV: str(self.manifest_path)},
            ),
            patch(
                "ai.nurture_service.decide_engagement",
                return_value={
                    "eligible": True,
                    "reason": "engagement_allowed",
                    "content_type": "batch_update",
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


if __name__ == "__main__":
    unittest.main()
