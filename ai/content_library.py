from typing import Optional, Dict, Any
from collections.abc import Iterable, Mapping

from ai.content_dedup import select_content_item_with_report
from ai.image_library import get_image_content

# =========================================================
# APPROVED EDUCATIONAL CONTENT
# =========================================================

EDUCATIONAL_CONTENT = {

    "AWS Cloud Engineering": (
        "AWS Cloud Engineering focuses on practical cloud skills. "
        "Skillect's approved AWS course topics include Amazon EC2, "
        "Amazon S3, IAM, VPC, EFS, RDS, Elastic Load Balancer, "
        "and CloudWatch."
    ),

    "Azure Cloud Engineering": (
        "Azure Cloud Engineering focuses on practical Microsoft Azure "
        "cloud services. Skillect's approved Azure course topics include "
        "Azure Virtual Machines, Blob Storage, Microsoft Entra ID, "
        "VNet, Azure SQL Database, Azure Load Balancer, and Azure Monitor."
    ),
}


# =========================================================
# APPROVED CAREER CONTENT
# =========================================================

CAREER_CONTENT = {

    "AWS Cloud Engineering": (
        "If you're building a career in cloud engineering, practical "
        "experience is important along with understanding AWS concepts. "
        "Skillect's AWS Cloud Engineering training includes practical "
        "cloud learning, interview preparation, and cloud project guidance."
    ),

    # We intentionally do not copy AWS-specific career-support claims
    # to Azure because those details are not currently approved.
    "Azure Cloud Engineering": (
        "If you're interested in Azure Cloud Engineering, Skillect offers "
        "a 3-month Azure Cloud Engineering course covering practical Azure "
        "services. Basic computer knowledge is enough to begin the training."
    ),
}


# =========================================================
# VERIFIED CONTENT TYPES
# =========================================================

VERIFIED_CONTENT_TYPES = {
    "industry_update",
    "newsletter",
    "image",
    "batch_update",
}


# =========================================================
# GET EDUCATIONAL CONTENT
# =========================================================

def get_educational_content(
    topic: Optional[str],
) -> Optional[str]:

    if not topic:
        return None

    return EDUCATIONAL_CONTENT.get(topic)


# =========================================================
# GET CAREER CONTENT
# =========================================================

def get_career_content(
    topic: Optional[str],
) -> Optional[str]:

    if not topic:
        return None

    return CAREER_CONTENT.get(topic)


# =========================================================
# GET CONTENT
# =========================================================

