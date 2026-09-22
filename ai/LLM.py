import ollama

from ai.rag import retrieve_relevant_knowledge


# =========================
# CONSTANTS
# =========================

BUSINESS_FALLBACK = (
    "I don't have enough information to answer that yet."
)


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
20. If the customer requests a business detail that is explicitly
    unavailable, do not substitute other available information.
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

    if "aws" in prompt_lower or "amazon" in prompt_lower:

        return (
            "Yes. Skillect provides training and examination "
            "preparation support for relevant official AWS "
            "certification examinations. To earn the official AWS "
            "certification, you must pass the relevant official AWS "
            "certification examination. Skillect does not directly "
            "issue the official AWS certification."
        )

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
# EXPLICIT INTEREST GUARD
# =========================

def get_explicit_interest_response(prompt: str):

    prompt_lower = prompt.lower().strip()

    interest_phrases = [
        "i am interested in",
        "i'm interested in",
        "im interested in",
        "my interest is",
        "actually i am interested in",
        "actually i'm interested in",
        "actually im interested in",
    ]

    is_interest_statement = any(
        phrase in prompt_lower
        for phrase in interest_phrases
    )

    if not is_interest_statement:
        return None

    if "aws" in prompt_lower or "amazon" in prompt_lower:
        return (
            "Great. You're interested in "
            "AWS Cloud Engineering."
        )

    if "azure" in prompt_lower:
        return (
            "Great. You're interested in "
            "Azure Cloud Engineering."
        )

    return None


# =========================
# REQUIREMENT ACKNOWLEDGEMENT
# =========================

def get_requirement_response(
    prompt: str,
    qualification=None
):

    prompt_lower = prompt.lower().strip()

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
        phrase in prompt_lower
        for phrase in career_switch_phrases
    ):
        return (
            "Got it. You're looking to make "
            "a career switch."
        )

    skill_phrases = [
        "improve my skills",
        "skill development",
        "develop my skills",
        "upgrade my skills",
        "upskill",
    ]

    if any(
        phrase in prompt_lower
        for phrase in skill_phrases
    ):
        return (
            "Got it. You're looking to improve "
            "your skills."
        )

    job_phrases = [
        "i need a job",
        "i want a job",
        "i am looking for a job",
        "i'm looking for a job",
        "im looking for a job",
        "i need this for a job",
        "i want this for a job",
        "i need this course for a job",
        "i want this course for a job",
    ]

    if any(
        phrase in prompt_lower
        for phrase in job_phrases
    ):
        return (
            "Got it. Your current requirement "
            "is a job."
        )

    return None


# =========================
# QUALIFICATION MEMORY GUARD
# =========================

def get_qualification_memory_response(
    prompt: str,
    qualification=None
):

    if not qualification:
        return None

    prompt_lower = prompt.lower().strip()

    # -------------------------
    # CURRENT INTEREST
    # -------------------------

    interest_questions = [
        "what is my current interest",
        "what's my current interest",
        "what is my interest",
        "what's my interest",
        "which course am i interested in",
        "which course i am interested in",
        "what course am i interested in",
    ]

    if any(
        phrase in prompt_lower
        for phrase in interest_questions
    ):

        interest = qualification.get("interest")

        if interest:
            return (
                f"Your current interest is "
                f"{interest} Cloud Engineering."
            )

        return (
            "You haven't provided your current "
            "course interest yet."
        )

    # -------------------------
    # CURRENT BUDGET
    # -------------------------

    budget_questions = [
        "what is my budget",
        "what's my budget",
        "what is my current budget",
        "what's my current budget",
        "how much is my budget",
    ]

    if any(
        phrase in prompt_lower
        for phrase in budget_questions
    ):

        budget = qualification.get("budget")

        if budget is not None:
            return f"Your current budget is ₹{budget:,}."

        return "You haven't provided your budget yet."

    # -------------------------
    # CURRENT TIMELINE
    # -------------------------

    timeline_questions = [
        "what is my timeline",
        "what's my timeline",
        "what is my current timeline",
        "what's my current timeline",
        "when do i want to start",
        "when am i planning to start",
    ]

    if any(
        phrase in prompt_lower
        for phrase in timeline_questions
    ):

        timeline = qualification.get("timeline")

        if timeline:
            return (
                f"Your current timeline is "
                f"{timeline}."
            )

        return "You haven't provided your timeline yet."

    # -------------------------
    # CURRENT REQUIREMENT
    # -------------------------

    requirement_questions = [
        "what is my requirement",
        "what's my requirement",
        "what is my current requirement",
        "what's my current requirement",
        "what do i need",
        "what is my goal",
        "what's my goal",
    ]

    if any(
        phrase in prompt_lower
        for phrase in requirement_questions
    ):

        requirement = qualification.get("requirement")

        if requirement:
            return (
                f"Your current requirement is "
                f"{requirement}."
            )

        return (
            "You haven't provided your requirement yet."
        )

    return None


# =========================
# UNAVAILABLE BUSINESS GUARD
# =========================

def get_unavailable_business_response(prompt: str):

    prompt_lower = prompt.lower().strip()

    is_azure = "azure" in prompt_lower

    if not is_azure:
        return None

    # Azure prerequisite is an approved answer.
    prerequisite_phrases = [
        "prerequisite",
        "prerequisites",
        "requirement to join",
        "requirements to join",
        "required to join",
        "need to know before",
        "knowledge required",
    ]

    if any(phrase in prompt_lower for phrase in prerequisite_phrases):
        return (
            "Basic computer knowledge is enough to start "
            "Azure Cloud Engineering."
        )

    # These Azure details are still unavailable.
    unavailable_azure_topics = [
        "training mode",
        "class mode",
        "course mode",
        "online class",
        "offline class",
        "online training",
        "offline training",
        "instructor-led",
        "target student",
        "target students",
        "who can join",
        "who should join",
        "who is this course for",
        "suitable for",
        "career support",
        "job support",
        "placement support",
        "interview preparation",
        "interview support",
        "project guidance",
        "career guidance",
    ]

    if any(phrase in prompt_lower for phrase in unavailable_azure_topics):
        return BUSINESS_FALLBACK

    return None


