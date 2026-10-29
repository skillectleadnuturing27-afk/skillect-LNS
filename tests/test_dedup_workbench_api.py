import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from ai.main import app, get_db
from ai.content_dedup import get_content_identities
from ai.main import _require_dedup_test_database
from database import Base
from models import Lead, NurtureContentIdentity


ROOT = Path(__file__).resolve().parents[1]
DEDUP_KINDS = {
    "text": (
        "educational",
        next(iter(get_content_identities(
            "educational",
            "Approved dedup test text candidate beta.",
        ))),
        "Approved dedup test text candidate beta.",
    ),
    "article": (
        "industry_update",
        "article:id:dedup-test-article-beta",
        (
            "Dedup test article beta\n"
            "Approved dedup test article summary beta.\n"
            "https://aws.amazon.com/blogs/aws/dedup-test-beta"
        ),
    ),
    "image": (
        "image",
        "image:id:dedup-test-image-beta",
        "https://images.example.test/dedup/beta.png",
    ),
    "batch": (
        "batch_update",
        "batch:id:dedup-test-batch-beta",
        "Approved dedup test batch update beta.",
    ),
}


class DedupWorkbenchApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.addCleanup(self.engine.dispose)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.previous_override = app.dependency_overrides.get(get_db)

        def override_get_db():
            with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.addCleanup(self._restore_dependency)
        self.database_guard = patch("ai.main._require_dedup_test_database")
        self.database_guard.start()
        self.addCleanup(self.database_guard.stop)

    def _restore_dependency(self):
        if self.previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = self.previous_override

    def _create_lead(self):
        with self.session_factory() as session:
            lead = Lead(
                name="Dedup Workbench Test Lead",
                phone="1234567890",
                email=f"dedup-{uuid4().hex}@example.test",
                source="Test",
                status="new",
                ai_temperature="cold",
                interest="AWS Cloud Engineering",
            )
            session.add(lead)
            session.commit()
            return lead.id

    def test_backend_selects_unused_fixture_and_persists_identities_for_each_type(self):
        fixture_path = ROOT / "ai" / "dedup_test_candidates.json"
        self.assertTrue(fixture_path.is_file())

        for kind, (content_type, expected_identity, expected_message) in (
            DEDUP_KINDS.items()
        ):
            with self.subTest(content_kind=kind):
                lead_id = self._create_lead()
                first = self.client.post(f"/ai/dedup-test/{lead_id}/{kind}")
                self.assertEqual(first.status_code, 200, first.text)
                first_result = first.json()
                self.assertTrue(first_result["ready_to_send"])
                self.assertEqual(first_result["content_type"], content_type)
                self.assertEqual(first_result["message"], {
                    "text": "Approved dedup test text candidate alpha.",
                    "article": (
                        "Dedup test article alpha\n"
                        "Approved dedup test article summary alpha.\n"
                        "https://aws.amazon.com/blogs/aws/dedup-test-alpha"
                    ),
                    "image": "https://images.example.test/dedup/alpha.png",
                    "batch": "Approved dedup test batch update alpha.",
                }[kind])
                self.assertEqual(
                    first_result["deduplication"]["skipped_duplicates"],
                    [],
                )
                self.assertFalse(
                    first_result["deduplication"][
                        "selected_previously_used"
                    ]
                )
                self.assertTrue(first_result["deduplication"]["persisted"])

                second = self.client.post(f"/ai/dedup-test/{lead_id}/{kind}")
                self.assertEqual(second.status_code, 200, second.text)
                second_result = second.json()
                self.assertTrue(second_result["ready_to_send"])
                self.assertEqual(second_result["message"], expected_message)
                self.assertFalse(
                    second_result["deduplication"][
                        "selected_previously_used"
                    ]
                )
                self.assertEqual(
                    len(
                        second_result["deduplication"][
                            "skipped_duplicates"
                        ]
                    ),
                    1,
                )
                if kind == "text":
                    beta_identity = next(iter(get_content_identities(
                        content_type,
                        "Approved dedup test text candidate beta.",
                    )))
                    self.assertIn(
                        beta_identity,
                        second_result["deduplication"]["selected_identities"],
                    )
                else:
                    self.assertIn(
                        expected_identity,
                        second_result["deduplication"][
                            "selected_identities"
                        ],
                    )
                self.assertIn(
                    first_result["deduplication"]["selected_identities"][0],
                    second_result["deduplication"]["skipped_duplicates"][0][
                        "matched_identities"
                    ],
                )

                with self.session_factory() as separate_session:
                    saved = {
                        row.identity
                        for row in separate_session.query(
                            NurtureContentIdentity
                        )
                        .filter(
                            NurtureContentIdentity.lead_id == lead_id,
                        )
                        .all()
                    }
                self.assertTrue(
                    set(
                        first_result["deduplication"][
                            "selected_identities"
                        ]
                    ).issubset(saved)
                )
                self.assertTrue(
                    set(
                        second_result["deduplication"][
                            "selected_identities"
                        ]
                    ).issubset(saved)
                )
                self.assertIn(expected_identity, saved)

    def test_empty_fixture_is_reported_without_claiming_a_saved_selection(self):
        with patch(
            "ai.main._load_dedup_test_candidates",
            return_value=[],
        ):
            response = self.client.post("/ai/dedup-test/1/text")

        self.assertEqual(response.status_code, 503)
        self.assertIn("No approved test candidates", response.json()["detail"])

    def test_test_endpoint_is_disabled_without_explicit_opt_in(self):
        with (
            patch.dict(os.environ, {}, clear=False),
            patch(
                "ai.main._require_dedup_test_database",
                side_effect=_require_dedup_test_database,
            ),
        ):
            os.environ.pop("ENABLE_DEDUP_TEST_ENDPOINT", None)
            response = self.client.post("/ai/dedup-test/1/text")

        self.assertEqual(response.status_code, 404)

    def test_database_guard_accepts_loopback_address_without_cidr_suffix(self):
        database = Mock()
        database.execute.return_value.one.return_value = (
            "lead_db_test",
            "127.0.0.1",
        )

        with patch.dict(os.environ, {"ENABLE_DEDUP_TEST_ENDPOINT": "true"}):
            _require_dedup_test_database(database)

        sql = str(database.execute.call_args.args[0])
        self.assertIn("host(inet_server_addr())", sql)

    def test_database_guard_rejects_remote_database(self):
        database = Mock()
        database.execute.return_value.one.return_value = (
            "lead_db",
            "192.168.1.9",
        )

        with (
            patch.dict(os.environ, {"ENABLE_DEDUP_TEST_ENDPOINT": "true"}),
            self.assertRaises(HTTPException) as raised,
        ):
            _require_dedup_test_database(database)

        self.assertEqual(raised.exception.status_code, 404)
        self.assertIn("restricted", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
