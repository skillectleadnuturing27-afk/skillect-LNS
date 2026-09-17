def calculate_lead_score(qualification: dict) -> dict:
    score = 0

    # Interest identified
    if qualification.get("interest"):
        score += 20

    # Budget identified
    if qualification.get("budget"):
        score += 30

    # Timeline
    timeline = qualification.get("timeline")

    if timeline == "Immediately":
        score += 30
    elif timeline == "This month":
        score += 25
    elif timeline == "Next month":
        score += 20

    # Requirement identified
    if qualification.get("requirement"):
        score += 20

    # Lead status
    if score >= 80:
        status = "HOT"
    elif score >= 50:
        status = "WARM"
    else:
        status = "COLD"

    return {
        "score": score,
        "status": status
    }