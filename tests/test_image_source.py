import importlib
import json
import os
import tempfile
import unittest
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DB_USERNAME", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ai.content_dedup import get_content_identities
from ai.image_library import (
    ApprovedImageSourceError,
    get_approved_images,
    get_image_content,
)
from ai.nurture_service import get_current_time, prepare_nurture_for_lead
from database import Base
from models import (
    Lead,
    NurtureContentIdentity,
    NurtureImageMetadata,
    NurtureMessage,
)


TOPIC = "AWS Cloud Engineering"
IMAGE_ENV = "APPROVED_IMAGE_MANIFEST"


class ImageSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.manifest = self.root / "approved-images.json"

    def write_manifest(self, entries):
        self.manifest.write_text(
            json.dumps(entries),
            encoding="utf-8",
        )
        return str(self.manifest)

    def make_image(self, **overrides):
        entry = {
            "image_id": "aws-infographic-1",
            "image_url": "https://images.example.test/aws/cloud.png",
            "topic": TOPIC,
            "source": "Approved internal image catalog",
            "approved": True,
        }
        entry.update(overrides)
        return entry

    def test_manifest_validates_required_metadata_and_approval(self):
        manifest_path = self.write_manifest(
            [
                self.make_image(),
                self.make_image(
                    image_id="unapproved",
                    approved=False,
                ),
            ]
        )

        with patch.dict(os.environ, {IMAGE_ENV: manifest_path}):
            images = get_approved_images(TOPIC)

        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["image_id"], "aws-infographic-1")
        self.assertEqual(images[0]["topic"], TOPIC)
        self.assertEqual(
            images[0]["canonical_url"],
            "https://images.example.test/aws/cloud.png",
        )
        self.assertTrue(images[0]["approved"])

    def test_rejects_approved_entries_missing_identity_or_source(self):
        bad_entries = [
            self.make_image(image_id=None, image_url=None),
            self.make_image(source=" "),
            self.make_image(image_url="file:///etc/passwd"),
        ]

        for entry in bad_entries:
            with self.subTest(entry=entry):
                manifest_path = self.write_manifest([entry])
                with patch.dict(os.environ, {IMAGE_ENV: manifest_path}):
                    with self.assertRaises(ApprovedImageSourceError):
                        get_approved_images(TOPIC)

    def test_manifest_can_hash_local_image_bytes_and_checks_supplied_hash(self):
        image_bytes = b"approved image fixture bytes"
        (self.root / "cloud-image.bin").write_bytes(image_bytes)
        content_hash = sha256(image_bytes).hexdigest()
        manifest_path = self.write_manifest(
            [
                self.make_image(
                    image_url=None,
                    file_path="cloud-image.bin",
                )
            ]
        )

        with patch.dict(os.environ, {IMAGE_ENV: manifest_path}):
            image = get_approved_images(TOPIC)[0]

        self.assertEqual(image["content_hash"], content_hash)

        manifest_path = self.write_manifest(
            [
                self.make_image(
                    image_url=None,
                    file_path="cloud-image.bin",
                    content_hash="0" * 64,
                )
            ]
        )
        with patch.dict(os.environ, {IMAGE_ENV: manifest_path}):
            with self.assertRaises(ApprovedImageSourceError):
                get_approved_images(TOPIC)

    def test_rejects_invalid_hash_and_manifest_path_escape(self):
        manifest_path = self.write_manifest(
            [self.make_image(content_hash="not-a-sha256")]
        )
        with patch.dict(os.environ, {IMAGE_ENV: manifest_path}):
            with self.assertRaises(ApprovedImageSourceError):
                get_approved_images(TOPIC)

        (self.root / "valid.bin").write_bytes(b"image")
        manifest_path = self.write_manifest(
            [
                self.make_image(
                    file_path="valid.bin",
                    content_hash=123,
                )
            ]
        )
        with patch.dict(os.environ, {IMAGE_ENV: manifest_path}):
            with self.assertRaises(ApprovedImageSourceError):
                get_approved_images(TOPIC)

        manifest_path = self.write_manifest(
            [
                self.make_image(
                    image_url=None,
                    file_path="../outside.bin",
                )
            ]
        )
        with patch.dict(os.environ, {IMAGE_ENV: manifest_path}):
            with self.assertRaises(ApprovedImageSourceError):
                get_approved_images(TOPIC)

    def test_identity_prevents_duplicate_url_and_hash_selection(self):
        manifest_path = self.write_manifest(
            [
                self.make_image(),
                self.make_image(
                    image_id="aws-infographic-2",
                    image_url="https://images.example.test/aws/cloud-alt.png",
                ),
            ]
        )
        previous = get_content_identities(
            "image",
            {"image_url": "http://www.images.example.test/aws/cloud.png"},
        )

        with patch.dict(os.environ, {IMAGE_ENV: manifest_path}):
            selected = get_image_content(
                TOPIC,
                previously_used_identities=previous,
            )

        self.assertTrue(selected["ready"])
        self.assertEqual(selected["image_id"], "aws-infographic-2")

        duplicate_bytes = b"same binary content"
        (self.root / "image-a.bin").write_bytes(duplicate_bytes)
        (self.root / "image-b.bin").write_bytes(duplicate_bytes)
        manifest_path = self.write_manifest(
            [
                self.make_image(
                    image_id="hash-a",
                    image_url=None,
                    file_path="image-a.bin",
                ),
                self.make_image(
                    image_id="hash-b",
                    image_url=None,
                    file_path="image-b.bin",
                ),
            ]
        )
        used_hash = {
            f"image:sha256:{sha256(duplicate_bytes).hexdigest()}"
        }
        with patch.dict(os.environ, {IMAGE_ENV: manifest_path}):
            result = get_image_content(
                TOPIC,
                previously_used_identities=used_hash,
            )
        self.assertFalse(result["ready"])
        self.assertEqual(result["reason"], "no_unused_approved_image")

    def test_missing_or_invalid_manifest_is_reported(self):
        with patch.dict(
            os.environ,
            {IMAGE_ENV: str(self.root / "missing.json")},
        ):
            with self.assertRaises(ApprovedImageSourceError):
                get_approved_images(TOPIC)

        self.manifest.write_text("{", encoding="utf-8")
        with patch.dict(os.environ, {IMAGE_ENV: str(self.manifest)}):
            with self.assertRaises(ApprovedImageSourceError):
                get_approved_images(TOPIC)


class ImageNurtureApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(Base.metadata, "create_all"):
            cls.api = importlib.import_module("ai.main")

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.manifest_path = self.root / "approved-images.json"
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
                name="Image Test Lead",
                phone="1234567890",
                email="image-test@example.com",
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

    def image_entry(self, image_id, url, source="Approved test catalog"):
        return {
            "image_id": image_id,
            "image_url": url,
            "topic": TOPIC,
            "source": source,
            "approved": True,
        }

    def test_nurture_api_selects_and_persists_approved_image_metadata(self):
        image_bytes = b"image fixture bytes for persistence"
        (self.root / "api-image.bin").write_bytes(image_bytes)
        self.write_manifest(
            [
                {
                    **self.image_entry(
                        "aws-image-1",
                        "https://images.example.test/aws/one.png",
                    ),
                    "file_path": "api-image.bin",
                }
            ]
        )

        with (
            patch.dict(
                os.environ,
                {IMAGE_ENV: str(self.manifest_path)},
            ),
            patch(
                "ai.nurture_service.decide_engagement",
                return_value={
                    "eligible": True,
                    "reason": "engagement_allowed",
                    "content_type": "image",
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
        self.assertEqual(
            result["message"],
            "https://images.example.test/aws/one.png",
        )
        self.assertEqual(result["image"]["image_id"], "aws-image-1")

        with self.session_factory() as session:
            metadata = (
                session.query(NurtureImageMetadata)
                .filter(
                    NurtureImageMetadata.nurture_id
                    == result["nurture_id"]
                )
                .one()
            )
            identities = {
                row.identity
                for row in session.query(NurtureContentIdentity)
                .filter(
                    NurtureContentIdentity.nurture_id
                    == result["nurture_id"]
                )
                .all()
            }

        self.assertEqual(metadata.image_id, "aws-image-1")
        self.assertEqual(
            metadata.canonical_url,
            "https://images.example.test/aws/one.png",
        )
        self.assertEqual(metadata.topic, TOPIC)
        self.assertEqual(metadata.source, "Approved test catalog")
        self.assertTrue(metadata.approved)
        self.assertEqual(metadata.content_hash, sha256(image_bytes).hexdigest())
        self.assertIn(
            "image:url:https://images.example.test/aws/one.png",
            identities,
        )
        self.assertIn("image:id:aws-image-1", identities)

    def test_nurture_api_skips_previously_used_image(self):
        self.write_manifest(
            [
                self.image_entry(
                    "aws-image-used",
                    "https://images.example.test/aws/used.png",
                ),
                self.image_entry(
                    "aws-image-new",
                    "https://images.example.test/aws/new.png",
                ),
            ]
        )
        now = get_current_time()
        with self.session_factory() as session:
            previous = NurtureMessage(
                lead_id=self.lead_id,
                message="https://images.example.test/aws/used.png",
                content_type="image",
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
                    identity="image:id:aws-image-used",
                )
            )
            session.commit()

            with (
                patch.dict(
                    os.environ,
                    {IMAGE_ENV: str(self.manifest_path)},
                ),
                patch(
                    "ai.nurture_service.decide_engagement",
                    return_value={
                        "eligible": True,
                        "reason": "engagement_allowed",
                        "content_type": "image",
                        "topic": TOPIC,
                    },
                ),
            ):
                result = prepare_nurture_for_lead(
                    session,
                    self.lead_id,
                    current_time=now,
                )

        self.assertTrue(result["ready_to_send"])
        self.assertEqual(
            result["message"],
            "https://images.example.test/aws/new.png",
        )
        self.assertEqual(
            result["image"]["image_id"],
            "aws-image-new",
        )

    def test_nurture_api_returns_service_unavailable_for_invalid_manifest(self):
        self.manifest_path.write_text("{", encoding="utf-8")

        with (
            patch.dict(
                os.environ,
                {IMAGE_ENV: str(self.manifest_path)},
            ),
            patch(
                "ai.nurture_service.decide_engagement",
                return_value={
                    "eligible": True,
                    "reason": "engagement_allowed",
                    "content_type": "image",
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
            "Approved image source is temporarily unavailable",
        )

    def test_nurture_api_does_not_fallback_when_image_manifest_is_empty(self):
        self.write_manifest([])

        with (
            patch.dict(
                os.environ,
                {IMAGE_ENV: str(self.manifest_path)},
            ),
            patch(
                "ai.nurture_service.decide_engagement",
                return_value={
                    "eligible": True,
                    "reason": "engagement_allowed",
                    "content_type": "image",
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
        self.assertEqual(result["reason"], "approved_image_not_found")
        self.assertIsNone(result.get("message"))
