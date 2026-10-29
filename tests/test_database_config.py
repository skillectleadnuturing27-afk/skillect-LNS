import unittest

from sqlalchemy.engine import make_url

from database import build_database_url


class DatabaseConfigTests(unittest.TestCase):
    def test_component_settings_build_escaped_postgresql_url(self):
        url = build_database_url(
            {
                "DB_USERNAME": "local-user",
                "DB_PASSWORD": "secret/with@symbols",
                "DB_NAME": "lead_db",
                "DB_PORT": "5433",
            }
        )

        self.assertEqual(url.drivername, "postgresql+psycopg2")
        self.assertEqual(url.host, "localhost")
        self.assertEqual(url.port, 5433)
        self.assertEqual(url.database, "lead_db")
        parsed_url = make_url(url.render_as_string(hide_password=False))
        self.assertEqual(parsed_url.username, "local-user")
        self.assertEqual(parsed_url.password, "secret/with@symbols")

    def test_database_url_takes_precedence_over_component_settings(self):
        url = build_database_url(
            {
                "DATABASE_URL": (
                    "postgresql+psycopg2://env-user:env-password"
                    "@db.example.test:5432/production"
                ),
                "DB_USERNAME": "stale-user",
                "DB_PASSWORD": "stale-password",
                "DB_NAME": "stale-db",
                "DB_HOST": "192.0.2.10",
            }
        )

        self.assertEqual(url.username, "env-user")
        self.assertEqual(url.host, "db.example.test")
        self.assertEqual(url.database, "production")

    def test_missing_required_settings_are_reported_without_values(self):
        with self.assertRaisesRegex(
            ValueError,
            "DB_USERNAME, DB_PASSWORD, DB_NAME",
        ):
            build_database_url({})

    def test_invalid_port_is_reported(self):
        with self.assertRaisesRegex(ValueError, "DB_PORT must be an integer"):
            build_database_url(
                {
                    "DB_USERNAME": "user",
                    "DB_PASSWORD": "password",
                    "DB_NAME": "database",
                    "DB_PORT": "invalid",
                }
            )


if __name__ == "__main__":
    unittest.main()
