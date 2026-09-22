import re


# =========================
# HELPER - PERSONAL INTENT
# =========================

def has_personal_interest_intent(message: str) -> bool:

    message_lower = message.lower()

    interest_phrases = [
        "i am interested",
        "i'm interested",
        "im interested",
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
        "my interest is",
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
        # -------------------------
        # JOB
        # -------------------------
        "i need a job",
        "i want a job",
        "i am looking for a job",
        "i'm looking for a job",
        "im looking for a job",
        "i need this for a job",
        "i want this for a job",
        "i need this course for a job",
        "i want this course for a job",

        # -------------------------
        # CAREER SWITCH
        # -------------------------
        "i want to switch career",
        "i want to switch careers",
        "i want to switch my career",
        "i need to switch career",
        "i need to switch careers",
        "i need to switch my career",
        "i want a career switch",
        "i need a career switch",
        "i am planning a career switch",
        "i'm planning a career switch",
        "im planning a career switch",
        "for a career switch",
        "for career switch",
        "for switching career",
        "for switching careers",
        "to switch career",
        "to switch careers",
        "to switch my career",
        "career change",
        "change my career",

        # -------------------------
        # SKILL DEVELOPMENT
        # -------------------------
        "i want to improve my skills",
        "i need to improve my skills",
        "i want skill development",
        "i need skill development",
        "improve my skills",
        "develop my skills",
        "upgrade my skills",
        "upskill",
    ]

    return any(
        phrase in message_lower
        for phrase in requirement_phrases
    )


# =========================
# QUALIFY LEAD
# =========================

def qualify_lead(message: str) -> dict:

    message_lower = message.lower().strip()

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
    #
    # Example:
    # "What is the AWS fee?" -> no interest change
    # "I am interested in AWS." -> AWS

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
    # "My budget is 20k."      -> 20000
    # "Is the course fee 20k?" -> no budget change

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

            # Support another numeric budget such as:
            # "My budget is 25000."

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

    # Timeline changes only when the customer
    # describes THEIR intended starting time.

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

    # Requirement changes only when the customer
    # expresses a personal goal.
    #
    # "Do you provide job support?"
    # -> no requirement change
    #
    # "I need a job."
    # -> Job
    #
    # "I need this course for a career switch."
    # -> Career switch

    if has_requirement_intent(message):

        # -------------------------
        # CAREER SWITCH
        # -------------------------

        career_switch_phrases = [
            "career switch",
            "switch career",
            "switch careers",
            "switch my career",
            "switching career",
            "switching careers",
            "career change",
            "change my career",
        ]

        if any(
            phrase in message_lower
            for phrase in career_switch_phrases
        ):
            qualification["requirement"] = "Career switch"

        # -------------------------
        # SKILL DEVELOPMENT
        # -------------------------

        elif (
            "improve my skills" in message_lower
            or "skill development" in message_lower
            or "develop my skills" in message_lower
            or "upgrade my skills" in message_lower
            or "upskill" in message_lower
        ):
            qualification["requirement"] = "Skill development"

        # -------------------------
        # JOB
        # -------------------------

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

        # Preserve the previous qualification value
        # unless the customer explicitly provides
        # a new qualification value.

        if value is not None:
            merged[key] = value

    return merged