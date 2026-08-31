"""Deterministic course recommendations for structured profile turns (no LLM).

Ranking is catalog-aware: official JSON title/level fields are scored against
experience / department / goal. Hybrid retrieval contributes a boost when the
same course_id appears in the vector+BM25 results, but is not the sole ranker.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from llama_index.core.schema import NodeWithScore, QueryBundle

from src.chatbot.course_cards import format_course_card_from_metadata
from src.chatbot.query_context import UserProfile, build_user_profile
from src.ingestion.course_catalog import apply_official_catalog, get_course, load_course_catalog

logger = logging.getLogger(__name__)

# Keep template recs on by default; set CHAT_TEMPLATE_PROFILE_RECS=false to force LLM.
_TEMPLATE_ENABLED = os.getenv("CHAT_TEMPLATE_PROFILE_RECS", "true").lower() in (
    "1",
    "true",
    "yes",
)
_MAX_COURSES = int(os.getenv("CHAT_TEMPLATE_RECS_MAX", "5"))
_MIN_COURSES = 1
# Weight of normalized retrieval score relative to catalog fit.
_RETRIEVAL_BLEND = float(os.getenv("CHAT_TEMPLATE_RECS_RETRIEVAL_BLEND", "0.55"))
# Max courses that share the same title stem (reduces near-duplicate lists).
_MAX_PER_STEM = int(os.getenv("CHAT_TEMPLATE_RECS_MAX_PER_STEM", "2"))

_WS_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s/+-]+")

# Department → primary title keywords (strong topic match).
# Prefer multi-word / domain phrases over bare tokens that false-match other fields.
_DEPT_PRIMARY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "finance": (
        "budget",
        "financial",
        "finance",
        "accounting",
        "appropriations",
        "appropriation",
        "fiscal",
        "funds control",
        "treasury",
        "cost accounting",
        "federal financial",
        "cfo",
        "dod fm",
        "defense financial",
        "working capital",
        "reimbursable",
    ),
    "it": (
        "information technology",
        "it acquisition",
        "it project",
        "cybersecurity",
        "cyber",
        "software",
        "data analytics",
        "data science",
        "data management",
        "cloud",
        "digital transformation",
        "information security",
        "enterprise architecture",
    ),
    "management": (
        "leadership",
        "supervisory",
        "supervisor",
        "management skills",
        "program management",
        "project management",
        "performance management",
        "emotional intelligence",
        "conflict management",
        "conflict resolution",
        "executive leadership",
        "strategic leadership",
        "team leadership",
        "non-managers",
        "non managers",
    ),
}

# Related but secondary (still on-topic, weaker weight than primary).
_DEPT_SECONDARY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "finance": (
        "audit",
        "internal controls",
        "internal control",
        "gao",
        "yellow book",
        "grants",
        "cost-reimbursement",
        "cost reimbursement",
    ),
    "it": (
        "information systems",
        "devops",
        "configuration management",
        "agile scrum",
        "agile project",
        "agile techniques",
        "agile contracting",
        "agile services",
        "agile practices",
        "agile requirements",
    ),
    "management": (
        "facilitation",
        "coaching skills",
        "human resources",
        "hr management",
        "communication skills",
        "leading teams",
        "team building",
    ),
}

# Combined list used when expanding the retrieval query.
_DEPT_TITLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    key: _DEPT_PRIMARY_KEYWORDS.get(key, ()) + _DEPT_SECONDARY_KEYWORDS.get(key, ())
    for key in ("finance", "it", "management")
}

_GOAL_TITLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "certification": (
        "certif",
        "fac-",
        "fac ",
        "fac/",
        "pmp",
        "capm",
        "cpa",
        "cdf",
        "defense financial",
        "dod fm",
        "professional certification",
    ),
    "promotion": (
        "leadership",
        "leader",
        "supervisor",
        "supervisory",
        "manager",
        "strategic",
        "executive",
        "core competenc",
    ),
    "upskill": (
        "skills",
        "fundamentals",
        "essentials",
        "workshop",
        "applied",
        "practitioner",
    ),
    "personal growth": (
        "skills",
        "fundamentals",
        "essentials",
        "workshop",
        "communication",
        "emotional intelligence",
    ),
}

_SOFT_PENALTY_TERMS = (
    "coaching",
    "accelerator",
    "package",
    "mentoring",
    "executive coach",
    "individual coaching",
    "performance accelerator",
)

# Generic title tokens ignored when building diversity stems.
_STEM_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "of",
        "for",
        "to",
        "in",
        "on",
        "with",
        "federal",
        "government",
        "advanced",
        "introduction",
        "intro",
        "basics",
        "basic",
        "overview",
        "workshop",
        "course",
        "program",
        "using",
        "your",
        "new",
    }
)


def template_profile_recs_enabled() -> bool:
    return _TEMPLATE_ENABLED


# Free-chat phrasing that means "rank courses for this ask" — not a fact lookup.
_REC_REQUEST_RE = re.compile(
    r"\b("
    r"recommend(ations?)?|"
    r"suggest(ions?)?|"
    r"looking for|"
    r"what (courses|classes|training)|"
    r"what .{0,40}(courses|classes|training)|"
    r"which courses|"
    r"(give me |show me |need )?(a )?list (of )?(courses|classes|training)|"
    r"(give|show|send|find) me (some |a few |a )?(courses|classes|recommendations|course|class|training)|"
    r"courses (for me|best suited|suited for|based on|do you offer|you offer)|"
    r"best (suited|courses|classes)|"
    r"suited for my (experience|profile|prefs|preferences|department|goal)|"
    r"based on my (profile|experience|prefs|preferences)|"
    r"please recommend|"
    r"i (want|need) (a |the )?(course|class|training|certification|cert|pmp|capm)"
    r")\b",
    re.IGNORECASE,
)

# Short topic asks (e.g. "PMP", "budgeting") that should still get catalog cards.
_TOPIC_QUERY_RE = re.compile(
    r"\b("
    r"pmp|capm|pmi|"
    r"budget(ing)?|appropriations?|"
    r"project management|program management|"
    r"leadership|supervisory|"
    r"acquisition|contracting|procurement|"
    r"agile|scrum|cybersecurity|"
    r"federal financial|grants?|"
    r"fac[- ]?p/?pm|fac[- ]?cor|"
    r"exam prep|certification prep"
    r")\b",
    re.IGNORECASE,
)

_CHITCHAT_RE = re.compile(
    r"^(hi|hello|hey|thanks|thank you|ok|okay|yo|"
    r"good (morning|afternoon|evening)|how are you)[\s!.?]*$",
    re.IGNORECASE,
)

_QUERY_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "for",
        "to",
        "in",
        "on",
        "with",
        "course",
        "courses",
        "class",
        "classes",
        "training",
        "workshop",
        "please",
        "recommend",
        "recommendation",
        "recommendations",
        "suggest",
        "suggestion",
        "suggestions",
        "show",
        "give",
        "need",
        "want",
        "looking",
        "find",
        "list",
        "some",
        "few",
        "best",
        "suited",
        "based",
        "my",
        "me",
        "i",
        "you",
        "do",
        "offer",
        "available",
        "what",
        "which",
        "that",
        "this",
        "about",
        "from",
        "your",
        "experience",
        "department",
        "career",
        "goal",
        "level",
        "profile",
        "prefs",
        "preferences",
    }
)


def looks_like_recommendation_request(message: str | None) -> bool:
    """True when the learner is asking for a ranked course list, not a single-course fact."""
    text = (message or "").strip()
    if not text:
        return False
    return _REC_REQUEST_RE.search(text) is not None


def looks_like_topic_query(message: str | None) -> bool:
    """True for short topic asks that should get catalog cards without a profile interview."""
    text = (message or "").strip()
    if not text or len(text) > 140:
        return False
    if _CHITCHAT_RE.match(text):
        return False
    return _TOPIC_QUERY_RE.search(text) is not None


def _metadata_profile_complete(meta: dict[str, Any]) -> bool:
    profile = meta.get("profile") if isinstance(meta.get("profile"), dict) else {}
    return all((meta.get(k) or profile.get(k)) for k in ("experience", "department", "goal"))


def should_use_template_recommendations(
    request_metadata: dict[str, Any] | None,
    *,
    latest_message: str | None = None,
) -> bool:
    """True when this turn should return catalog course cards (no LLM).

    Fires on an explicit rec/list ask or a short topic query. A complete
    learner profile is optional — it only improves ranking when present.
    """
    if not template_profile_recs_enabled():
        return False
    meta = request_metadata or {}
    if looks_like_recommendation_request(latest_message):
        return True
    if looks_like_topic_query(latest_message):
        return True
    # Legacy profile-complete payloads still skip the LLM.
    if meta.get("profile_complete") is True:
        return True
    if meta.get("step") == "goal" and _metadata_profile_complete(meta):
        return True
    return False


def build_profile_search_query(profile: UserProfile) -> str:
    """Build a retrieval query from structured prefs (no chat history needed)."""
    parts: list[str] = []
    dept_key = _department_key(profile.department)
    if dept_key and dept_key in _DEPT_TITLE_KEYWORDS:
        # Prefer catalog-aligned phrases so hybrid retrieval surfaces on-topic IDs.
        parts.append(" ".join(_DEPT_TITLE_KEYWORDS[dept_key][:6]))
    elif profile.department:
        parts.append(f"{profile.department} training courses")
    if profile.experience:
        parts.append(f"{profile.experience} experience")
    if profile.goal:
        parts.append(f"career goal {profile.goal}")
    if not parts:
        parts.append("Management Concepts course recommendations")
    parts.append("recommend core catalog courses")
    return " ".join(parts)


def _official_metadata(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Apply the same official catalog overlay used in RAG postprocessing."""
    metadata = dict(raw or {})
    metadata = apply_official_catalog(metadata)
    # Prefer full official entry when present so title/duration/level/price are canonical.
    course_id = metadata.get("course_id")
    if course_id:
        entry = get_course(course_id)
        if entry:
            if entry.get("title"):
                metadata["course_title"] = entry["title"]
                metadata["title"] = entry["title"]
            for key in ("duration", "level", "credits", "url", "price"):
                if entry.get(key):
                    metadata[key] = entry[key]
    # Price fill from price catalog when still missing (same as CourseMetadataPostprocessor).
    try:
        from src.ingestion.pricing import apply_catalog_prices

        metadata = apply_catalog_prices(metadata)
    except Exception:
        pass
    return metadata


