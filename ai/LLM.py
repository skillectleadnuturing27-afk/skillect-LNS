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
3. Ask only one qualification question at a time.
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
    it naturally and continue the conversation.
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
16. When a customer provides broad contact availability, such as
    "this week", you may ask for ONE specific preferred day or time.
"""


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
            "Is there a particular day or time that works best for you?"
        )

    if "next week" in prompt_lower:
        return (
            "Sure. You're available to be contacted next week. "
            "Is there a particular day or time that works best for you?"
        )

    if "tomorrow" in prompt_lower:
        return (
            "Sure. You're available to be contacted tomorrow. "
            "What time works best for you?"
        )

    return (
        "Sure. I've noted your availability. "
        "What day or time works best for you?"
    )


# =========================
# ASK AI
# =========================

def ask_ai(prompt: str, history=None) -> str:

    # =========================
    # 1. BUILD RAG QUERY
    # =========================

    retrieval_parts = []

    prompt_lower = prompt.lower()

    # Detect whether CURRENT message explicitly
    # mentions AWS or Azure.
    current_mentions_aws = "aws" in prompt_lower
    current_mentions_azure = "azure" in prompt_lower

    current_has_explicit_provider = (
        current_mentions_aws
        or current_mentions_azure
    )

    # If the current message explicitly says AWS/Azure,
    # current message gets retrieval priority.
    #
    # Example:
    # Saved interest = Azure
    # Current question = "What is the AWS course fee?"
    #
    # RAG must retrieve AWS information,
    # while qualification can remain Azure.
    if current_has_explicit_provider:

        retrieval_query = prompt

    else:

        # No explicit provider in the current message.
        # Use recent history to understand follow-ups:
        # "How much is it?"
        # "How long is it?"
        # "What about that?"
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
    # 2. RETRIEVE KNOWLEDGE
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
    # 3. BUILD SYSTEM CONTEXT
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
   - "I am free this weekend."

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
   - If useful, ask ONE relevant qualification question.
   - Do not ask for information the customer already provided.

10. Example:

    Customer:
    "I can start immediately and I need a job."

    Good response:
    "Got it. You're ready to start immediately and your goal is
    to get a job. What budget are you planning for the training?"

    Bad response:
    "I don't have enough information to answer that yet."

11. GENERAL CONVERSATION:

    Respond naturally to greetings, thanks, confirmations,
    and other normal conversation.

12. CONTACT AVAILABILITY:

    If the customer tells you when they are available for contact,
    acknowledge the availability naturally.

13. If the customer gives only a broad period such as:
    - this week
    - next week
    - tomorrow
    - this weekend

    you may ask ONE useful follow-up question for a preferred
    day or time when appropriate.

14. Example:

    Customer:
    "I am free this week. You can contact me."

    Good response:
    "Sure. You're available to be contacted this week. Is there
    a particular day or time that works best for you?"

15. Never say:
    - "I'll call you."
    - "I'll contact you."
    - "I'll send you a message."
    - "I'll reach out to you."
    - "I've scheduled your call."
    - "Your appointment is booked."

    unless the application actually has a tool or capability
    that performed that action.

16. Do not say:
    "I've got your contact information."

    unless the customer actually provided contact information
    in the conversation.

17. Contact availability is NOT automatically the same as the
    customer's course-start timeline.

18. Do not change or infer the qualification timeline only
    because the customer says when they are available for a call.

19. Never invent business facts.

20. Do not mention information that the customer did not ask for.

21. Do not mention missing business information unless the
    customer actually requested that information.

22. Previous conversation messages are for conversation context
    and memory.

23. Do not repeat unrelated information from previous
    conversation history.

24. If an older assistant message conflicts with CURRENT
    APPROVED BUSINESS KNOWLEDGE or these current rules,
    ignore the older assistant message.

25. For follow-up questions such as:
    - "How long is it?"
    - "How much is it?"
    - "What about that?"

    use recent conversation context to understand what
    the customer is referring to.

26. Answer only the customer's CURRENT message unless they
    explicitly refer to something discussed earlier.

27. IMPORTANT PROVIDER RULE:

    If the CURRENT customer message explicitly mentions AWS,
    answer the current business question about AWS.

    If the CURRENT customer message explicitly mentions Azure,
    answer the current business question about Azure.

    A saved qualification interest from previous conversation
    must NOT override an explicitly named provider in the
    CURRENT business question.

    Example:

    Previous qualification interest:
    Azure

    Current customer question:
    "What is the fee for the AWS Cloud Engineering course?"

    Correct behavior:
    Answer the AWS course fee.

    Do NOT change the customer's saved qualification interest
    merely because they asked an AWS business-information question.

28. Keep the final answer concise and natural.
"""


    # =========================
    # 4. START MESSAGES
    # =========================

    messages = [
        {
            "role": "system",
            "content": system_content
        }
    ]


    # =========================
    # 5. ADD CONVERSATION MEMORY
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
    # 6. REINFORCE CURRENT REQUEST
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

1. First classify the CURRENT message as:
   - business information question
   - qualification statement
   - general conversation
   - contact availability

2. Do not output the classification.

3. If it is a business information question:
   - Use only retrieved approved knowledge for business facts.
   - Answer directly if the information exists.
   - Use the fallback only when the requested business
     information is unavailable.

4. If it is a qualification statement:
   - Acknowledge what the customer said naturally.
   - Do NOT use the business-information fallback.
   - Do NOT invent business information.
   - Ask at most ONE useful qualification question if needed.

5. If it is general conversation:
   - Respond naturally.

6. If it is contact availability:
   - Acknowledge the customer's availability.
   - Do NOT claim that you will personally call, contact,
     reach out, message, schedule, or book anything.
   - Do NOT claim that you received contact information unless
     the customer actually provided it.
   - If useful, ask at most ONE question for a preferred
     day or time.
   - Do NOT treat contact availability as a new course-start
     timeline.

7. Understand references such as "it", "that", and "this"
   using recent conversation context.

8. CURRENT MESSAGE PROVIDER PRIORITY:

   If the CURRENT message explicitly says AWS:
   - Answer the current business question using AWS knowledge.
   - Do not switch the answer to Azure because of old history.

   If the CURRENT message explicitly says Azure:
   - Answer the current business question using Azure knowledge.
   - Do not switch the answer to AWS because of old history.

   Asking about a provider does NOT automatically mean the
   customer's qualification interest has changed.

9. Do not repeat unrelated previous conversation content.

10. Answer the CURRENT question directly.

11. Keep the response concise.
"""
        }
    )


    # =========================
    # 7. ADD CURRENT MESSAGE
    # =========================

    messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )


    # =========================
    # 8. GENERATE AI RESPONSE
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


        # =========================
        # 9. CONTACT AVAILABILITY GUARD
        # =========================

        safe_contact_response = (
            get_contact_availability_response(prompt)
        )

        if safe_contact_response is not None:
            return safe_contact_response


        # =========================
        # 10. NORMAL AI RESPONSE
        # =========================

        return ai_message


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