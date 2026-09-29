import re
import time

import ollama

from ai.rag import retrieve_relevant_knowledge


# =========================
# CONSTANTS
# =========================

BUSINESS_FALLBACK = (
    "I don't have enough information to answer that yet."
)

MAX_LLM_HISTORY = 8


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
   interest
   budget
   timeline
   requirement

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

11. When the customer provides qualification information,
    acknowledge it naturally.

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

20. If requested business information is unavailable, do not invent it.

21. Do not use Markdown bullet symbols such as *, -, or • in the
    final response. When listing multiple items, write each item on
    its own separate line without any bullet symbol.

22. Never ask for a qualification field that already has a value in
    CURRENT STRUCTURED QUALIFICATION.

23. When a qualification statement needs a follow-up question, ask only
    the next missing qualification field in this order:
    interest, budget, timeline, requirement.

Example:

Amazon EC2
Amazon S3
IAM
VPC
EFS
RDS
Elastic Load Balancer
CloudWatch

Do NOT write:

* Amazon EC2
* Amazon S3
* IAM
"""


# =========================
# RESPONSE FORMAT CLEANER
# =========================

def clean_response_format(text: str) -> str:

    if not text:
        return text

    cleaned_lines = []

    for line in text.splitlines():

        cleaned_line = re.sub(
            r"^\s*[\*\-•]\s+",
            "",
            line
        )

        cleaned_line = cleaned_line.replace(
            "**",
            ""
        )

        cleaned_lines.append(
            cleaned_line.rstrip()
        )

    return "\n".join(
        cleaned_lines
    ).strip()


# =========================
# CERTIFICATION GUARD
# =========================

def get_certification_response(
    prompt: str
):

    prompt_lower = (
        prompt.lower().strip()
    )

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


    # =========================
    # AWS
    # =========================

    if (
        "aws" in prompt_lower
        or "amazon" in prompt_lower
    ):

        return (
            "Yes. Skillect provides training and examination "
            "preparation support for relevant official AWS "
            "certification examinations. To earn the official AWS "
            "certification, you must pass the relevant official AWS "
            "certification examination. Skillect does not directly "
            "issue the official AWS certification."
        )


    # =========================
    # AZURE
    # =========================

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


    # =========================
    # GENERAL
    # =========================

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

def get_contact_availability_response(
    prompt: str
):

    prompt_lower = (
        prompt.lower().strip()
    )

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

def get_explicit_interest_response(
    prompt: str
):

    prompt_lower = (
        prompt.lower().strip()
    )

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


    if (
        "aws" in prompt_lower
        or "amazon" in prompt_lower
    ):

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

    prompt_lower = (
        prompt.lower().strip()
    )


    # =========================
    # CAREER SWITCH
    # =========================

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


    # =========================
    # SKILL DEVELOPMENT
    # =========================

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


    # =========================
    # JOB
    # =========================

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
# QUALIFICATION STATEMENT GUARD
# =========================

def get_qualification_statement_response(
    prompt: str,
    qualification=None
):

    if not qualification:
        return None


    prompt_lower = (
        prompt.lower().strip()
    )


    interest = qualification.get(
        "interest"
    )

    budget = qualification.get(
        "budget"
    )

    timeline = qualification.get(
        "timeline"
    )

    requirement = qualification.get(
        "requirement"
    )


    # =========================
    # BUDGET STATEMENT
    # =========================

    budget_phrases = [
        "my budget",
        "i have a budget",
        "i can spend",
        "i can afford",
        "my maximum budget",
        "my max budget",
    ]

    is_budget_statement = any(
        phrase in prompt_lower
        for phrase in budget_phrases
    )


    if (
        is_budget_statement
        and budget is not None
    ):

        acknowledgement = (
            f"Got it. Your budget is "
            f"₹{budget:,}."
        )


        # Interest missing

        if not interest:

            return (
                f"{acknowledgement} "
                "What is your interest in "
                "cloud engineering?"
            )


        # Timeline missing

        if not timeline:

            return (
                f"{acknowledgement} "
                "When are you planning to "
                "start the course?"
            )


        # Requirement missing

        if not requirement:

            return (
                f"{acknowledgement} "
                "What is your main goal for "
                "taking the course?"
            )


        return acknowledgement


    # =========================
    # TIMELINE STATEMENT
    # =========================

    timeline_phrases = [
        "i want to start",
        "i can start",
        "i would like to start",
        "i'm planning to start",
        "i am planning to start",
        "i plan to start",
        "i need to start",
        "start immediately",
        "start now",
        "this month",
        "next month",
        "as soon as possible",
        "asap",
    ]

    is_timeline_statement = any(
        phrase in prompt_lower
        for phrase in timeline_phrases
    )


    if (
        is_timeline_statement
        and timeline
    ):

        acknowledgement = (
            f"Got it. You're planning to start "
            f"{timeline.lower()}."
        )


        # Interest missing

        if not interest:

            return (
                f"{acknowledgement} "
                "What is your interest in "
                "cloud engineering?"
            )


        # Budget missing

        if budget is None:

            return (
                f"{acknowledgement} "
                "What is your budget for "
                "the course?"
            )


        # Requirement missing

        if not requirement:

            return (
                f"{acknowledgement} "
                "What is your main goal for "
                "taking the course?"
            )


        return acknowledgement


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


    prompt_lower = (
        prompt.lower().strip()
    )


    # =========================
    # CURRENT INTEREST
    # =========================

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

        interest = qualification.get(
            "interest"
        )

        if interest:

            return (
                f"Your current interest is "
                f"{interest} Cloud Engineering."
            )

        return (
            "You haven't provided your current "
            "course interest yet."
        )


    # =========================
    # CURRENT BUDGET
    # =========================

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

        budget = qualification.get(
            "budget"
        )

        if budget is not None:

            return (
                f"Your current budget is "
                f"₹{budget:,}."
            )

        return (
            "You haven't provided your budget yet."
        )


    # =========================
    # CURRENT TIMELINE
    # =========================

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

        timeline = qualification.get(
            "timeline"
        )

        if timeline:

            return (
                f"Your current timeline is "
                f"{timeline}."
            )

        return (
            "You haven't provided your timeline yet."
        )


    # =========================
    # CURRENT REQUIREMENT
    # =========================

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

        requirement = qualification.get(
            "requirement"
        )

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
# ASK AI
# =========================

def ask_ai(
    prompt: str,
    history=None,
    qualification=None
) -> str:

    total_llm_start = (
        time.perf_counter()
    )


    # =========================
    # 1. CERTIFICATION GUARD
    # =========================

    certification_response = (
        get_certification_response(
            prompt
        )
    )

    if certification_response is not None:

        return clean_response_format(
            certification_response
        )


    # =========================
    # 2. CONTACT GUARD
    # =========================

    contact_response = (
        get_contact_availability_response(
            prompt
        )
    )

    if contact_response is not None:

        return clean_response_format(
            contact_response
        )


    # =========================
    # 3. EXPLICIT INTEREST GUARD
    # =========================

    interest_response = (
        get_explicit_interest_response(
            prompt
        )
    )

    if interest_response is not None:

        return clean_response_format(
            interest_response
        )


    # =========================
    # 4. REQUIREMENT GUARD
    # =========================

    requirement_response = (
        get_requirement_response(
            prompt,
            qualification
        )
    )

    if requirement_response is not None:

        return clean_response_format(
            requirement_response
        )


    # =========================
    # 5. QUALIFICATION STATEMENT
    # =========================

    qualification_statement_response = (
        get_qualification_statement_response(
            prompt,
            qualification
        )
    )

    if qualification_statement_response is not None:

        return clean_response_format(
            qualification_statement_response
        )


    # =========================
    # 6. QUALIFICATION MEMORY
    # =========================

    qualification_response = (
        get_qualification_memory_response(
            prompt,
            qualification
        )
    )

    if qualification_response is not None:

        return clean_response_format(
            qualification_response
        )


    # =========================
    # 7. BUILD RAG QUERY
    # =========================

    retrieval_parts = []

    prompt_lower = (
        prompt.lower()
    )


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
                if item.role in (
                    "lead",
                    "user"
                )
            ][-3:]


            retrieval_parts.extend(
                recent_user_messages
            )


        retrieval_parts.append(
            prompt
        )


        retrieval_query = " ".join(
            retrieval_parts
        )


    # =========================
    # 8. RETRIEVE KNOWLEDGE
    # =========================

    rag_start = (
        time.perf_counter()
    )


    business_knowledge = (
        retrieve_relevant_knowledge(
            retrieval_query
        )
    )


    rag_time = (
        time.perf_counter()
        - rag_start
    )


    print(
        f"RAG TIME: "
        f"{rag_time:.3f} seconds"
    )


    knowledge_found = bool(
        business_knowledge.strip()
    )


    if not knowledge_found:

        business_knowledge = (
            "NO RELEVANT APPROVED "
            "BUSINESS INFORMATION FOUND."
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

    prompt_build_start = (
        time.perf_counter()
    )


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
   interest
   budget
   timeline
   requirement

3. If history conflicts with structured qualification,
   use structured qualification.

4. For a business-information question, answer ONLY the
   information specifically requested.

5. Do not substitute another available business fact when
   the requested fact is unavailable.

6. If requested information exists in approved knowledge,
   answer directly.

7. If all specifically requested business information is
   unavailable, answer exactly:

   "{BUSINESS_FALLBACK}"

8. Never invent business facts.

9. Qualification statements are not business-information
   questions.

10. A qualification statement should be acknowledged
    naturally.

11. Do not change qualification merely because a customer
    asks a factual question about AWS or Azure.

12. If the CURRENT message explicitly mentions AWS, use
    AWS business knowledge for that business question.

13. If the CURRENT message explicitly mentions Azure, use
    Azure business knowledge for that business question.

14. A saved interest must not override a provider explicitly
    named in the current business question.

15. Do not repeat unrelated conversation history.

16. Do not mention information the customer did not ask for.

17. Do not add unnecessary follow-up questions.

18. After answering a business-information question, STOP.

19. Keep the final response concise and direct.

20. Do not use Markdown bullet symbols such as *, -, or •
    in the final response.

21. If multiple services, topics, courses, or other items
    must be listed, put each item on a separate line with
    no symbol before it.

22. Never ask for interest, budget, timeline, or requirement
    when that field already has a value in CURRENT STRUCTURED
    QUALIFICATION.

Correct list format:

Amazon EC2
Amazon S3
IAM
VPC
EFS
RDS
Elastic Load Balancer
CloudWatch
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
    # 12. ADD LIMITED HISTORY
    # =========================

    if history:

        recent_history = (
            history[
                -MAX_LLM_HISTORY:
            ]
        )


        print(
            "\n------------------------------"
        )

        print(
            "LLM HISTORY OPTIMIZATION"
        )

        print(
            "------------------------------"
        )


        print(
            f"TOTAL STORED HISTORY: "
            f"{len(history)}"
        )


        print(
            f"HISTORY SENT TO LLAMA: "
            f"{len(recent_history)}"
        )


        for item in recent_history:


            # =========================
            # DATABASE ROLE → OLLAMA ROLE
            # =========================

            if item.role in (
                "lead",
                "user"
            ):

                ollama_role = (
                    "user"
                )


            elif item.role in (
                "ai",
                "assistant"
            ):

                ollama_role = (
                    "assistant"
                )


            else:

                continue


            messages.append(
                {
                    "role": ollama_role,
                    "content": item.message
                }
            )


    else:

        print(
            "\n------------------------------"
        )

        print(
            "LLM HISTORY OPTIMIZATION"
        )

        print(
            "------------------------------"
        )


        print(
            "TOTAL STORED HISTORY: 0"
        )


        print(
            "HISTORY SENT TO LLAMA: 0"
        )


    # =========================
    # 13. REINFORCE CURRENT REQUEST
    # =========================

    current_interest = (
        qualification.get(
            "interest"
        )
        if qualification
        else None
    )


    current_budget = (
        qualification.get(
            "budget"
        )
        if qualification
        else None
    )


    current_timeline = (
        qualification.get(
            "timeline"
        )
        if qualification
        else None
    )


    current_requirement = (
        qualification.get(
            "requirement"
        )
        if qualification
        else None
    )


    messages.append(
        {
            "role": "system",
            "content": f"""