def format_course_card(
    metadata: dict[str, Any],
    *,
    description: str = "",
    why: str | None = None,
) -> str | None:
    """Render one course card: title → duration / credits / cost."""
    return format_course_card_from_metadata(
        metadata,
        description=description,
        why=why,
        include_credits=True,
    )


def _norm(value: str | None) -> str:
    return _WS_RE.sub(" ", (value or "").strip().lower())


def _department_key(department: str | None) -> str | None:
    """Map free-text / chip department labels to a scoring key.

    Uses exact match first, then word-boundary contains — never raw substring
    (``"it" in "facilities"`` would otherwise false-positive).
    """
    dept = _norm(department)
    if not dept:
        return None
    # Exact chip / alias match.
    if dept in _DEPT_TITLE_KEYWORDS:
        return dept
    aliases = {
        "information technology": "it",
        "information tech": "it",
        "fin": "finance",
        "mgmt": "management",
        "mgr": "management",
    }
    if dept in aliases:
        return aliases[dept]
    for key in _DEPT_TITLE_KEYWORDS:
        # Whole-word / phrase match only (boundaries avoid "it" inside other words).
        if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", dept):
            return key
    return None


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    """Count keyword hits with longest-match-first de-dupe.

    Overlapping needles (e.g. cyber / cybersecurity, appropriation /
    appropriations) count once so compound titles are not double-boosted.
    """
    if not text:
        return 0
    # Longest first so "cybersecurity" claims the span before "cyber".
    ordered = sorted({kw.lower() for kw in keywords if kw}, key=len, reverse=True)
    claimed: list[tuple[int, int]] = []
    hits = 0
    for needle in ordered:
        if len(needle) <= 2:
            pattern = rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])"
        else:
            # Phrase / multi-char: allow match inside punctuation-normalized text.
            pattern = re.escape(needle)
        for match in re.finditer(pattern, text):
            start, end = match.span()
            if any(not (end <= cs or start >= ce) for cs, ce in claimed):
                continue
            claimed.append((start, end))
            hits += 1
            break  # one span per keyword is enough for ranking
    return hits


