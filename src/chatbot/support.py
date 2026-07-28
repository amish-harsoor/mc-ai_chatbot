"""
Technical-support / out-of-scope routing for non-course customer issues.

Course discovery continues through the normal RAG path. Account, password,
certificate generation, and explicit human-agent requests stay in-chat with
fixed acknowledgment replies — no page redirects.
"""

from __future__ import annotations

import re
from typing import Any, Literal

SupportKind = Literal["agent", "password", "certificate", "generic"]

# ---------------------------------------------------------------------------
# Customer-facing replies (in-chat only — no external page routing)
# ---------------------------------------------------------------------------

SUPPORT_PHONE = "844-876-7476"
SUPPORT_EMAIL = "technicalsupport@managementconcepts.com"

# Canonical technical-support contact copy (password / login / generic issues).
# Frontend shows a Speak with Agent chip when this message is used.
TECHNICAL_SUPPORT_CONTACT_MESSAGE = (
    "Please contact our technical support team at 844-876-7476, "
    "via email (technicalsupport@managementconcepts.com), "
    "or select Speak with Agent below and we'll connect you."
)

PASSWORD_CHANGE_MESSAGE = TECHNICAL_SUPPORT_CONTACT_MESSAGE

SPEAK_WITH_AGENT_OPTION = "Speak with Agent"

# After the learner already chose Speak with Agent — phone/email only (no chip CTA).
SPEAK_WITH_AGENT_CONFIRMATION = (
    "Please contact our technical support team at 844-876-7476, "
    "via email (technicalsupport@managementconcepts.com), "
    "or stay in this chat — we'll connect you with a specialist."
)

CERTIFICATE_REQUEST_MESSAGE = (
    "Your certificate request has been received. It will be generated shortly — "
    "you'll be notified when it's ready. "
    "If you need help, contact technical support at 844-876-7476 "
    "or technicalsupport@managementconcepts.com."
)

# Generic account / access / billing / site issues
SUPPORT_TICKET_MESSAGE = TECHNICAL_SUPPORT_CONTACT_MESSAGE

# ---------------------------------------------------------------------------
# Intent patterns
# ---------------------------------------------------------------------------

# Explicit human / agent requests
_AGENT_PATTERNS = [
    r"\bspeak with (an? )?(agent|representative|specialist|someone|person)\b",
    r"\btalk to (an? )?(agent|representative|specialist|someone|human|person|advisor)\b",
    r"\b(connect|transfer) me (to )?(an? )?(agent|human|person|representative)\b",
    r"\b(real|live) (person|agent|human|support)\b",
    r"\bhuman (agent|support|help)\b",
    r"\bcustomer service\b",
    r"\bcall me\b",
    r"\bphone support\b",
    r"^speak with agent$",
]

# Password change / reset (specific ticket wording)
_PASSWORD_PATTERNS = [
    r"\b(reset|change|forgot(ten)?|update)\s+(my\s+)?password\b",
    r"\bpassword\s+(reset|change|update|problem|issue)\b",
    r"\b(new|different)\s+password\b",
    r"\bcan'?t\s+(remember|find)\s+(my\s+)?password\b",
    r"\b(need|want)\s+to\s+(reset|change)\s+(my\s+)?password\b",
]

# Login / account access (generic ticket)
_LOGIN_PATTERNS = [
    r"\b(log ?in|login|sign[- ]?in|username|account (locked|access|issue|problem))\b",
    r"\bcan'?t (log ?in|access|sign[- ]?in|open|register|enroll)\b",
    r"\b(unable to|not able to) (log ?in|access|sign[- ]?in|open|register|enroll)\b",
]

# Print / generate certificates (service request — not course discovery)
_CERTIFICATE_PATTERNS = [
    r"\b(print|generate|download|issue|create|request|resend|re[- ]?issue)\b.{0,40}\b(certificate|certificates|cert)\b",
    r"\b(certificate|certificates|cert)\b.{0,40}\b(print|generate|download|issue|create|request|resend|re[- ]?issue)\b",
    r"\bmy (course )?certificate(s)?\b",
    r"\bcertificate of completion\b",
    r"\bneed (my |a |the )?(course )?certificate(s)?\b",
    r"\b(get|send|email)\s+(me\s+)?(my\s+)?(course\s+)?certificate(s)?\b",
    r"\b(certificate|transcript|receipt) (not|never) (received|arrived|showing)\b",
]

# Other non-catalog issues
_ISSUE_PATTERNS = [
    r"\b(billing|invoice|refund|payment failed|charge(d)?|credit card)\b",
    r"\b(website|site|page|portal|lms|dashboard) (is )?(down|broken|not working|error)\b",
    r"\b(error|bug|broken|glitch|not working|doesn'?t work|won'?t load)\b",
    r"\btechnical (support|issue|problem|error|difficulty|difficulties)\b",
    r"\b(having )?(trouble|problem|issue)s?\b.*\b(access|login|account|website|site|payment|enroll|password)",
    r"\b(cancel|cancellation) (my )?(registration|enrollment|order)\b",
    r"\b(complaint|escalate|manager)\b",
    r"\b(844[- ]?876[- ]?7476|technicalsupport@managementconcepts\.com)\b",
]

# Strong course-discovery signals — never treat these as support handoff
_COURSE_PATTERNS = [
    r"\b(course|courses|class|classes|training|catalog|curriculum|workshop)\b",
    r"\b(recommend|recommendation|suggest|what do you (offer|have)|looking for)\b",
    # "certification" as a learning goal / prep is course discovery, not cert printing
    r"\b(certification|budget(ing)?|project management|acquisition|contracting|leadership)\b",
    r"\b(duration|cost|price|tuition|online|in[- ]person|virtual)\b",
    r"\bmy (experience level|department|career goal) is\b",
    r"\bplease recommend courses\b",
    r"\bproduct/\d+\b",
    r"\bearn a certification\b",
]