# =========================
# ASK AI
# =========================

def ask_ai(
    prompt: str,
    history=None,
    qualification=None
) -> str:

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
    # 3. EXPLICIT INTEREST GUARD
    # =========================

    interest_response = get_explicit_interest_response(
        prompt
    )

    if interest_response is not None:
        return interest_response

    # =========================
    # 4. REQUIREMENT GUARD
    # =========================

    requirement_response = get_requirement_response(
        prompt,
        qualification
    )

    if requirement_response is not None:
        return requirement_response

    # =========================
    # 5. QUALIFICATION MEMORY
    # =========================

    qualification_response = (
        get_qualification_memory_response(
            prompt,
            qualification
        )
    )

    if qualification_response is not None:
        return qualification_response

    # =========================
    # 6. UNAVAILABLE BUSINESS GUARD
    # =========================

    unavailable_response = (
        get_unavailable_business_response(prompt)
    )

    if unavailable_response is not None:
        return unavailable_response

    # =========================
    # 7. BUILD RAG QUERY
    # =========================

    retrieval_parts = []

    prompt_lower = prompt.lower()

    current_mentions_aws = (
        "aws" in prompt_lower
        or "amazon" in prompt_lower
    )

    current_mentions_azure = (
        "azure" in prompt_lower
    )

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
    # 8. RETRIEVE KNOWLEDGE
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
    # 9. BUILD QUALIFICATION CONTEXT
    # =========================

    if qualification:

        qualification_context = f"""
Interest:
{qualification.get("interest")}

Budget:
{qualification.get("budget")}

Timeline:
{qualification.get("timeline")}

Requirement:
{qualification.get("requirement")}
"""

    else:

        qualification_context = """
No structured qualification data is currently available.
"""

    # =========================
    # 10. BUILD SYSTEM CONTEXT
    # =========================

    system_content = f"""
{SYSTEM_PROMPT}

=========================
CURRENT STRUCTURED QUALIFICATION
=========================

{qualification_context}

=========================
CURRENT APPROVED BUSINESS KNOWLEDGE
=========================

{business_knowledge}

=========================
END OF APPROVED BUSINESS KNOWLEDGE
=========================

STRICT GROUNDING RULES:

1. CURRENT APPROVED BUSINESS KNOWLEDGE is the authoritative
   source for business facts.

2. CURRENT STRUCTURED QUALIFICATION is the authoritative
   source for the customer's:
   - interest
   - budget
   - timeline
   - requirement

3. If history conflicts with structured qualification,
   use structured qualification.

4. For a business-information question, answer ONLY the
   information specifically requested.

5. Do not substitute another available business fact when
   the requested fact is unavailable.

7. If requested information exists in approved knowledge,
   answer directly.

8. If all specifically requested business information is
   unavailable, answer exactly:

   "{BUSINESS_FALLBACK}"

9. Never invent business facts.

10. Qualification statements are not business-information
    questions.

11. A qualification statement should be acknowledged
    naturally.

12. Do not change qualification merely because a customer
    asks a factual question about AWS or Azure.

13. If the CURRENT message explicitly mentions AWS, use
    AWS business knowledge for that business question.

14. If the CURRENT message explicitly mentions Azure, use
    Azure business knowledge for that business question.

15. A saved interest must not override a provider explicitly
    named in the current business question.

16. Do not repeat unrelated conversation history.

17. Do not mention information the customer did not ask for.

18. Do not add unnecessary follow-up questions.

19. After answering a business-information question, STOP.

20. Keep the final response concise and direct.
"""

    # =========================
    # 11. START MESSAGES
    # =========================

    messages = [
        {
            "role": "system",
            "content": system_content
        }
    ]

    # =========================
    # 12. ADD CONVERSATION MEMORY
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
    # 13. REINFORCE CURRENT REQUEST
    # =========================

    messages.append(
        {
            "role": "system",
            "content": f"""
CURRENT CUSTOMER MESSAGE:

{prompt}

CURRENT STRUCTURED QUALIFICATION:

Interest: {
    qualification.get("interest")
    if qualification
    else None
}

Budget: {
    qualification.get("budget")
    if qualification
    else None
}

Timeline: {
    qualification.get("timeline")
    if qualification
    else None
}

Requirement: {
    qualification.get("requirement")
    if qualification
    else None
}

RETRIEVED APPROVED KNOWLEDGE:

{business_knowledge}

FINAL RESPONSE RULES:

1. Answer only the CURRENT customer message.

2. Use only approved knowledge for business facts.

3. If the specifically requested business fact is unavailable,
   do not replace it with other available facts.

4. If the requested business information is unavailable,
   reply exactly:

   "{BUSINESS_FALLBACK}"

5. If AWS is explicitly named in the current question,
   use AWS information.

6. If Azure is explicitly named in the current question,
   use Azure information.

7. The customer's saved qualification interest does not
   override the provider named in the current question.

8. Asking a factual question about AWS or Azure does not
   automatically change the saved interest.

9. Do not repeat unrelated history.

10. Do not invent information.

11. Do not add unnecessary follow-up questions.

12. Keep the response concise.
"""
        }
    )

    # =========================
    # 14. ADD CURRENT MESSAGE
    # =========================

    messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    # =========================
    # 15. GENERATE AI RESPONSE
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