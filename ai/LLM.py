import ollama

from ai.rag import retrieve_relevant_knowledge


# =========================
# SYSTEM PROMPT
# =========================

SYSTEM_PROMPT = """
You are a Lead Nurturing AI Assistant.

Your job is to communicate with potential customers and understand
their requirements.

Rules:
1. Be professional, friendly, and concise.
2. Help the customer with their enquiry.
3. Ask only one qualification question at a time when a qualification
   question is actually needed.
4. Try to understand the customer's:
   - interest
   - budget
   - timeline
   - requirement
5. For business-specific questions, use ONLY the approved business
   knowledge provided in the BUSINESS KNOWLEDGE section.
6. Never invent business information, prices, course details,
   discounts, guarantees, services, or policies.
7. Do not pressure the customer.
8. Keep responses easy to understand.
9. Distinguish between a customer QUESTION and a customer STATEMENT.
10. A customer statement about their interest, budget, timeline,
    requirement, career goal, situation, or contact availability
    does NOT require business knowledge.
11. When the customer provides qualification information, acknowledge
    it naturally.
12. Do not use the business-information fallback just because a
    qualification statement is not present in the knowledge base.
13. If the customer says when they are available to be contacted,
    acknowledge their availability naturally.
14. Never claim that you have scheduled a call, booked an appointment,
    sent a message, contacted the customer, or will contact the
    customer later unless the application actually provides that
    capability.
15. Never claim that the customer provided contact information unless
    that information is actually present in the conversation.
16. For business-information questions, answer the customer's question
    directly and stop after answering it.
17. Do not add unnecessary follow-up questions.
18. Do not repeat the same information multiple times in one response.
19. Give each important fact only once unless repetition is required
    to avoid misunderstanding.
"""


# =========================
# CERTIFICATION GUARD
# =========================

def get_certification_response(prompt: str):

    prompt_lower = prompt.lower().strip()

    certification_words = [
        "certification",
        "certificate",
        "international certificate",
        "international certification",
        "certification exam",
        "certification examination",
        "exam preparation",
        "examination preparation",
    ]

    is_certification_message = any(
        word in prompt_lower
        for word in certification_words
    )

    if not is_certification_message:
        return None

    # -------------------------
    # AWS CERTIFICATION
    # -------------------------

    if "aws" in prompt_lower or "amazon" in prompt_lower:

        return (
            "Yes. Skillect provides training and examination "
            "preparation support for relevant official AWS "
            "certification examinations. To earn the official AWS "
            "certification, you must pass the relevant official AWS "
            "certification examination. Skillect does not directly "
            "issue the official AWS certification."
        )

    # -------------------------
    # AZURE CERTIFICATION
    # -------------------------

    if (
        "azure" in prompt_lower
        or "microsoft" in prompt_lower
    ):

        return (
            "Yes. Skillect provides training and examination "
            "preparation support for relevant official Microsoft "
            "Azure certification examinations. To earn the official "
            "Microsoft Azure certification, you must pass the relevant "
            "official Microsoft certification examination. Skillect "
            "does not directly issue the official Microsoft Azure "
            "certification."
        )

    # -------------------------
    # GENERAL CERTIFICATION
    # -------------------------

    return (
        "Skillect provides training and examination preparation "
        "support for relevant AWS and Microsoft Azure certification "
        "examinations. Official certifications require students to "
        "pass the relevant official AWS or Microsoft certification "
        "examination. Skillect does not directly issue these official "
        "international certifications."
    )


# =========================
# CONTACT AVAILABILITY GUARD
# =========================

def get_contact_availability_response(prompt: str):

    prompt_lower = prompt.lower().strip()

    contact_phrases = [
        "contact me",
        "call me",
        "reach me",
        "available for a call",
        "available to talk",
        "available to speak",
        "free this week",
        "free next week",
        "free tomorrow",
        "free on",
        "free after",
    ]

    is_contact_availability = any(
        phrase in prompt_lower
        for phrase in contact_phrases
    )

    if not is_contact_availability:
        return None

    if "this week" in prompt_lower:
        return (
            "Sure. You're available to be contacted this week. "
            "Please provide your preferred day and time."
        )

    if "next week" in prompt_lower:
        return (
            "Sure. You're available to be contacted next week. "
            "Please provide your preferred day and time."
        )

    if "tomorrow" in prompt_lower:
        return (
            "Sure. You're available to be contacted tomorrow. "
            "Please provide your preferred time."
        )

    return (
        "Sure. I've noted your availability. "
        "Please provide your preferred day and time."
    )