_AGENT_RE = [re.compile(p, re.I) for p in _AGENT_PATTERNS]
_PASSWORD_RE = [re.compile(p, re.I) for p in _PASSWORD_PATTERNS]
_LOGIN_RE = [re.compile(p, re.I) for p in _LOGIN_PATTERNS]
_CERTIFICATE_RE = [re.compile(p, re.I) for p in _CERTIFICATE_PATTERNS]
_ISSUE_RE = [re.compile(p, re.I) for p in _ISSUE_PATTERNS]
_COURSE_RE = [re.compile(p, re.I) for p in _COURSE_PATTERNS]


def is_speak_with_agent_selection(message: str) -> bool:
    text = (message or "").strip().lower()
    return text in {
        "speak with agent",
        "speak with an agent",
        "talk to agent",
        "talk to an agent",
    }


def looks_like_course_query(message: str) -> bool:
    text = message or ""
    return any(p.search(text) for p in _COURSE_RE)


def looks_like_certificate_request(message: str) -> bool:
    """True for print/generate/download certificate service requests."""
    text = message or ""
    if not text.strip():
        return False
    return any(p.search(text) for p in _CERTIFICATE_RE)


def looks_like_password_request(message: str) -> bool:
    text = message or ""
    return any(p.search(text) for p in _PASSWORD_RE)


def classify_support_issue(
    message: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> SupportKind | None:
    """
    Return the support intent kind, or None when the message should use RAG.
    """
    if not message or not str(message).strip():
        return None

    meta = metadata or {}
    # Profile-complete onboarding always goes to course recommendations.
    if meta.get("profile_complete") or meta.get("step") == "goal":
        return None

    text = str(message).strip()

    if is_speak_with_agent_selection(text) or any(p.search(text) for p in _AGENT_RE):
        return "agent"

    # Certificate service requests win over broad course keywords when explicit.
    if looks_like_certificate_request(text):
        return "certificate"

    if looks_like_password_request(text):
        return "password"

    # Course intent wins over weak issue keywords (e.g. "support for budgeting courses").
    if looks_like_course_query(text):
        return None

    if any(p.search(text) for p in _LOGIN_RE):
        return "password"  # account access → same ticket-style handling

    if any(p.search(text) for p in _ISSUE_RE):
        return "generic"

    return None


def is_support_issue(
    message: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """
    Return True when the learner is raising a non-catalog issue that should
    get a fixed in-chat acknowledgment instead of RAG course advice.
    """
    return classify_support_issue(message, metadata=metadata) is not None


def support_reply_for_message(message: str) -> str:
    """Return the appropriate fixed in-chat acknowledgment for a support-bound message."""
    kind = classify_support_issue(message) or "generic"
    if kind == "agent" or is_speak_with_agent_selection(message):
        return SPEAK_WITH_AGENT_CONFIRMATION
    if kind == "password":
        return PASSWORD_CHANGE_MESSAGE
    if kind == "certificate":
        return CERTIFICATE_REQUEST_MESSAGE
    return SUPPORT_TICKET_MESSAGE


def support_options_for_message(message: str) -> list[str] | None:
    """
    Optional follow-up chips after a support reply.

    Certificate and agent confirmations need no extra chip.
    Password / generic tickets offer Speak with Agent as an in-chat escalate.
    """
    kind = classify_support_issue(message) or "generic"
    if kind in ("certificate", "agent") or is_speak_with_agent_selection(message):
        return None
    return [SPEAK_WITH_AGENT_OPTION]


# ---------------------------------------------------------------------------
# Out-of-domain (non-training) — fixed reply, no RAG
# ---------------------------------------------------------------------------

OUT_OF_DOMAIN_MESSAGE = (
    "I only help with Management Concepts courses and training. "
    "Try asking about budgeting, project management, leadership, "
    "or share your experience level, department, and career goal."
)

_OUT_OF_DOMAIN_PATTERNS = [
    r"\b(bake|baking|sourdough|recipe|cook(ing)?|kitchen|food|pizza|pasta)\b",
    r"\b(football|soccer|basketball|baseball|nba|nfl|world cup)\b",
    r"\b(weather|forecast|temperature outside)\b",
    r"\b(movie|netflix|spotify|video game|playstation|xbox)\b",
    r"\b(tell me a joke|write (me )?(a )?poem|sing (me )?(a )?song)\b",
    r"\b(dating advice|horoscope|astrology)\b",
    r"\b(bitcoin|crypto trading|stock tips)\b",
    r"\b(how to (fix|repair) (my )?(car|phone|laptop))\b",
]

_OOD_RE = [re.compile(p, re.I) for p in _OUT_OF_DOMAIN_PATTERNS]


def is_out_of_domain_message(
    message: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """True for clearly non-training topics that should not hit RAG."""
    if not message or not str(message).strip():
        return False

    meta = metadata or {}
    # Onboarding / profile recs always stay on the course path
    if meta.get("profile_complete") or meta.get("step") in (
        "goal",
        "experience",
        "department",
        "welcome",
    ):
        return False

    text = str(message).strip()
    if looks_like_course_query(text):
        return False
    if is_support_issue(text, metadata=metadata):
        return False

    return any(p.search(text) for p in _OOD_RE)


def out_of_domain_reply() -> str:
    return OUT_OF_DOMAIN_MESSAGE
