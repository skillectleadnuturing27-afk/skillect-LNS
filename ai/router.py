# =========================
# AI FAST ROUTER
# =========================

import re


# =========================
# CLEAN MESSAGE
# =========================

def clean_message_text(message: str) -> str:
    """
    Normalize the lead message for fast routing.
    """

    message = message.lower().strip()

    message = re.sub(
        r"[^\w\s]",
        "",
        message
    )

    message = " ".join(
        message.split()
    )

    return message


# =========================
# HELPER
# =========================

def contains_any(
    message: str,
    keywords: tuple
) -> bool:

    return any(
        keyword in message
        for keyword in keywords
    )


# =========================
# FAST MESSAGE ROUTER
# =========================

def route_message(message: str):

    clean_message = clean_message_text(
        message
    )


    # =========================
    # GREETING
    # =========================

    greetings = {
        "hi",
        "hello",
        "hey",
        "hai",
        "hii",
        "hiii",
        "hello there",
        "hi there",
        "hey there",
        "good morning",
        "good afternoon",
        "good evening"
    }

    if clean_message in greetings:

        return (
            "Hi, welcome to Skillect Organization. "
            "How can I help you today?"
        )


    # =========================
    # THANK YOU
    # =========================

    thanks_messages = {
        "thanks",
        "thank you",
        "thankyou",
        "thanks a lot"
    }

    if clean_message in thanks_messages:

        return (
            "You're welcome. "
            "I'm happy to help you."
        )


    # =========================
    # PROVIDER DETECTION
    # =========================

    is_aws = contains_any(
        clean_message,
        (
            "aws",
            "amazon web services"
        )
    )

    is_azure = contains_any(
        clean_message,
        (
            "azure",
            "microsoft azure"
        )
    )


    # =========================
    # INTENT DETECTION
    # =========================

    is_fee_question = contains_any(
        clean_message,
        (
            "fee",
            "fees",
            "price",
            "cost",
            "how much"
        )
    )


    is_duration_question = contains_any(
        clean_message,
        (
            "duration",
            "how long",
            "how many months",
            "months"
        )
    )


    is_service_question = contains_any(
        clean_message,
        (
            "service",
            "services",
            "topic",
            "topics",
            "module",
            "modules",
            "subject",
            "subjects",
            "syllabus",
            "technology",
            "technologies",
            "course details",
            "course detail",
            "what will i learn",
            "what do i learn",
            "what can i learn",
            "what is covered",
            "what are covered",
            "what does it cover",
            "what do you teach",
            "what will you teach",
            "what is included",
            "what are included",
            "coures"
        )
    )


    is_prerequisite_question = contains_any(
        clean_message,
        (
            "prerequisite",
            "prerequisites",
            "eligibility",
            "eligible",
            "requirement to join",
            "requirements to join",
            "qualification to join",
            "who can join",
            "can i join",
            "can beginners join",
            "beginner join",
            "experience required",
            "need experience",
            "knowledge required",
            "need to know before"
        )
    )


    is_certificate_question = contains_any(
        clean_message,
        (
            "certificate",
            "certificates",
            "certification",
            "certifications",
            "official certificate",
            "official certification"
        )
    )


    # =========================
    # COMMON CLOUD USE CASES
    # =========================

    is_scalability_question = contains_any(
        clean_message,
        (
            "scalable application",
            "scalable applications",
            "application scaling",
            "scale application",
            "scale an application",
            "scalability"
        )
    )


    # =========================
    # AWS FAST ROUTES
    # =========================

    if is_aws:

        # =========================
        # AWS FEE
        # =========================

        if is_fee_question:

            return (
                "The AWS Cloud Engineering "
                "course fee is ₹25,000."
            )


        # =========================
        # AWS DURATION
        # =========================

        if is_duration_question:

            return (
                "The AWS Cloud Engineering "
                "course duration is 3 months."
            )


        # =========================
        # AWS PREREQUISITES
        # =========================

        if is_prerequisite_question:

            return (
                "Basic computer knowledge is enough "
                "to start AWS Cloud Engineering."
            )


        # =========================
        # AWS CERTIFICATION
        # =========================

        if is_certificate_question:

            return (
                "Students completing the Skillect AWS "
                "Cloud Engineering training receive a "
                "Skillect course completion certificate. "
                "For official AWS certification, the "
                "student must pass the relevant official "
                "AWS certification examination. Skillect "
                "provides training and exam-preparation "
                "support but does not directly issue the "
                "official AWS certification."
            )


        # =========================
        # AWS SERVICES / TOPICS
        # =========================

        if is_service_question:

            return (
                "AWS Cloud Engineering covers:\n\n"
                "Amazon EC2\n"
                "Amazon S3\n"
                "SNS\n"
                "IAM\n"
                "VPC\n"
                "EFS\n"
                "RDS\n"
                "Elastic Load Balancer\n"
                "CloudWatch\n\n"
                "The course duration is 3 months and "
                "the fee is ₹25,000."
            )


        # =========================
        # AWS SCALABLE APPLICATION
        # =========================

        if is_scalability_question:

            return (
                "AWS can support scalable applications "
                "using services such as EC2 for compute, "
                "Elastic Load Balancer for distributing "
                "traffic, and CloudWatch for monitoring. "
                "These services can be used as part of "
                "a scalable cloud architecture."
            )


    # =========================
    # AZURE FAST ROUTES
    # =========================

    if is_azure:

        # =========================
        # AZURE FEE
        # =========================

        if is_fee_question:

            return (
                "The Azure Cloud Engineering "
                "course fee is ₹25,000."
            )


        # =========================
        # AZURE DURATION
        # =========================

        if is_duration_question:

            return (
                "The Azure Cloud Engineering "
                "course duration is 3 months."
            )


        # =========================
        # AZURE PREREQUISITES
        # =========================

        if is_prerequisite_question:

            return (
                "Basic computer knowledge is enough "
                "to start Azure Cloud Engineering."
            )


        # =========================
        # AZURE CERTIFICATION
        # =========================

        if is_certificate_question:

            return (
                "Students completing the Skillect Azure "
                "Cloud Engineering training receive a "
                "Skillect course completion certificate. "
                "For official Microsoft Azure "
                "certification, the student must pass "
                "the relevant official Microsoft exam. "
                "Skillect provides training and "
                "exam-preparation support but does not "
                "directly issue the official Microsoft "
                "Azure certification."
            )


        # =========================
        # AZURE SERVICES / TOPICS
        # =========================

        if is_service_question:

            return (
                "Azure Cloud Engineering covers:\n\n"
                "Azure Virtual Machines\n"
                "Azure Blob Storage\n"
                "Microsoft Entra ID\n"
                "Azure Virtual Network\n"
                "Azure SQL Database\n"
                "Azure Load Balancer\n"
                "Azure Monitor\n\n"
                "The course duration is 3 months and "
                "the fee is ₹25,000."
            )


        # =========================
        # AZURE SCALABLE APPLICATION
        # =========================

        if is_scalability_question:

            return (
                "Microsoft Azure can support scalable "
                "applications using Azure Virtual "
                "Machines for compute, Azure Load "
                "Balancer for distributing traffic, "
                "and Azure Monitor for monitoring. "
                "These services can be used as part of "
                "a scalable cloud architecture."
            )


    # =========================
    # UNKNOWN / COMPLEX
    # =========================

    # Only questions that cannot be answered
    # safely by the fast deterministic routes
    # continue to RAG + Ollama.

    return None