def department_topic_score(entry: dict[str, Any], profile: UserProfile) -> float:
    """How well the course title matches the learner's department (0 = no match)."""
    dept_key = _department_key(profile.department)
    if not dept_key:
        return 0.0
    title = _norm(str(entry.get("title") or entry.get("course_title") or ""))
    primary_hits = _keyword_hits(title, _DEPT_PRIMARY_KEYWORDS.get(dept_key, ()))
    secondary_hits = _keyword_hits(title, _DEPT_SECONDARY_KEYWORDS.get(dept_key, ()))
    if primary_hits <= 0 and secondary_hits <= 0:
        return 0.0
    if primary_hits > 0:
        # Core department vocabulary (budget/IT/leadership) outranks adjacent topics.
        return 1.15 + 0.22 * min(primary_hits - 1, 4) + 0.08 * min(secondary_hits, 2)
    # Secondary-only (e.g. audit under Finance) — on-topic but weaker.
    return 0.55 + 0.12 * min(secondary_hits - 1, 3)


def level_fit_score(entry: dict[str, Any], profile: UserProfile) -> float:
    """Align official catalog level with experience band."""
    level = _norm(str(entry.get("level") or ""))
    exp = _norm(profile.experience)
    if not exp:
        return 0.0

    if "entry" in exp or re.search(r"\b0\b", exp) or "0–2" in exp or "0-2" in exp:
        if level in ("basic", "overview", "entry"):
            return 1.0
        if level == "intermediate":
            return 0.3
        if level == "advanced":
            return -0.7
        return 0.05

    if "senior" in exp or "manager" in exp or "8+" in exp or "8 +" in exp:
        if level == "advanced":
            return 1.0
        if level == "intermediate":
            return 0.55
        if level in ("basic", "overview", "entry"):
            return -0.3
        # Untitled levels often include leadership programs — mild positive.
        return 0.15

    # Mid-level (3–7 years) and anything else defaulting to mid.
    if level == "intermediate":
        return 1.0
    if level in ("basic", "advanced"):
        return 0.35
    if level in ("overview", "entry"):
        return 0.15
    return 0.1


