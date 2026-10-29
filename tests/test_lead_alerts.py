import os
import unittest
from uuid import uuid4
from unittest.mock import patch
from types import SimpleNamespace

os.environ.setdefault("DB_USERNAME", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from main import app, get_db
from models import Lead, LeadAlert


class LeadAlertApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.previous_override = app.dependency_overrides.get(get_db)

        def override_get_db():
            with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.addCleanup(self._restore_dependency)
        self.addCleanup(self.engine.dispose)

    def _restore_dependency(self):
        if self.previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = self.previous_override

    def _create_lead(self):
        response = self.client.post(
            "/leads",
            json={
                "name": "HOT Alert Test",
                "phone": "1234567890",
                "email": f"hot-alert-{uuid4().hex}@example.com",
                "source": "Website",
                "status": "new",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        lead_id = response.json()["id"]
        with self.session_factory() as session:
            lead = session.query(Lead).filter(Lead.id == lead_id).one()
            lead.interest = "AWS Cloud Engineering"
            lead.budget = 5000
            lead.timeline = "This month"
            lead.requirement = "Career change"
            session.commit()
        return lead_id

    def _make_lead_hot(self, lead_id):
        response = self.client.patch(
            f"/leads/{lead_id}/status",
            json={"status": "qualified"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["lead_temperature"], "hot")

    def test_hot_transition_creates_one_persistent_alert_and_api_updates_status(self):
        lead_id = self._create_lead()
        with self.session_factory() as session:
            self.assertEqual(session.query(LeadAlert).count(), 0)

        self._make_lead_hot(lead_id)
        with self.session_factory() as session:
            alerts = session.query(LeadAlert).filter(
                LeadAlert.lead_id == lead_id
            ).all()
            self.assertEqual(len(alerts), 1)
            alert_id = alerts[0].id
            self.assertEqual(alerts[0].status, "active")
            self.assertEqual(alerts[0].alert_type, "hot_lead")
            self.assertEqual(alerts[0].score, 70)
            self.assertIn("CRM score of 70", alerts[0].reason)
            self.assertEqual(alerts[0].reason, alerts[0].message)
            self.assertIn("AWS Cloud Engineering", alerts[0].qualification_summary)
            self.assertIn("Budget: 5000", alerts[0].qualification_summary)
            self.assertIsNotNone(alerts[0].created_at)

        listed = self.client.get("/alerts")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(listed.json()[0]["lead"]["id"], lead_id)
        self.assertEqual(listed.json()[0]["lead"]["name"], "HOT Alert Test")

        details = self.client.get(f"/alerts/{alert_id}")
        self.assertEqual(details.status_code, 200, details.text)
        self.assertEqual(details.json()["id"], alert_id)
        self.assertEqual(details.json()["qualification_summary"], listed.json()[0]["qualification_summary"])

        acknowledged = self.client.patch(
            f"/alerts/{alert_id}/status",
            json={"status": "acknowledged"},
        )
        self.assertEqual(acknowledged.status_code, 200, acknowledged.text)
        self.assertEqual(acknowledged.json()["status"], "acknowledged")
        self.assertEqual(
            self.client.get("/alerts?status=active").json(),
            [],
        )

        self._make_lead_hot(lead_id)
        with self.session_factory() as session:
            self.assertEqual(
                session.query(LeadAlert)
                .filter(LeadAlert.lead_id == lead_id)
                .count(),
                1,
            )

        resolved = self.client.patch(
            f"/alerts/{alert_id}/status",
            json={"status": "resolved"},
        )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(resolved.json()["status"], "resolved")

    def test_new_hot_transition_after_cooling_creates_new_alert(self):
        lead_id = self._create_lead()
        self._make_lead_hot(lead_id)
        first = self.client.get("/alerts").json()[0]
        self.client.patch(
            f"/alerts/{first['id']}/status",
            json={"status": "acknowledged"},
        )

        cooled = self.client.patch(
            f"/leads/{lead_id}/status",
            json={"status": "lost"},
        )
        self.assertEqual(cooled.status_code, 200, cooled.text)
        self.assertEqual(cooled.json()["lead_temperature"], "cold")

        hot_again = self.client.patch(
            f"/leads/{lead_id}/status",
            json={"status": "qualified"},
        )
        self.assertEqual(hot_again.status_code, 200, hot_again.text)
        self.assertEqual(hot_again.json()["lead_temperature"], "hot")

        alerts = self.client.get("/alerts").json()
        self.assertEqual(len(alerts), 2)
        self.assertEqual(
            {alert["status"] for alert in alerts},
            {"active", "acknowledged"},
        )
        reactivated = self.client.patch(
            f"/alerts/{first['id']}/status",
            json={"status": "active"},
        )
        self.assertEqual(reactivated.status_code, 409)

    def test_alert_details_and_status_validation_return_not_found_or_unprocessable(self):
        self.assertEqual(self.client.get("/alerts/999").status_code, 404)
        missing_status = self.client.patch(
            "/alerts/999/status",
            json={"status": "handled"},
        )
        self.assertEqual(missing_status.status_code, 422)

    def test_alert_status_database_failure_returns_error_without_mutating_record(self):
        lead_id = self._create_lead()
        self._make_lead_hot(lead_id)
        alert_id = self.client.get("/alerts").json()[0]["id"]

        with patch.object(
            Session,
            "commit",
            side_effect=OperationalError(
                "UPDATE",
                {},
                RuntimeError("isolated test database failure"),
            ),
        ):
            response = self.client.patch(
                f"/alerts/{alert_id}/status",
                json={"status": "acknowledged"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json()["detail"],
            "Unable to update alert status",
        )
        with self.session_factory() as session:
            alert = session.query(LeadAlert).filter(
                LeadAlert.id == alert_id
            ).one()
            self.assertEqual(alert.status, "active")

    def test_ai_temperature_transition_creates_only_one_alert_while_hot(self):
        lead_id = self._create_lead()
        from ai import main as ai_api

        previous_override = ai_api.app.dependency_overrides.get(ai_api.get_db)

        def override_ai_db():
            with self.session_factory() as session:
                execute = session.execute

                def execute_for_test(statement, *args, **kwargs):
                    sql = str(statement)
                    if "current_database()" in sql:
                        return SimpleNamespace(
                            fetchone=lambda: (
                                "isolated_test",
                                "public",
                                "test_user",
                                "127.0.0.1",
                                5432,
                            )
                        )
                    if "SELECT id FROM public.leads" in sql:
                        return SimpleNamespace(
                            scalars=lambda: SimpleNamespace(
                                all=lambda: [lead_id]
                            )
                        )
                    return execute(statement, *args, **kwargs)

                with patch.object(
                    session,
                    "execute",
                    side_effect=execute_for_test,
                ):
                    yield session

        ai_api.app.dependency_overrides[ai_api.get_db] = override_ai_db
        try:
            with TestClient(ai_api.app) as ai_client:
                with (
                    patch(
                        "ai.main.qualify_lead",
                        return_value={
                            "interest": "AWS Cloud Engineering",
                            "budget": 5000,
                            "timeline": "This month",
                            "requirement": "Career change",
                        },
                    ),
                    patch(
                        "ai.main.merge_qualification",
                        return_value={
                            "interest": "AWS Cloud Engineering",
                            "budget": 5000,
                            "timeline": "This month",
                            "requirement": "Career change",
                        },
                    ),
                    patch(
                        "ai.main.calculate_lead_score",
                        return_value={"score": 85, "status": "hot"},
                    ),
                    patch("ai.main.route_message", return_value="Test response"),
                ):
                    first = ai_client.post(
                        "/ai/chat",
                        json={
                            "lead_id": lead_id,
                            "message": "I am ready to enroll.",
                        },
                    )
                    second = ai_client.post(
                        "/ai/chat",
                        json={
                            "lead_id": lead_id,
                            "message": "I have one more question.",
                        },
                    )
        finally:
            if previous_override is None:
                ai_api.app.dependency_overrides.pop(ai_api.get_db, None)
            else:
                ai_api.app.dependency_overrides[ai_api.get_db] = previous_override

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        with self.session_factory() as session:
            lead = session.query(Lead).filter(Lead.id == lead_id).one()
            alerts = session.query(LeadAlert).filter(
                LeadAlert.lead_id == lead_id
            ).all()
            self.assertEqual(lead.ai_temperature, "hot")
            self.assertEqual(len(alerts), 1)
            self.assertEqual(alerts[0].score, 85)
            self.assertIn("AI qualification score of 85", alerts[0].reason)


if __name__ == "__main__":
    unittest.main()