CURRENT CUSTOMER MESSAGE:

{prompt}

CURRENT STRUCTURED QUALIFICATION:

Interest: {current_interest}

Budget: {current_budget}

Timeline: {current_timeline}

Requirement: {current_requirement}

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

13. Do not use *, -, •, or any Markdown bullet symbol
    in the final response.

14. When listing multiple items, put each item on its
    own separate line without a bullet symbol.

15. Never ask for a qualification field that already has
    a value in CURRENT STRUCTURED QUALIFICATION.

Example:

Amazon EC2
Amazon S3
IAM
VPC
EFS
RDS
Elastic Load Balancer
CloudWatch
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


    prompt_build_time = (
        time.perf_counter()
        - prompt_build_start
    )


    print(
        f"PROMPT BUILD TIME: "
        f"{prompt_build_time:.3f} seconds"
    )


    # =========================
    # 15. GENERATE AI RESPONSE
    # =========================

    try:

        print(
            "\n------------------------------"
        )


        print(
            "OLLAMA GENERATION"
        )


        print(
            "------------------------------"
        )


        ollama_start = (
            time.perf_counter()
        )


        response = ollama.chat(
            model="llama3.2:3b",
            messages=messages,
            options={
                "temperature": 0,
                "num_predict": 150
            }
        )


        ollama_time = (
            time.perf_counter()
            - ollama_start
        )


        print(
            f"OLLAMA CHAT TIME: "
            f"{ollama_time:.3f} seconds"
        )


        ai_message = (
            response[
                "message"
            ][
                "content"
            ]
        )


        if (
            not ai_message
            or not ai_message.strip()
        ):

            raise RuntimeError(
                "Ollama returned an empty response"
            )


        # =========================
        # CLEAN RESPONSE FORMAT
        # =========================

        ai_message = (
            clean_response_format(
                ai_message
            )
        )


        total_llm_time = (
            time.perf_counter()
            - total_llm_start
        )


        print(
            f"TOTAL LLM TIME: "
            f"{total_llm_time:.3f} seconds"
        )


        return ai_message


    # =========================
    # OLLAMA CONNECTION FAILURE
    # =========================

    except ConnectionError as error:

        print(
            f"Ollama connection error: "
            f"{error}"
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
            f"{type(error).__name__}: "
            f"{error}"
        )


        raise RuntimeError(
            "AI service is temporarily unavailable"
        ) from error