def goal_fit_score(entry: dict[str, Any], profile: UserProfile) -> float:
    """Light title boost for career-goal intent.

    Compound chip goals (e.g. \"Upskill / personal growth\") may match more than
    one key — take the best score so secondary intent keywords still apply.
    """
    goal = _norm(profile.goal)
    if not goal:
        return 0.0
    title = _norm(str(entry.get("title") or entry.get("course_title") or ""))
    best = 0.0
    matched_any_key = False
    for key, keywords in _GOAL_TITLE_KEYWORDS.items():
        if key not in goal:
            continue
        matched_any_key = True
        hits = _keyword_hits(title, keywords)
        if hits:
            best = max(best, 0.35 + 0.1 * min(hits - 1, 2))
    if matched_any_key:
        return best
    # Unmapped free-text goal: tiny boost if goal words appear in title.
    tokens = [t for t in re.split(r"[^a-z0-9]+", goal) if len(t) >= 4]
    if any(t in title for t in tokens):
        return 0.2
    return 0.0


def penalty_score(entry: dict[str, Any]) -> float:
    """Down-rank coaching packages / accelerators for generic onboarding recs."""
    title = _norm(str(entry.get("title") or entry.get("course_title") or ""))
    penalty = 0.0
    for term in _SOFT_PENALTY_TERMS:
        if term in title:
            penalty -= 0.9
            break
    # Multi-day "Program" immersions are often packages, not single courses.
    if "immersion" in title or title.endswith(" program") or " program (" in title:
        penalty -= 0.35
    return penalty


def catalog_profile_fit(entry: dict[str, Any], profile: UserProfile) -> float:
    """Combined catalog-only fit score (department + level + goal − penalties)."""
    topic = department_topic_score(entry, profile)
    level = level_fit_score(entry, profile)
    goal = goal_fit_score(entry, profile)
    penalty = penalty_score(entry)

    score = topic + 0.55 * level + goal + penalty
    # Without a department, lean on level/goal only and avoid large positives.
    if not _department_key(profile.department):
        score = 0.55 * level + goal + penalty + 0.15
    return score


def query_title_score(entry: dict[str, Any], query: str | None) -> float:
    """How well the course title matches the learner's free-text ask."""
    q = _NON_ALNUM_RE.sub(" ", _norm(query))
    title = _NON_ALNUM_RE.sub(
        " ",
        _norm(str(entry.get("title") or entry.get("course_title") or "")),
    )
    if not q.strip() or not title.strip():
        return 0.0
    if q.strip() in title:
        return 2.4
    tokens = [
        t for t in q.split() if t and t not in _QUERY_STOPWORDS and len(t) >= 2
    ]
    if not tokens:
        return 0.0
    hits = 0
    for token in tokens:
        if len(token) <= 3:
            if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", title):
                hits += 1
        elif token in title:
            hits += 1
    if hits <= 0:
        return 0.0
    return 0.55 * hits + 1.2 * (hits / len(tokens))


