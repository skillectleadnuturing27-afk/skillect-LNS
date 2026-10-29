import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("DB_USERNAME", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


ROOT = Path(__file__).resolve().parents[1]


class DatabaseMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database_path = Path(self.temp_dir.name) / "migration.sqlite"
        self.database_url = f"sqlite:///{self.database_path.as_posix()}"
        self.config = Config(str(ROOT / "alembic.ini"))
        self.config.set_main_option("sqlalchemy.url", self.database_url)
        self.engine = create_engine(self.database_url)
        self.addCleanup(self.engine.dispose)

    def test_fresh_database_migrates_tables_keys_and_indexes(self):
        command.upgrade(self.config, "head")
        command.check(self.config)
        inspector = inspect(self.engine)

        self.assertTrue(
            {
                "leads",
                "lead_activities",
                "conversations",
                "nurture_messages",
                "nurture_content_identities",
                "nurture_image_metadata",
                "lead_alerts",
            }.issubset(set(inspector.get_table_names()))
        )

        identity_indexes = {
            index["name"]: index
            for index in inspector.get_indexes(
                "nurture_content_identities"
            )
        }
        self.assertEqual(
            identity_indexes[
                "uq_nurture_content_identity_lead_identity"
            ]["column_names"],
            ["lead_id", "identity"],
        )
        self.assertTrue(
            identity_indexes[
                "uq_nurture_content_identity_lead_identity"
            ]["unique"]
        )
        self.assertEqual(
            {
                foreign_key["referred_table"]
                for foreign_key in inspector.get_foreign_keys(
                    "nurture_content_identities"
                )
            },
            {"leads", "nurture_messages"},
        )
        self.assertTrue(
            any(
                index["unique"]
                and index["column_names"] == ["nurture_id"]
                for index in inspector.get_indexes("nurture_image_metadata")
            )
        )
        alert_columns = {
            column["name"]: column
            for column in inspector.get_columns("lead_alerts")
        }
        self.assertTrue(
            {
                "reason",
                "score",
                "qualification_summary",
            }.issubset(alert_columns)
        )
        self.assertFalse(alert_columns["reason"]["nullable"])

    def test_hot_alert_migration_preserves_existing_alerts_and_normalizes_status(self):
        command.upgrade(self.config, "0001_initial_schema")
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO leads (
                        name, phone, email, source, status,
                        lead_score, lead_temperature, ai_score, ai_temperature,
                        created_at, updated_at
                    ) VALUES (
                        'Existing Alert Lead', '1234567890',
                        'existing-alert@example.com', 'Test', 'new',
                        10, 'cold', 0, 'cold',
                        '2026-10-27 00:00:00', '2026-10-27 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO lead_alerts (
                        lead_id, alert_type, message, status, created_at
                    ) VALUES
                    (
                        1, 'hot_lead', 'Legacy pending alert', 'pending',
                        '2026-10-27 00:00:00'
                    ),
                    (
                        1, 'hot_lead', 'Legacy handled alert', 'handled',
                        '2026-10-27 00:00:00'
                    )
                    """
                )
            )

        command.upgrade(self.config, "head")
        with self.engine.connect() as connection:
            migrated = connection.execute(
                text(
                    """
                    SELECT message, reason, score,
                           qualification_summary, status
                    FROM lead_alerts
                    ORDER BY id
                    """
                )
            ).all()

        self.assertEqual(len(migrated), 2)
        self.assertEqual(migrated[0], (
            "Legacy pending alert",
            "Legacy pending alert",
            0,
            "",
            "active",
        ))
        self.assertEqual(migrated[1], (
            "Legacy handled alert",
            "Legacy handled alert",
            0,
            "",
            "resolved",
        ))

    def test_upgrade_refuses_duplicates_without_deleting_existing_rows(self):
        command.upgrade(self.config, "0001_initial_schema")

        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE nurture_content_identities (
                        id INTEGER PRIMARY KEY,
                        lead_id INTEGER NOT NULL,
                        nurture_id INTEGER NOT NULL,
                        identity TEXT NOT NULL,
                        FOREIGN KEY (lead_id) REFERENCES leads(id)
                            ON DELETE CASCADE,
                        FOREIGN KEY (nurture_id) REFERENCES nurture_messages(id)
                            ON DELETE CASCADE
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO nurture_content_identities
                        (id, lead_id, nurture_id, identity)
                    VALUES
                        (1, 9, 21, 'article:id:legacy'),
                        (2, 9, 22, 'article:id:legacy'),
                        (3, 9, 23, 'batch:id:legacy')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE nurture_image_metadata (
                        id INTEGER PRIMARY KEY,
                        nurture_id INTEGER NOT NULL,
                        image_id VARCHAR(255),
                        canonical_url TEXT,
                        topic VARCHAR(100) NOT NULL,
                        source TEXT NOT NULL,
                        approved BOOLEAN NOT NULL,
                        content_hash VARCHAR(64),
                        FOREIGN KEY (nurture_id) REFERENCES nurture_messages(id)
                            ON DELETE CASCADE
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO nurture_image_metadata
                        (id, nurture_id, topic, source, approved)
                    VALUES
                        (1, 21, 'AWS', 'legacy catalog', 1),
                        (2, 21, 'AWS', 'duplicate legacy row', 1)
                    """
                )
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "duplicate values.*no rows were deleted",
        ):
            command.upgrade(self.config, "head")

        with self.engine.connect() as connection:
            identity_rows = connection.execute(
                text(
                    """
                    SELECT lead_id, identity
                    FROM nurture_content_identities
                    ORDER BY id
                    """
                )
            ).all()
            image_rows = connection.execute(
                text(
                    """
                    SELECT nurture_id, source
                    FROM nurture_image_metadata
                    ORDER BY id
                    """
                )
            ).all()

        self.assertEqual(
            identity_rows,
            [
                (9, "article:id:legacy"),
                (9, "article:id:legacy"),
                (9, "batch:id:legacy"),
            ],
        )
        self.assertEqual(
            image_rows,
            [(21, "legacy catalog"), (21, "duplicate legacy row")],
        )
        self.assertEqual(
            inspect(self.engine).get_indexes("nurture_content_identities"),
            [],
        )

    def test_upgrade_existing_identity_tables_preserves_rows_and_adds_keys(self):
        command.upgrade(self.config, "0001_initial_schema")
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE nurture_content_identities (
                        id INTEGER PRIMARY KEY,
                        lead_id INTEGER NOT NULL,
                        nurture_id INTEGER NOT NULL,
                        identity TEXT NOT NULL,
                        FOREIGN KEY (lead_id) REFERENCES leads(id)
                            ON DELETE CASCADE,
                        FOREIGN KEY (nurture_id) REFERENCES nurture_messages(id)
                            ON DELETE CASCADE
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO nurture_content_identities
                        (id, lead_id, nurture_id, identity)
                    VALUES (1, 9, 21, 'article:id:legacy')
                    """
                )
            )

        command.upgrade(self.config, "head")
        with self.engine.connect() as connection:
            identity_rows = connection.execute(
                text(
                    """
                    SELECT lead_id, nurture_id, identity
                    FROM nurture_content_identities
                    """
                )
            ).all()

        self.assertEqual(
            identity_rows,
            [(9, 21, "article:id:legacy")],
        )
        self.assertTrue(
            any(
                index["unique"]
                and index["column_names"] == ["lead_id", "identity"]
                for index in inspect(self.engine).get_indexes(
                    "nurture_content_identities"
                )
            )
        )
        self.assertEqual(
            {
                foreign_key["referred_table"]
                for foreign_key in inspect(self.engine).get_foreign_keys(
                    "nurture_content_identities"
                )
            },
            {"leads", "nurture_messages"},
        )
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO nurture_content_identities
                        (lead_id, nurture_id, identity)
                    VALUES (9, 21, 'article:id:guard')
                    """
                )
            )
        with self.assertRaises(IntegrityError):
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO nurture_content_identities
                            (lead_id, nurture_id, identity)
                        VALUES (9, 22, 'article:id:guard')
                        """
                    )
                )


if __name__ == "__main__":
    unittest.main()
