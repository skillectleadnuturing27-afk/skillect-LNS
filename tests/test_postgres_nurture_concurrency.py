import ipaddress
import os
import secrets
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

os.environ.setdefault("DB_USERNAME", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")

from fastapi.testclient import TestClient
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

from models import Lead, NurtureContentIdentity, NurtureMessage
from ai.nurture_service import get_current_time


POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
ROOT = Path(__file__).resolve().parents[1]


def _validate_disposable_database_url(database_url):
    parsed_url = make_url(database_url)
    if not parsed_url.database or "test" not in parsed_url.database.lower():
        raise RuntimeError(
            "POSTGRES_TEST_DATABASE_URL database name must contain 'test'"
        )

    host = (parsed_url.host or "").lower()
    if host == "localhost":
        return parsed_url

    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback:
        raise RuntimeError(
            "POSTGRES_TEST_DATABASE_URL must use localhost or a loopback IP "
            "to prevent tests from modifying a remote/shared database"
        )

    return parsed_url


def _alembic_database_url(parsed_url, schema_name):
    schema_url = parsed_url.update_query_dict(
        {"options": [f"-csearch_path={schema_name}"]}
    )
    return schema_url.render_as_string(hide_password=False).replace(
        "%",
        "%%",
    )


class PostgresTestDatabaseSafetyTests(unittest.TestCase):
    def test_accepts_loopback_database_with_test_name(self):
        parsed_url = _validate_disposable_database_url(
            "postgresql+psycopg2://127.0.0.1:5432/skillect_test"
        )

        self.assertEqual(parsed_url.database, "skillect_test")

    def test_rejects_remote_database_even_when_name_contains_test(self):
        with self.assertRaisesRegex(RuntimeError, "loopback"):
            _validate_disposable_database_url(
                "postgresql+psycopg2://db.example.test:5432/skillect_test"
            )

    def test_rejects_database_without_test_in_name(self):
        with self.assertRaisesRegex(RuntimeError, "must contain 'test'"):
            _validate_disposable_database_url(
                "postgresql+psycopg2://localhost:5432/lead_db"
            )

    def test_alembic_url_keeps_password_and_escapes_config_percent(self):
        password = f"{secrets.token_urlsafe(16)}%"
        parsed_url = URL.create(
            "postgresql+psycopg2",
            username="test_user",
            password=password,
            host="127.0.0.1",
            port=5432,
            database="skillect_test",
        )

        alembic_url = _alembic_database_url(parsed_url, "nurture_test_schema")
        config = Config()
        config.set_main_option("sqlalchemy.url", alembic_url)
        restored_url = make_url(config.get_main_option("sqlalchemy.url"))

        self.assertEqual(restored_url.password, password)
        self.assertIn(
            "-csearch_path=nurture_test_schema",
            restored_url.query["options"],
        )


@unittest.skipUnless(
    POSTGRES_TEST_URL,
    "Set POSTGRES_TEST_DATABASE_URL to a disposable PostgreSQL database",
)
class PostgresNurtureConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parsed_url = _validate_disposable_database_url(POSTGRES_TEST_URL)
        if not parsed_url.drivername.startswith("postgresql"):
            raise RuntimeError(
                "POSTGRES_TEST_DATABASE_URL must use PostgreSQL"
            )

        cls.admin_engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)
        cls.schema_name = f"nurture_test_{uuid4().hex}"
        with cls.admin_engine.begin() as connection:
            identity = connection.execute(
                text(
                    """
                    SELECT current_database(), inet_server_addr()::text
                    """
                )
            ).one()
            if identity[0] != parsed_url.database:
                raise RuntimeError(
                    "Connected database does not match "
                    "POSTGRES_TEST_DATABASE_URL"
                )
            try:
                is_loopback_server = ipaddress.ip_address(identity[1]).is_loopback
            except (TypeError, ValueError):
                is_loopback_server = False
            if not is_loopback_server:
                raise RuntimeError(
                    "Connected PostgreSQL server is not on loopback; "
                    "refusing to create test schema"
                )
            connection.execute(text(f'CREATE SCHEMA "{cls.schema_name}"'))

        alembic_config = Config(str(ROOT / "alembic.ini"))
        alembic_config.set_main_option(
            "sqlalchemy.url",
            _alembic_database_url(parsed_url, cls.schema_name),
        )
        command.upgrade(alembic_config, "head")

        cls.engine = create_engine(
            POSTGRES_TEST_URL,
            pool_pre_ping=True,
            connect_args={
                "options": f"-csearch_path={cls.schema_name}",
            },
        )
        cls.session_factory = sessionmaker(
            bind=cls.engine,
            expire_on_commit=False,
        )

        from ai import main as ai_api

        cls.api = ai_api

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        with cls.admin_engine.begin() as connection:
            connection.execute(
                text(f'DROP SCHEMA "{cls.schema_name}" CASCADE')
            )
        cls.admin_engine.dispose()

    def setUp(self):
        self.email = f"concurrent-{uuid4().hex}@example.test"
        with self.session_factory() as session:
            lead = Lead(
                name="Concurrency Test Lead",
                phone="1234567890",
                email=self.email,
                source="Test",
                status="new",
                ai_temperature="cold",
                interest="AWS Cloud Engineering",
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

    def test_concurrent_api_requests_generate_only_one_same_day_nurture(self):
        barrier = threading.Barrier(2)

        def post_nurture():
            barrier.wait(timeout=10)
            with TestClient(self.api.app) as client:
                return client.post(f"/ai/nurture/{self.lead_id}")

        with patch(
            "ai.nurture_service.decide_engagement",
            return_value={
                "eligible": True,
                "reason": "engagement_allowed",
                "content_type": "educational",
                "topic": "AWS Cloud Engineering",
            },
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = list(executor.map(lambda _: post_nurture(), range(2)))

        self.assertEqual([response.status_code for response in responses], [200, 200])
        payloads = [response.json() for response in responses]
        self.assertEqual(
            sum(bool(payload.get("ready_to_send")) for payload in payloads),
            1,
        )
        self.assertEqual(
            sum(
                payload.get("reason") == "already_generated_today"
                for payload in payloads
            ),
            1,
        )

        with self.session_factory() as session:
            nurtures = (
                session.query(NurtureMessage)
                .filter(NurtureMessage.lead_id == self.lead_id)
                .all()
            )
            identities = (
                session.query(NurtureContentIdentity)
                .filter(NurtureContentIdentity.lead_id == self.lead_id)
                .all()
            )

        self.assertEqual(len(nurtures), 1)
        self.assertTrue(identities)

    def test_identity_records_persist_across_postgresql_sessions(self):
        with self.session_factory() as session:
            lead = Lead(
                name="Persistence Test Lead",
                phone="1234567890",
                email=f"persistence-{uuid4().hex}@example.test",
                source="Test",
                status="new",
                ai_temperature="cold",
            )
            session.add(lead)
            session.flush()
            nurture = NurtureMessage(
                lead_id=lead.id,
                message="Approved source content",
                content_type="industry_update",
                topic="AWS Cloud Engineering",
                stage=1,
                status="generated",
            )
            session.add(nurture)
            session.flush()
            session.add_all(
                [
                    NurtureContentIdentity(
                        lead_id=lead.id,
                        nurture_id=nurture.id,
                        identity=identity,
                    )
                    for identity in (
                        "article:id:postgres-article",
                        "image:id:postgres-image",
                        "batch:id:postgres-batch",
                    )
                ]
            )
            lead_id = lead.id
            session.commit()

        with self.session_factory() as verification_session:
            saved = {
                row.identity
                for row in verification_session.query(NurtureContentIdentity)
                .filter(NurtureContentIdentity.lead_id == lead_id)
                .all()
            }

        self.assertEqual(
            saved,
            {
                "article:id:postgres-article",
                "image:id:postgres-image",
                "batch:id:postgres-batch",
            },
        )


if __name__ == "__main__":
    unittest.main()