def get_content(
    content_type: Optional[str],
    topic: Optional[str],
    previously_used_identities: Optional[set[str]] = None,
    approved_items: Optional[Iterable[Mapping[str, Any] | str]] = None,
) -> Dict[str, Any]:

    if not content_type:

        return {
            "ready": False,
            "reason": "content_type_missing",
            "content_type": None,
            "topic": topic,
            "message": None,
        }

    content_type = content_type.lower().strip()
    previously_used_identities = (
        previously_used_identities or set()
    )
    approved_items_were_provided = approved_items is not None
    approved_items = list(approved_items or [])

    # -----------------------------------------------------
    # EDUCATIONAL
    # -----------------------------------------------------

    if content_type == "educational":

        approved_message = get_educational_content(topic)
        candidates = approved_items or (
            [approved_message]
            if approved_message
            else []
        )
        candidate_messages = [
            (
                candidate
                if isinstance(candidate, str)
                else candidate.get("message")
                or candidate.get("text")
                or candidate.get("content")
            )
            for candidate in candidates
        ]
        candidate_messages = [
            candidate
            for candidate in candidate_messages
            if candidate
        ]
        selected, identities, deduplication = select_content_item_with_report(
            content_type,
            candidate_messages,
            previously_used_identities,
        )
        message = selected if isinstance(selected, str) else None

        if not message:

            return {
                "ready": False,
                "reason": "approved_content_not_found",
                "content_type": content_type,
                "topic": topic,
                "message": None,
                "deduplication": deduplication,
            }

        return {
            "ready": True,
            "reason": "approved_content_found",
            "content_type": content_type,
            "topic": topic,
            "message": message,
            "content_identities": identities,
            "deduplication": deduplication,
        }

    # -----------------------------------------------------
    # CAREER TIP
    # -----------------------------------------------------

    if content_type == "career_tip":

        approved_message = get_career_content(topic)
        candidates = approved_items or (
            [approved_message]
            if approved_message
            else []
        )
        candidate_messages = [
            (
                candidate
                if isinstance(candidate, str)
                else candidate.get("message")
                or candidate.get("text")
                or candidate.get("content")
            )
            for candidate in candidates
        ]
        candidate_messages = [
            candidate
            for candidate in candidate_messages
            if candidate
        ]
        selected, identities, deduplication = select_content_item_with_report(
            content_type,
            candidate_messages,
            previously_used_identities,
        )
        message = selected if isinstance(selected, str) else None

        if not message:

            return {
                "ready": False,
                "reason": "approved_content_not_found",
                "content_type": content_type,
                "topic": topic,
                "message": None,
                "deduplication": deduplication,
            }

        return {
            "ready": True,
            "reason": "approved_content_found",
            "content_type": content_type,
            "topic": topic,
            "message": message,
            "content_identities": identities,
            "deduplication": deduplication,
        }

    if content_type == "image":
        image_result = get_image_content(
            topic,
            previously_used_identities=previously_used_identities,
            approved_items=(
                approved_items
                if approved_items_were_provided
                else None
            ),
        )
        if not image_result.get("ready"):
            return {
                **image_result,
                "content_type": content_type,
                "message": None,
            }

        image_url = image_result.get("image_url")
        image_id = image_result.get("image_id")
        metadata = {
            "image_id": image_id,
            "canonical_url": image_result.get("canonical_url"),
            "topic": image_result.get("topic"),
            "source": image_result.get("source"),
            "approved": image_result.get("approved"),
            "content_hash": image_result.get("content_hash"),
        }
        return {
            "ready": True,
            "reason": image_result["reason"],
            "content_type": content_type,
            "topic": topic,
            "message": image_url or image_id,
            "image_url": image_url,
            "image_metadata": metadata,
            "content_identities": image_result["content_identities"],
            "deduplication": image_result["deduplication"],
        }

    # -----------------------------------------------------
    # VERIFIED / EXTERNAL CONTENT
    #
    # Do NOT invent these using the LLM.
    # Later these will come from:
    #
    # industry_update -> trusted verified source
    # newsletter      -> approved content
    # batch_update    -> real batch data
    # -----------------------------------------------------

    if content_type in VERIFIED_CONTENT_TYPES:

        candidates = approved_items
        if content_type in {"industry_update", "newsletter"}:
            candidates = [
                item
                for item in candidates
                if isinstance(item, Mapping)
                and item.get("verified") is True
            ]
        prepared_candidates = []
        for item in candidates:
            if isinstance(item, str):
                if content_type == "image":
                    prepared_candidates.append(
                        {
                            "image_url": item,
                            "message": item,
                        }
                    )
                elif content_type == "batch_update":
                    raise ValueError(
                        "Batch update content must include a stable batch identifier"
                    )
                else:
                    prepared_candidates.append(item)
                continue

            item_message = (
                item.get("message")
                or item.get("summary")
                or item.get("text")
            )
            if item_message:
                prepared_candidates.append(
                    {
                        **item,
                        "message": item_message,
                    }
                )

        if prepared_candidates:
            selected, identities, deduplication = (
                select_content_item_with_report(
                content_type,
                prepared_candidates,
                previously_used_identities,
                )
            )
            if selected:
                message = (
                    selected
                    if isinstance(selected, str)
                    else selected.get("share_message")
                    or selected.get("message")
                )
                return {
                    "ready": True,
                    "reason": "approved_content_found",
                    "content_type": content_type,
                    "topic": topic,
                    "message": message,
                    "content_identities": identities,
                    "deduplication": deduplication,
                }

        _, _, deduplication = select_content_item_with_report(
            content_type,
            prepared_candidates,
            previously_used_identities,
        )
        return {
            "ready": False,
            "reason": "verified_content_required",
            "content_type": content_type,
            "topic": topic,
            "message": None,
            "deduplication": deduplication,
        }

    # -----------------------------------------------------
    # UNKNOWN CONTENT TYPE
    # -----------------------------------------------------

    return {
        "ready": False,
        "reason": "unsupported_content_type",
        "content_type": content_type,
        "topic": topic,
        "message": None,
    }