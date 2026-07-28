import re
from dataclasses import dataclass, field
from typing import Any

from llama_index.core.llms import ChatMessage
from llama_index.core.vector_stores import FilterCondition, FilterOperator, MetadataFilter, MetadataFilters

EXPERIENCE_PATTERN = re.compile(
    r"experience level is:\s*(.+?)(?:\.\s*please|\.\s*$|$)",
    re.IGNORECASE,
)
DEPARTMENT_PATTERN = re.compile(
    r"department is:\s*(.+?)(?:\.\s*please|\.\s*$|$)",
    re.IGNORECASE,
)
GOAL_PATTERN = re.compile(
    r"career goal is:\s*(.+?)(?:\.\s*please|\.\s*$|$)",
    re.IGNORECASE,
)
COURSE_ID_IN_QUERY_PATTERNS = (
    re.compile(
        r"course\s+(?:id\s+|number\s*:?\s*|#)?(\d{4,6})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|[^\d])(\d{4,6})(?=\s*(?:course|class|training)\b)",
        re.IGNORECASE,
    ),
    re.compile(r"course/id/(\d{4,6})\b", re.IGNORECASE),
    re.compile(r"Course\s+Number:\s*(\d{4,6})\b", re.IGNORECASE),
)
YEAR_LIKE_ID_PATTERN = re.compile(r"^20[12]\d$")


@dataclass
class UserProfile:
    experience: str | None = None
    department: str | None = None
    goal: str | None = None
    course_ids: list[str] = field(default_factory=list)
    source_types: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = []
        if self.experience:
            parts.append(f"Experience: {self.experience}")
        if self.department:
            parts.append(f"Department: {self.department}")
        if self.goal:
            parts.append(f"Career goal: {self.goal}")
        if self.course_ids:
            parts.append(f"Course IDs: {', '.join(self.course_ids)}")
        return "; ".join(parts)


def _clean_value(value: str) -> str:
    return value.strip().rstrip(".")


def extract_course_ids_from_text(text: str) -> list[str]:
    """Extract course IDs from explicit catalog references (not years or phone numbers)."""
    ids: list[str] = []
    for pattern in COURSE_ID_IN_QUERY_PATTERNS:
        ids.extend(pattern.findall(text))
    return list(
        dict.fromkeys(
            course_id
            for course_id in ids
            if course_id and not YEAR_LIKE_ID_PATTERN.match(course_id)
        )
    )


def _extract_from_text(text: str, profile: UserProfile) -> None:
    if match := EXPERIENCE_PATTERN.search(text):
        profile.experience = _clean_value(match.group(1))
    if match := DEPARTMENT_PATTERN.search(text):
        profile.department = _clean_value(match.group(1))
    if match := GOAL_PATTERN.search(text):
        profile.goal = _clean_value(match.group(1))
    profile.course_ids.extend(extract_course_ids_from_text(text))


def build_user_profile(
    chat_history: list[ChatMessage] | None = None,
    *,
    latest_message: str | None = None,
    request_metadata: dict[str, Any] | None = None,
) -> UserProfile:
    profile = UserProfile()

    for message in chat_history or []:
        _extract_from_text(message.content or "", profile)

    if latest_message:
        _extract_from_text(latest_message, profile)

    metadata = request_metadata or {}
    step = metadata.get("step")
    if step == "experience" and metadata.get("value"):
        profile.experience = str(metadata["value"])
    if step == "department" and metadata.get("value"):
        profile.department = str(metadata["value"])
    if step == "goal" and metadata.get("value"):
        profile.goal = str(metadata["value"])

    profile_data = metadata.get("profile")
    if isinstance(profile_data, dict):
        for key in ("experience", "department", "goal"):
            if profile_data.get(key):
                setattr(profile, key, str(profile_data[key]))

    for key in ("department", "experience", "goal"):
        if metadata.get(key) and not getattr(profile, key):
            setattr(profile, key, str(metadata[key]))

    if metadata.get("course_id"):
        profile.course_ids.append(str(metadata["course_id"]))

    if metadata.get("source_type"):
        profile.source_types.append(str(metadata["source_type"]))

    profile.course_ids = list(dict.fromkeys(profile.course_ids))
    profile.source_types = list(dict.fromkeys(profile.source_types))
    return profile


def build_metadata_filters(profile: UserProfile) -> MetadataFilters | None:
    """Build strict metadata filters only for high-confidence keys present in indexed chunks.

    Department and goals are handled via query rewriting instead, because most chunks
    do not carry structured department metadata.
    """
    filters: list[MetadataFilter] = []

    if len(profile.course_ids) == 1:
        filters.append(
            MetadataFilter(
                key="course_id",
                value=profile.course_ids[0],
                operator=FilterOperator.EQ,
            )
        )

    if profile.source_types:
        if len(profile.source_types) == 1:
            filters.append(
                MetadataFilter(
                    key="source_type",
                    value=profile.source_types[0],
                    operator=FilterOperator.EQ,
                )
            )
        else:
            for source_type in profile.source_types:
                filters.append(
                    MetadataFilter(
                        key="source_type",
                        value=source_type,
                        operator=FilterOperator.EQ,
                    )
                )

    if not filters:
        return None

    condition = FilterCondition.OR if len(filters) > 1 else FilterCondition.AND
    return MetadataFilters(filters=filters, condition=condition)


# Department → catalog-focused search phrases (keeps recs on-topic vs coaching/audit drift)
_DEPARTMENT_SEARCH_TERMS: dict[str, list[str]] = {
    "finance": [
        "federal financial management",
        "budget formulation execution accounting",
        "appropriations financial systems",
    ],
    "it": [
        "information technology IT project management",
        "IT systems cybersecurity data",
        "FAC-P/PM technology",
    ],
    "management": [
        "leadership supervisory management skills",
        "program management team leadership",
        "manager development",
    ],
}

_GOAL_SEARCH_TERMS: dict[str, list[str]] = {
    "certification": ["certification preparation FAC-P/PM DoD FM CAPM PMP"],
    "promotion": ["career advancement supervisory leadership core competencies"],
    "upskill": ["professional development skills growth"],
    "personal growth": ["professional development skills growth"],
}


def _norm_key(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def build_query_expansion_terms(profile: UserProfile) -> list[str]:
    """Profile-aware terms that bias retrieval toward core department catalog hits."""
    terms: list[str] = []
    dept = _norm_key(profile.department)
    if dept:
        # Match "finance", "it", or startswith for longer labels
        for key, phrases in _DEPARTMENT_SEARCH_TERMS.items():
            if key == dept or key in dept or dept in key:
                terms.extend(phrases)
                break
        else:
            terms.append(f"{profile.department} courses and training")

    exp = _norm_key(profile.experience)
    if exp:
        if "entry" in exp or "0" in exp:
            terms.append("foundational introductory overview fundamentals entry-level")
        elif "senior" in exp or "manager" in exp or "8" in exp:
            terms.append("advanced senior leadership strategic")
        elif "mid" in exp:
            terms.append("intermediate applied practitioner")

    goal = _norm_key(profile.goal)
    if goal:
        matched_goal = False
        for key, phrases in _GOAL_SEARCH_TERMS.items():
            if key in goal:
                terms.extend(phrases)
                matched_goal = True
                break
        if not matched_goal:
            terms.append(f"courses to help with {profile.goal}")

    # Prefer core classroom/self-study courses over coaching packages in generic recs
    if profile.department and not profile.course_ids:
        terms.append("Course Number catalog training class workshop seminar")

    if profile.course_ids:
        terms.extend(f"course {course_id} details" for course_id in profile.course_ids[:3])
    return terms