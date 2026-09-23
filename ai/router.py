# =========================
# AI FAST ROUTER
# =========================

import re


# =========================
# CLEAN MESSAGE
# =========================

def clean_message_text(message: str) -> str:
    """
    Convert the lead message into a simple
    normalized format for fast routing.
    """

    message = message.lower().strip()

    # Remove punctuation
    message = re.sub(
        r"[^\w\s]",
        "",
        message
    )

    # Remove extra spaces
    message = " ".join(
        message.split()
    )

    return message


# =========================
# FAST MESSAGE ROUTER
# =========================

def route_message(message: str):
    """
    Decide whether the message can be answered
    directly without calling Ollama.

    Returns:
        str  -> direct fast response
        None -> continue to RAG + Ollama
    """

    clean_message = clean_message_text(
        message
    )


    # =========================
    # GREETING ROUTE
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
    # THANK YOU ROUTE
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
    # COMPLEX / UNKNOWN MESSAGE
    # =========================

    # Returning None tells main.py:
    #
    # Router cannot answer this directly.
    # Continue with existing RAG + Ollama.

    return None