from pathlib import Path
import re


# =========================
# KNOWLEDGE FILE PATH
# =========================

KNOWLEDGE_FILE = (
    Path(__file__).parent
    / "knowledge"
    / "business_knowledge.txt"
)


# =========================
# LOAD BUSINESS KNOWLEDGE
# =========================

def load_business_knowledge() -> str:

    if not KNOWLEDGE_FILE.exists():
        return ""

    return KNOWLEDGE_FILE.read_text(
        encoding="utf-8"
    )


# =========================
# NORMALIZE TEXT
# =========================

def normalize_words(text: str) -> set[str]:

    words = re.findall(
        r"\b[a-zA-Z0-9]+\b",
        text.lower()
    )

    return set(words)


# =========================
# DETECT CLOUD PROVIDER
# =========================

def detect_provider(query: str) -> str | None:
    """
    Detect the cloud provider mentioned most recently
    in the query.

    This prevents old conversation history from
    overriding the provider in the current message.

    Example:

    Old history:
    "What is the Azure course duration?"

    Current message:
    "What is the AWS course duration?"

    Combined retrieval query may contain both Azure
    and AWS. Because AWS appears most recently,
    this function returns "aws".
    """

    query_lower = query.lower()

    aws_matches = list(
        re.finditer(
            r"\baws\b",
            query_lower
        )
    )

    azure_matches = list(
        re.finditer(
            r"\bazure\b",
            query_lower
        )
    )

    # Neither provider mentioned
    if not aws_matches and not azure_matches:
        return None

    # Only AWS mentioned
    if aws_matches and not azure_matches:
        return "aws"

    # Only Azure mentioned
    if azure_matches and not aws_matches:
        return "azure"

    # Both providers mentioned.
    # The most recently mentioned provider wins.
    last_aws_position = aws_matches[-1].start()
    last_azure_position = azure_matches[-1].start()

    if last_aws_position > last_azure_position:
        return "aws"

    return "azure"


# =========================
# EXTRACT KNOWLEDGE BLOCKS
# =========================

def get_knowledge_blocks() -> dict[str, str]:

    knowledge = load_business_knowledge()

    if not knowledge:
        return {
            "general": "",
            "aws": "",
            "azure": "",
            "rules": ""
        }

    upper_knowledge = knowledge.upper()

    aws_marker = "AWS CLOUD ENGINEERING"
    azure_marker = "AZURE CLOUD ENGINEERING"
    rules_marker = "IMPORTANT AI RULES"

    aws_start = upper_knowledge.find(
        aws_marker
    )

    azure_start = upper_knowledge.find(
        azure_marker
    )

    rules_start = upper_knowledge.find(
        rules_marker
    )

    # If expected headings are not found,
    # safely return the complete knowledge
    # as general knowledge.
    if aws_start == -1 or azure_start == -1:

        return {
            "general": knowledge.strip(),
            "aws": "",
            "azure": "",
            "rules": ""
        }

    # General information before AWS section
    general = knowledge[
        :aws_start
    ].strip()

    # AWS section ends where Azure starts
    aws = knowledge[
        aws_start:azure_start
    ].strip()

    # Azure section
    if (
        rules_start != -1
        and rules_start > azure_start
    ):

        azure = knowledge[
            azure_start:rules_start
        ].strip()

        rules = knowledge[
            rules_start:
        ].strip()

    else:

        azure = knowledge[
            azure_start:
        ].strip()

        rules = ""

    return {
        "general": general,
        "aws": aws,
        "azure": azure,
        "rules": rules
    }


# =========================
# EXPAND QUERY MEANING
# =========================

