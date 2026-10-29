import re


def calculate_lead_score(qualification: dict) -> dict:

    score = 0


    # =========================
    # INTEREST
    # =========================
    # If the lead has clearly identified
    # what they are interested in:
    #
    # AWS / Azure / DevOps /
    # Python / Cloud Computing
    #
    # +20 points

    if qualification.get("interest"):
        score += 20


    # =========================
    # BUDGET
    # =========================
    # If the lead has provided their budget,
    # +30 points.

    if qualification.get("budget"):
        score += 30


    # =========================
    # TIMELINE
    # =========================

    timeline = qualification.get("timeline")


    # -------------------------
    # IMMEDIATE
    # -------------------------

    if timeline == "Immediately":

        score += 30


    # -------------------------
    # THIS WEEK
    # -------------------------

    elif timeline == "This week":

        score += 30


    # -------------------------
    # NEXT WEEK
    # -------------------------

    elif timeline == "Next week":

        score += 30


    # -------------------------
    # THIS MONTH
    # -------------------------

    elif timeline == "This month":

        score += 25


    # -------------------------
    # NEXT MONTH
    # -------------------------

    elif timeline == "Next month":

        score += 20


    # -------------------------
    # WITHIN N DAYS
    # -------------------------

    elif timeline:

        days_match = re.fullmatch(
            r"Within (\d+) days?",
            timeline
        )

        if days_match:

            days = int(
                days_match.group(1)
            )

            if days <= 7:
                score += 30

            elif days <= 14:
                score += 25

            elif days <= 30:
                score += 20


        # -------------------------
        # WITHIN N WEEKS
        # -------------------------

        else:

            weeks_match = re.fullmatch(
                r"Within (\d+) weeks?",
                timeline
            )

            if weeks_match:

                weeks = int(
                    weeks_match.group(1)
                )

                if weeks <= 1:
                    score += 30

                elif weeks <= 2:
                    score += 25

                elif weeks <= 4:
                    score += 20


    # =========================
    # REQUIREMENT
    # =========================
    # Job / Career switch /
    # Skill development
    #
    # +20 points

    if qualification.get("requirement"):
        score += 20


    # =========================
    # LEAD TEMPERATURE
    # =========================

    if score >= 80:

        status = "hot"

    elif score >= 50:

        status = "warm"

    else:

        status = "cold"


    # =========================
    # RESULT
    # =========================

    return {
        "score": score,
        "status": status
    }