def _title_stem(title: str) -> str:
    """First content word(s) for light diversity (e.g. 'budget' vs 'acquisition')."""
    cleaned = _NON_ALNUM_RE.sub(" ", _norm(title))
    tokens = [t for t in cleaned.split() if t and t not in _STEM_STOPWORDS and len(t) > 2]
    if not tokens:
        return cleaned[:24] or "course"
    # Use first two content tokens when available for slightly finer buckets.
    return " ".join(tokens[:2])


def _hard_level_mismatch(entry: dict[str, Any], profile: UserProfile) -> bool:
    """True when catalog level clearly conflicts with experience band."""
    level = _norm(str(entry.get("level") or ""))
    exp = _norm(profile.experience)
    if not level or not exp:
        return False
    if "entry" in exp or re.search(r"\b0\b", exp) or "0–2" in exp or "0-2" in exp:
        return level == "advanced"
    if "senior" in exp or "manager" in exp or "8+" in exp or "8 +" in exp:
        return level in ("basic", "overview", "entry")
    return False


def _retrieval_scores_by_course_id(
    nodes: list[NodeWithScore],
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for node_with_score in nodes:
        meta = dict(node_with_score.node.metadata or {})
        # Prefer official overlay for id consistency, but don't require full catalog I/O here.
        course_id = str(meta.get("course_id") or "").strip()
        if not course_id:
            continue
        score = float(node_with_score.score or 0.0)
        prev = scores.get(course_id)
        if prev is None or score > prev:
            scores[course_id] = score
    return scores


def rank_courses_for_profile(
    profile: UserProfile,
    retrieved_nodes: list[NodeWithScore] | None = None,
    *,
    max_courses: int | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """Rank official catalog courses; blend in hybrid-retrieval scores when present.

    ``query`` (the learner's current ask) boosts title matches so recs work
    without an onboarding profile.

    Returns official metadata dicts (course_id, title, duration, …), best first.
    """
    limit = max_courses if max_courses is not None else _MAX_COURSES
    catalog = load_course_catalog()
    retrieval = _retrieval_scores_by_course_id(retrieved_nodes or [])
    max_ret = max(retrieval.values()) if retrieval else 0.0

    dept_key = _department_key(profile.department)
    scored: list[tuple[float, str, dict[str, Any]]] = []

    # Score full catalog so weak retrieval cannot trap us in off-topic nodes.
    for course_id, entry in catalog.items():
        topic = department_topic_score(entry, profile)
        in_retrieval = course_id in retrieval
        qscore = query_title_score(entry, query)

        # Candidate gate: on-topic for department, query title hit, or retrieval.
        if dept_key and topic <= 0 and not in_retrieval and qscore <= 0:
            continue
        if (
            not dept_key
            and not in_retrieval
            and qscore <= 0
            and catalog_profile_fit(entry, profile) < 0.4
        ):
            continue

        fit = catalog_profile_fit(entry, profile)
        ret_norm = 0.0
        if max_ret > 0 and course_id in retrieval:
            ret_norm = max(0.0, retrieval[course_id] / max_ret)

        total = fit + _RETRIEVAL_BLEND * ret_norm + qscore
        # Retrieved but off-topic for a known department: keep only if still competitive.
        if dept_key and topic <= 0 and in_retrieval and qscore <= 0:
            total = 0.2 * fit + 0.35 * ret_norm
            if total < 0.35:
                continue

        scored.append((total, course_id, entry))

    scored.sort(key=lambda item: item[0], reverse=True)

    selected: list[dict[str, Any]] = []
    stem_counts: dict[str, int] = {}
    seen_ids: set[str] = set()
    deferred_mismatch: list[tuple[float, str, dict[str, Any]]] = []

    def _try_append(course_id: str, entry: dict[str, Any]) -> bool:
        if course_id in seen_ids:
            return False
        stem = _title_stem(str(entry.get("title") or ""))
        if stem_counts.get(stem, 0) >= _MAX_PER_STEM:
            return False
        # Drop heavily penalized packages unless the list would otherwise be empty.
        if penalty_score(entry) <= -0.8 and len(selected) >= _MIN_COURSES:
            return False
        metadata = _official_metadata({"course_id": course_id, **entry})
        if not format_course_card(metadata, description=""):
            return False
        seen_ids.add(course_id)
        stem_counts[stem] = stem_counts.get(stem, 0) + 1
        selected.append(metadata)
        return True

    for total, course_id, entry in scored:
        if len(selected) >= limit:
            break
        if _hard_level_mismatch(entry, profile):
            deferred_mismatch.append((total, course_id, entry))
            continue
        _try_append(course_id, entry)

    # Fill remaining slots with level-mismatched courses only if needed.
    if len(selected) < limit:
        for _total, course_id, entry in deferred_mismatch:
            if len(selected) >= limit:
                break
            _try_append(course_id, entry)

    # Fallback: retrieval-only path if catalog gate yielded nothing (e.g. empty catalog).
    if len(selected) < _MIN_COURSES and retrieval:
        for course_id, _ret in sorted(retrieval.items(), key=lambda kv: kv[1], reverse=True):
            if course_id in seen_ids:
                continue
            entry = catalog.get(course_id) or {"course_id": course_id}
            metadata = _official_metadata({"course_id": course_id, **entry})
            if not format_course_card(metadata, description=""):
                continue
            selected.append(metadata)
            seen_ids.add(course_id)
            if len(selected) >= limit:
                break

    return selected


def nodes_to_course_cards(
    nodes: list[NodeWithScore],
    profile: UserProfile,
    *,
    max_courses: int | None = None,
    query: str | None = None,
) -> list[str]:
    """Dedupe by course_id, catalog-rank, apply official fields, format cards."""
    ranked = rank_courses_for_profile(
        profile, nodes, max_courses=max_courses, query=query
    )
    cards: list[str] = []
    for metadata in ranked:
        card = format_course_card(metadata, description="")
        if card:
            cards.append(card)
    return cards


def build_intro(profile: UserProfile) -> str:
    focus = []
    if profile.department:
        focus.append(profile.department)
    if profile.experience:
        focus.append(profile.experience)
    if profile.goal:
        focus.append(profile.goal)
    if focus:
        return (
            "Based on your profile ("
            + " · ".join(focus)
            + "), here are courses from the Management Concepts catalog:"
        )
    return "Here are Management Concepts courses that match what you asked:"


def build_empty_reply(profile: UserProfile) -> str:
    dept = profile.department or "your area"
    return (
        f"I couldn't find a strong catalog match for {dept} just now. "
        "Try a follow-up with topics like budgeting, project management, "
        "leadership, or a specific course ID."
    )


def retrieve_recommendation_nodes(
    profile: UserProfile,
    *,
    query: str | None = None,
) -> list[NodeWithScore]:
    """Run the same hybrid retrieve + postprocess stack as the chat engine."""
    from src.chatbot.chatbot import get_index
    from src.chatbot.query_context import build_metadata_filters
    from src.chatbot.retrieval import create_hybrid_retriever, create_node_postprocessors

    search_query = query or build_profile_search_query(profile)
    metadata_filters = build_metadata_filters(profile)
    retriever = create_hybrid_retriever(
        get_index(),
        metadata_filters=metadata_filters,
        profile=profile,
    )
    nodes = retriever.retrieve(search_query)
    query_bundle = QueryBundle(query_str=search_query)
    # Template recs: catalog ranks in Python; skip cross-encoder to keep onboarding fast.
    for postprocessor in create_node_postprocessors(skip_rerank=True):
        nodes = postprocessor.postprocess_nodes(nodes, query_bundle=query_bundle)
    return nodes


def build_template_recommendation_reply(
    *,
    latest_message: str | None = None,
    request_metadata: dict[str, Any] | None = None,
    chat_history: list | None = None,
) -> str:
    """Full no-LLM recommendation reply for a profile-complete turn."""
    profile = build_user_profile(
        chat_history,
        latest_message=latest_message,
        request_metadata=request_metadata,
    )
    search_query = (latest_message or "").strip() or build_profile_search_query(profile)
    nodes: list[NodeWithScore] = []
    try:
        nodes = retrieve_recommendation_nodes(profile, query=search_query)
    except Exception as exc:
        # Catalog ranking can still produce solid recs without retrieval.
        logger.warning(
            "Template recommendation retrieval failed; ranking catalog only: %s",
            exc,
            exc_info=True,
        )

    cards = nodes_to_course_cards(nodes, profile, query=search_query)
    if len(cards) < _MIN_COURSES:
        return build_empty_reply(profile)

    return build_intro(profile) + "\n\n" + "\n\n".join(cards)