def expand_query(query: str) -> str:

    query_lower = query.lower()

    extra_words = []

    provider = detect_provider(query)

    # =========================
    # PROVIDER CONTEXT
    # =========================

    if provider == "azure":

        extra_words.extend([
            "azure",
            "cloud",
            "engineering"
        ])

    elif provider == "aws":

        extra_words.extend([
            "aws",
            "cloud",
            "engineering"
        ])

    # =========================
    # DURATION
    # =========================

    if (
        "how long" in query_lower
        or "duration" in query_lower
        or "length" in query_lower
    ):

        extra_words.extend([
            "course",
            "duration"
        ])

    # =========================
    # FEE / PRICE
    # =========================

    if (
        "how much" in query_lower
        or "fee" in query_lower
        or "price" in query_lower
        or "cost" in query_lower
    ):

        extra_words.extend([
            "course",
            "fee"
        ])

    # =========================
    # TOPICS / SERVICES
    # =========================

    if (
        "topic" in query_lower
        or "topics" in query_lower
        or "service" in query_lower
        or "services" in query_lower
        or "what will i learn" in query_lower
        or "what do i learn" in query_lower
        or "syllabus" in query_lower
    ):

        extra_words.extend([
            "topics",
            "services",
            "covered"
        ])

    # =========================
    # TRAINING MODE
    # =========================

    if (
        "online" in query_lower
        or "offline" in query_lower
        or "training mode" in query_lower
        or "mode of training" in query_lower
    ):

        extra_words.extend([
            "training",
            "mode"
        ])

    # =========================
    # PREREQUISITES
    # =========================

    if (
        "prerequisite" in query_lower
        or "prerequisites" in query_lower
        or "requirement to join" in query_lower
        or "before joining" in query_lower
    ):

        extra_words.extend([
            "prerequisites",
            "computer",
            "knowledge"
        ])

    # =========================
    # CAREER SUPPORT
    # =========================

    if (
        "career support" in query_lower
        or "interview preparation" in query_lower
        or "job support" in query_lower
    ):

        extra_words.extend([
            "career",
            "support",
            "interview",
            "project",
            "guidance"
        ])

    # =========================
    # CERTIFICATION
    # =========================

    if (
        "certificate" in query_lower
        or "certification" in query_lower
        or "certification exam" in query_lower
        or "certification examination" in query_lower
        or "international certification" in query_lower
    ):

        extra_words.extend([
            "certification",
            "certificate",
            "examination",
            "training",
            "preparation",
            "support"
        ])

    # =========================
    # NUMBER OF COURSES
    # =========================

    if (
        "how many" in query_lower
        or "number of courses" in query_lower
        or "courses available" in query_lower
    ):

        extra_words.extend([
            "cloud",
            "engineering",
            "courses",
            "available",
            "total",
            "number"
        ])

    if extra_words:

        return (
            query
            + " "
            + " ".join(extra_words)
        )

    return query


# =========================
# SCORE KNOWLEDGE BLOCK
# =========================

def score_block(
    query: str,
    block: str
) -> int:

    if not block:
        return 0

    expanded_query = expand_query(
        query
    )

    query_words = normalize_words(
        expanded_query
    )

    block_words = normalize_words(
        block
    )

    return len(
        query_words.intersection(
            block_words
        )
    )


# =========================
# RETRIEVE RELEVANT KNOWLEDGE
# =========================

def retrieve_relevant_knowledge(
    query: str
) -> str:

    blocks = get_knowledge_blocks()

    general = blocks["general"]
    aws = blocks["aws"]
    azure = blocks["azure"]
    rules = blocks["rules"]

    provider = detect_provider(
        query
    )

    # =========================
    # AWS-SPECIFIC QUESTION
    # =========================

    if provider == "aws":

        selected = []

        if general:
            selected.append(
                general
            )

        if aws:
            selected.append(
                aws
            )

        if rules:
            selected.append(
                rules
            )

        return "\n\n".join(
            selected
        )


    # =========================
    # AZURE-SPECIFIC QUESTION
    # =========================

    if provider == "azure":

        selected = []

        if general:
            selected.append(
                general
            )

        if azure:
            selected.append(
                azure
            )

        if rules:
            selected.append(
                rules
            )

        return "\n\n".join(
            selected
        )


    # =========================
    # GENERAL COURSE QUESTION
    # =========================

    query_lower = query.lower()

    if (
        "how many" in query_lower
        or "courses available" in query_lower
        or "number of courses" in query_lower
        or "cloud engineering courses" in query_lower
    ):

        selected = []

        if general:
            selected.append(
                general
            )

        if rules:
            selected.append(
                rules
            )

        return "\n\n".join(
            selected
        )


    # =========================
    # NO PROVIDER SPECIFIED
    # =========================

    scored_blocks = []

    if general:

        scored_blocks.append(
            (
                score_block(
                    query,
                    general
                ),
                general
            )
        )

    if aws:

        scored_blocks.append(
            (
                score_block(
                    query,
                    aws
                ),
                aws
            )
        )

    if azure:

        scored_blocks.append(
            (
                score_block(
                    query,
                    azure
                ),
                azure
            )
        )

    scored_blocks.sort(
        key=lambda item: item[0],
        reverse=True
    )

    relevant_blocks = [
        block
        for score, block in scored_blocks
        if score > 0
    ][:2]

    if rules:
        relevant_blocks.append(
            rules
        )

    return "\n\n".join(
        relevant_blocks
    )