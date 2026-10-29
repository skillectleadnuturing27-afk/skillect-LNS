from sqlalchemy.orm import Session

import models


def is_hot_lead(lead: models.Lead) -> bool:
    return any(
        (temperature or "").strip().lower() == "hot"
        for temperature in (
            lead.lead_temperature,
            lead.ai_temperature,
        )
    )


def create_hot_lead_alert(
    db: Session,
    lead: models.Lead,
    *,
    was_hot: bool,
    score: int,
    reason: str,
) -> models.LeadAlert | None:
    if was_hot or not is_hot_lead(lead):
        return None

    active_alert = (
        db.query(models.LeadAlert)
        .filter(
            models.LeadAlert.lead_id == lead.id,
            models.LeadAlert.alert_type == "hot_lead",
            models.LeadAlert.status == "active",
        )
        .first()
    )
    if active_alert:
        return None

    qualification = (
        ("Interest", lead.interest),
        ("Budget", str(lead.budget) if lead.budget is not None else None),
        ("Timeline", lead.timeline),
        ("Requirement", lead.requirement),
    )
    qualification_summary = "; ".join(
        f"{label}: {value}"
        for label, value in qualification
        if value
    ) or "No qualification details recorded."

    alert = models.LeadAlert(
        lead_id=lead.id,
        alert_type="hot_lead",
        message=reason,
        reason=reason,
        score=score,
        qualification_summary=qualification_summary,
        status="active",
    )
    db.add(alert)
    return alert
