"""
Lazo Agent — Escalation & Contact Capture Tools

Tools for handing off to human agents and capturing customer
contact information when no agents are available.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool


@tool
async def escalate_to_agent(
    reason: str,
    priority: str = "normal",
    conversation_summary: Optional[str] = None,
) -> str:
    """Escalate the conversation to a human agent.

    Use this when:
    - The customer explicitly asks to speak with a person
    - You cannot resolve the issue with available tools
    - The situation requires human judgment (complaints, complex returns, etc.)
    - You've attempted multiple approaches and the customer is unsatisfied

    The system will automatically check if agents are online.
    If yes, it routes to them live. If not, it captures contact info
    and creates an inbox item for follow-up.

    Args:
        reason: Brief description of why escalation is needed
        priority: Priority level (low, normal, high, urgent)
        conversation_summary: Summary of the conversation so far for the agent
    """
    from app.services.escalation_service import escalation_service

    result = await escalation_service.escalate(
        reason=reason,
        priority=priority,
        conversation_summary=conversation_summary,
    )

    if result.get("agent_available"):
        return (
            "I've connected you with a team member who will take it from here. "
            "They have the full context of our conversation."
        )
    else:
        return (
            "Our team is not available right now, but I want to make sure "
            "someone follows up with you. Could you please share your email "
            "or phone number so we can reach out to you?"
        )


@tool
async def capture_contact_info(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    name: Optional[str] = None,
    note: Optional[str] = None,
) -> str:
    """Capture customer contact information for follow-up.

    Use this AFTER the customer provides their contact details when
    no agents are available. This creates an inbox item so the team
    can follow up later.

    Args:
        email: Customer's email address
        phone: Customer's phone number
        name: Customer's name
        note: Any additional context about what the customer needs
    """
    if not email and not phone:
        return (
            "I need at least an email address or phone number to ensure "
            "our team can reach you. Could you please provide one?"
        )

    from app.services.inbox_service import inbox_service

    result = await inbox_service.create_inbox_item(
        contact_email=email,
        contact_phone=phone,
        contact_name=name,
        note=note,
    )

    contact_method = email or phone
    return (
        f"Thank you! I've saved your contact information ({contact_method}). "
        f"A member of our team will reach out to you within "
        f"{result.get('sla_hours', 2)} hours. "
        f"Your reference number is {result.get('reference_id', 'N/A')}."
    )