# =========================
# ASK AI
# =========================

def ask_ai(prompt: str, history=None) -> str:

    # =========================
    # 1. CERTIFICATION GUARD
    # =========================

    certification_response = get_certification_response(
        prompt
    )

    if certification_response is not None:
        return certification_response


    # =========================
    # 2. CONTACT GUARD
    # =========================

    contact_response = get_contact_availability_response(
        prompt
    )

    if contact_response is not None:
        return contact_response


    # =========================
    # 3. BUILD RAG QUERY
    # =========================

    retrieval_parts = []

    prompt_lower = prompt.lower()

    current_mentions_aws = "aws" in prompt_lower
    current_mentions_azure = "azure" in prompt_lower

    current_has_explicit_provider = (
        current_mentions_aws
        or current_mentions_azure
    )

    if current_has_explicit_provider:

        retrieval_query = prompt

    else:

        if history:

            recent_user_messages = [
                item.message
                for item in history
                if item.role == "user"
            ][-3:]

            retrieval_parts.extend(
                recent_user_messages
            )

        retrieval_parts.append(prompt)

        retrieval_query = " ".join(
            retrieval_parts
        )


    # =========================
    # 4. RETRIEVE KNOWLEDGE
    # =========================

    business_knowledge = retrieve_relevant_knowledge(
        retrieval_query
    )

    knowledge_found = bool(
        business_knowledge.strip()
    )

    if not knowledge_found:
        business_knowledge = (
            "NO RELEVANT APPROVED BUSINESS INFORMATION FOUND."
        )


    # =========================
    # 5. BUILD SYSTEM CONTEXT
    # =========================

    system_content = f"""
{SYSTEM_PROMPT}

=========================
CURRENT APPROVED BUSINESS KNOWLEDGE
=========================

{business_knowledge}

=========================
END OF APPROVED BUSINESS KNOWLEDGE
=========================

STRICT GROUNDING RULES:

1. The CURRENT APPROVED BUSINESS KNOWLEDGE is the highest
   priority source for business facts.

2. First determine what type of message the customer sent.

   TYPE A - BUSINESS INFORMATION QUESTION

   Examples:
   - "How much is the course?"
   - "How long is the course?"
   - "What AWS topics will I learn?"
   - "Do you provide a discount?"
   - "Is the training online?"

   TYPE B - CUSTOMER QUALIFICATION STATEMENT

   Examples:
   - "My budget is 20k."
   - "I need a job."
   - "I can start immediately."
   - "I am interested in AWS."
   - "I want to switch my career."

   TYPE C - GENERAL CONVERSATION

   Examples:
   - "Hello"
   - "Okay"
   - "Thanks"
   - "I understand"

   TYPE D - CONTACT AVAILABILITY

   Examples:
   - "I am free this week. You can contact me."
   - "Call me tomorrow."
   - "I am available on Friday."
   - "You can contact me after 6 PM."

3. BUSINESS INFORMATION QUESTIONS:

   If the customer asks for business-specific information,
   use ONLY the CURRENT APPROVED BUSINESS KNOWLEDGE.

4. If the requested business information exists in the approved
   knowledge, answer directly using that information.

5. When the requested business information is available,
   DO NOT add any fallback message.

6. If ALL business information specifically requested by the
   customer is unavailable, reply exactly:

   "I don't have enough information to answer that yet."

7. If the customer asks for multiple business details and only
   some are available:
   - Answer the available parts.
   - Clearly identify only the unavailable requested parts.

8. CUSTOMER QUALIFICATION STATEMENTS:

   If the customer is telling you about their interest, budget,
   timeline, requirement, career goal, or personal situation,
   DO NOT use the missing-business-information fallback.

9. For a qualification statement:
   - Acknowledge the information naturally.
   - Do not invent business facts.
   - If a qualification question is necessary, ask at most ONE.
   - Do not ask for information the customer already provided.

10. GENERAL CONVERSATION:

    Respond naturally to greetings, thanks, confirmations,
    and other normal conversation.

11. Never invent business facts.

12. Do not mention information that the customer did not ask for.

13. Do not mention missing business information unless the
    customer actually requested that information.

14. Previous conversation messages are for conversation context
    and memory.

15. Do not repeat unrelated information from previous
    conversation history.

16. If an older assistant message conflicts with CURRENT
    APPROVED BUSINESS KNOWLEDGE or these current rules,
    ignore the older assistant message.

17. For follow-up questions such as:
    - "How long is it?"
    - "How much is it?"
    - "What about that?"

    use recent conversation context to understand what
    the customer is referring to.

18. Answer only the customer's CURRENT message unless they
    explicitly refer to something discussed earlier.

19. IMPORTANT PROVIDER RULE:

    If the CURRENT customer message explicitly mentions AWS,
    answer the current business question about AWS.

    If the CURRENT customer message explicitly mentions Azure,
    answer the current business question about Azure.

    A saved qualification interest from previous conversation
    must NOT override an explicitly named provider in the
    CURRENT business question.

20. Asking about a provider does NOT automatically mean the
    customer's qualification interest has changed.

21. BUSINESS RESPONSE ENDING RULE:

    After answering a business-information question, STOP.

    Do NOT end with:
    - "Would you like to know more?"
    - "Would you like information about..."
    - "Do you want to know..."
    - "Can I help with anything else?"

22. REPETITION RULE:

    Do not state the same fact more than once in the same
    response.

23. Keep the final answer concise, direct, and natural.
"""


    # =========================
    # 6. START MESSAGES
    # =========================

    messages = [
        {
            "role": "system",
            "content": system_content
        }
    ]


    # =========================
    # 7. ADD CONVERSATION MEMORY
    # =========================

    if history:

        for item in history:

            messages.append(
                {
                    "role": item.role,
                    "content": item.message
                }
            )


    # =========================
    # 8. REINFORCE CURRENT REQUEST
    # =========================

    messages.append(
        {
            "role": "system",
            "content": f"""
CURRENT CUSTOMER MESSAGE:

{prompt}

RETRIEVED APPROVED KNOWLEDGE:

{business_knowledge}

INSTRUCTIONS FOR THIS RESPONSE:

1. Answer the CURRENT customer message.

2. For business questions:
   - Use only the retrieved approved knowledge.
   - Answer only what was asked.
   - Do not invent information.
   - Do not repeat information.
   - Do not ask an unnecessary follow-up question.

3. For qualification statements:
   - Acknowledge the information naturally.
   - Do not invent business information.
   - Ask at most ONE qualification question only if needed.

4. If the CURRENT message explicitly says AWS:
   answer the business question using AWS knowledge.

5. If the CURRENT message explicitly says Azure:
   answer the business question using Azure knowledge.

6. Asking about AWS or Azure does NOT automatically change
   the customer's saved qualification interest.

7. Do not repeat unrelated previous conversation content.

8. Keep the response concise.

9. After answering a business-information question, STOP.
"""
        }
    )


    # =========================
    # 9. ADD CURRENT MESSAGE
    # =========================

    messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )


    # =========================
    # 10. GENERATE AI RESPONSE
    # =========================

    try:

        response = ollama.chat(
            model="llama3.2:3b",
            messages=messages,
            options={
                "temperature": 0
            }
        )

        ai_message = response["message"]["content"]

        if not ai_message or not ai_message.strip():
            raise RuntimeError(
                "Ollama returned an empty response"
            )

        return ai_message.strip()


    # =========================
    # OLLAMA CONNECTION FAILURE
    # =========================

    except ConnectionError as error:

        print(
            f"Ollama connection error: {error}"
        )

        raise RuntimeError(
            "AI service is temporarily unavailable"
        ) from error


    # =========================
    # OTHER OLLAMA FAILURE
    # =========================

    except Exception as error:

        print(
            f"Ollama AI error: "
            f"{type(error).__name__}: {error}"
        )

        raise RuntimeError(
            "AI service is temporarily unavailable"
        ) from error