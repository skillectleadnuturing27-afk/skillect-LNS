import re


# =========================
# HELPER - PERSONAL INTENT
# =========================

def has_personal_interest_intent(message: str) -> bool:

    message_lower = message.lower()

    interest_phrases = [
        "i am interested",
        "i'm interested",
        "i want to learn",
        "i want to study",
        "i want to join",
        "i would like to learn",
        "i would like to join",
        "i'm planning to learn",
        "i am planning to learn",
        "i plan to learn",
        "i want to take",
        "i would like to take",
    ]

    return any(
        phrase in message_lower
        for phrase in interest_phrases
    )


# =========================
# HELPER - BUDGET INTENT
# =========================

def has_budget_intent(message: str) -> bool:

    message_lower = message.lower()

    budget_phrases = [
        "my budget",
        "i have a budget",
        "i can spend",
        "i can afford",
        "my maximum budget",
        "my max budget",
    ]

    return any(
        phrase in message_lower
        for phrase in budget_phrases
    )


# =========================
# HELPER - TIMELINE INTENT
# =========================

def has_timeline_intent(message: str) -> bool:

    message_lower = message.lower()

    timeline_phrases = [
        "i want to start",
        "i can start",
        "i would like to start",
        "i'm planning to start",
        "i am planning to start",
        "i plan to start",
        "i need to start",
    ]

    return any(
        phrase in message_lower
        for phrase in timeline_phrases
    )


# =========================
# HELPER - REQUIREMENT INTENT
# =========================

def has_requirement_intent(message: str) -> bool:

    message_lower = message.lower()

    requirement_phrases = [
        "i need a job",
        "i want a job",
        "i am looking for a job",
        "i'm looking for a job",
        "i need this for a job",
        "i want this for a job",
        "i want to switch career",
        "i want a career switch",
        "i am planning a career switch",
        "i'm planning a career switch",
        "i want to improve my skills",
        "i need to improve my skills",
        "i want skill development",
    ]

    return any(
        phrase in message_lower
        for phrase in requirement_phrases
    )


# =========================
# QUALIFY LEAD
# =========================

def qualify_lead(message: str) -> dict:

    message_lower = message.lower()

    qualification = {
        "interest": None,
        "budget": None,
        "timeline": None,
        "requirement": None
    }


    # =========================
    # INTEREST
    # =========================

    # A technology/course mention alone is NOT enough.
    # The customer must express personal interest.

    if has_personal_interest_intent(message):

        if "azure" in message_lower:
            qualification["interest"] = "Azure"

        elif "aws" in message_lower:
            qualification["interest"] = "AWS"

        elif "cloud" in message_lower:
            qualification["interest"] = "Cloud Computing"

        elif "python" in message_lower:
            qualification["interest"] = "Python"


    # =========================
    # BUDGET
    # =========================

    # Only extract money when the customer is
    # talking about THEIR budget.
    #
    # Example:
    # "My budget is 20k."       -> qualification
    # "Is the course fee 20k?"  -> NOT qualification

    if has_budget_intent(message):

        if (
            "20000" in message_lower
            or "20k" in message_lower
            or "20,000" in message_lower
        ):
            qualification["budget"] = 20000

        elif (
            "30000" in message_lower
            or "30k" in message_lower
            or "30,000" in message_lower
        ):
            qualification["budget"] = 30000

        else:
            # Try to extract another numeric budget.
            budget_match = re.search(
                r"\b(\d{4,6})\b",
                message_lower.replace(",", "")
            )

            if budget_match:
                qualification["budget"] = int(
                    budget_match.group(1)
                )


    # =========================
    # TIMELINE
    # =========================

    # Timeline is updated only when the customer
    # talks about THEIR intended starting time.

    if has_timeline_intent(message):

        if (
            "immediately" in message_lower
            or "right now" in message_lower
            or "start now" in message_lower
            or "as soon as possible" in message_lower
            or "asap" in message_lower
        ):
            qualification["timeline"] = "Immediately"

        elif "this month" in message_lower:
            qualification["timeline"] = "This month"

        elif "next month" in message_lower:
            qualification["timeline"] = "Next month"


    # =========================
    # REQUIREMENT
    # =========================

    # A word like "job" alone is NOT enough.
    #
    # "Do you provide job support?" -> no change
    # "I need a job."               -> Job

    if has_requirement_intent(message):

        if (
            "career switch" in message_lower
            or "switch career" in message_lower
        ):
            qualification["requirement"] = "Career switch"

        elif (
            "improve my skills" in message_lower
            or "skill development" in message_lower
        ):
            qualification["requirement"] = "Skill development"

        elif "job" in message_lower:
            qualification["requirement"] = "Job"


    return qualification


# =========================
# MERGE QUALIFICATION MEMORY
# =========================

def merge_qualification(
    old_qualification: dict,
    new_qualification: dict
) -> dict:

    merged = old_qualification.copy()

    for key, value in new_qualification.items():

        # Preserve previous qualification unless
        # the customer provides new qualification data.
        if value is not None:
            merged[key] = value

    return merged