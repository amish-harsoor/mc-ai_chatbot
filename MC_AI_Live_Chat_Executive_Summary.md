# MC AI Live Chat — Case Document

**Prepared for:** Management Concepts  
**Product:** MC AI Live Chat (Course Advisor)  
**Document type:** Executive summary + technical overview  
**Status:** Current implementation (preference-centered architecture)

---

## Executive Summary

MC AI Live Chat is a conversational course advisor built for Management Concepts. Learners describe their training needs in plain language and receive recommendations drawn directly from the current course catalog, including course titles, direct links, duration, cost, and delivery format when available.

The tool begins with a short onboarding sequence on experience level, department, and goal. It then presents a focused list of relevant courses and refines those suggestions through natural follow-up questions. All recommendations remain strictly within the actual catalog; the system does not create courses or process enrollment.

**What makes this release durable is the preference layer.** Every conversation is owned by either a registered user or a stable guest. Full chat history is retained so a session can be restored after a page reload. At the same time, the system continuously captures experience, department, goal, delivery preference, course interest, and topics into a durable learner profile. That profile carries forward so returning visitors do not re-enter the same answers, and it becomes the foundation for future recommendation, analytics, CRM, and LMS work.

The objective is to shorten the time from initial interest to identification of suitable courses. This benefits learners through faster guidance, internal teams through reduced repetitive inquiries, and the organization by establishing a foundation for future integration with identity, catalog, sales, and learning systems.

---

## The Challenge

Course catalogs at this scale are inherently difficult to browse. Learners typically encounter one or more of the following patterns:

- **Scrolling and guessing:** Without deep familiarity with catalog structure, users must infer category names, titles, or keywords and frequently miss well-matched options.
- **Waiting on a human advisor:** When self-service search fails, the fallback involves delays, repeated context explanations, and back-and-forth communication via email or phone.
- **Repetitive staff workload:** Many questions follow predictable patterns, yet each currently consumes individual staff time even though the underlying logic is repeatable.
- **Drop-off from friction:** Every extra click, dead-end search, or wait for a reply creates an opportunity for an interested learner to abandon the process.
- **Lost context across visits:** Without a durable preference store, every return visit restarts discovery from zero — even when the learner already stated experience, department, and goals.

These patterns create a discovery bottleneck at the precise moment when learner interest and intent are highest.

---

## Solution Approach and Current Capabilities

The tool delivers an always-available conversational advisor through a branded chat widget embedded on the website, internal portal, or LMS. It operates under firm guardrails: every recommendation corresponds to an actual catalog entry, off-topic questions are redirected, and genuinely complex cases or enrollment transactions are referred to human advisors.

### Current product capabilities

- Interpreting course questions expressed in everyday language, without requiring catalog terminology, department codes, or exact titles.
- Recommending real courses with direct links and essential details: title, duration, cost, and format whenever that information exists in the catalog.
- Conducting a brief three-step onboarding sequence (experience level, department, career goal) that generates relevant initial recommendations without lengthy forms.
- Supporting natural follow-up refinements in plain language, such as requests for virtual-only delivery or more entry-level content, and adjusting the recommendation set in place.
- **Saving preferences automatically** for both anonymous guests and logged-in users so returning visitors do not need to repeat experience, department, or goal.
- Restoring an active conversation if the learner reloads the page mid-session.
- Presenting a consistent, on-brand floating chat button wherever learners already work.
- Staying scoped to course guidance and gently redirecting questions that fall outside that purpose.
- Allowing catalog content updates to flow into recommendations without requiring product redevelopment.

### Current technical capabilities (high level)

| Layer | What it does |
|-------|----------------|
| Chat widget | Onboarding UI, live streaming answers, guest continuity, session restore |
| Advisor service | Conversational API layer that host apps or the widget can call |
| Catalog intelligence (RAG) | Grounds answers in the real catalog via search + language model |
| Preference memory | Captures and reuses learner context across sessions |
| Knowledge store | Holds catalog content and conversation/preference history |

---

## Example Conversation Flow

A typical session follows this sequence:

```text
Open chat
  → Experience level
  → Department
  → Career goal
  → Ranked course recommendations (with links, duration, cost when known)
  → Optional free-text follow-ups
  → Click-through to a course page
```

**What is remembered along the way (automatic, not opt-in):**

| Step | Conversation history | Learner preferences |
|------|----------------------|---------------------|
| Experience selected | Turn is saved | Experience is stored |
| Department selected | Turn is saved | Department is stored |
| Goal selected + first recs | Full exchange is saved | Goal is stored; profile is treated as complete |
| Free-chat follow-ups | Every turn is saved | Topics and interest signals accumulate |
| Return visit | Prior thread can be restored; new session can start personalized | Experience / department / goal can be reused |

Partial onboarding steps are recorded without needing a full AI recommendation call. The first full recommendation happens when the goal step completes and enough profile context is available.

---

## Conversation Flow

A typical session follows a clear sequence: open the chat, select experience level, select department, state the underlying goal, receive a short ranked list of course recommendations, refine through follow-up questions if desired, and click through to a specific course page.

The three initial questions quickly establish context. Each recommendation includes course code, title, duration, cost, and a brief explanation of how it supports the stated goal. Follow-up messages adjust the existing recommendation list rather than restarting the process. The natural conclusion of a successful conversation is a direct transition from the chat widget to the chosen course page on the site.

This structure balances the need for relevant first suggestions with the flexibility of an ongoing conversation that still feels personal rather than form-driven.

Because preferences are saved per learner (guest or registered), the next session can open already knowing who they are in catalog terms — without forcing them through the same form again when a profile already exists.

---

## Preference & Identity System (central capability)

Preference saving is the **central product capability** of this system. Chat answers create immediate value; saved preferences turn every conversation into durable learner intelligence.

### Design principles

1. **Always keep the full conversation** — so history can be restored and reviewed.
2. **Always update preferences** — not opt-in; onboarding and free chat both enrich the profile over time.
3. **Support two identity modes** — logged-in users (host-app identity) and anonymous guests (stable browser identity).
4. **Prefer registered identity when available** — a guest conversation can later attach to a logged-in account.
5. **Separate “what was said” from “what we know about the learner”** — full transcripts for continuity; compact preferences for personalization, analytics, and future integrations.

### What is stored about the learner

| Signal | Source | Why it matters |
|--------|--------|----------------|
| Experience level | Onboarding | Matches seniority and course depth |
| Department | Onboarding | Aligns recommendations to functional area |
| Career goal | Onboarding | Frames why they are shopping for training |
| Delivery preference | Follow-up conversation | Filters virtual vs in-person and similar needs |
| Courses of interest | Conversation signals | Tracks which offerings they engaged with |
| Topics explored | Free-chat questions | Captures emerging interests beyond the form |

A profile is treated as **complete** once experience, department, and goal are all known.

### How it works in practice

```text
Learner uses chat (guest or logged in)
        │
        ▼
Conversation is saved in full
        │
        ▼
Preferences are condensed from onboarding + chat
        │
        ▼
Durable learner profile is updated
        │
        ▼
Next visit can restore history and reuse preferences
```

- **Guests** keep continuity through a stable browser identifier (no account required).
- **Registered users** keep continuity through the host application’s user identity.
- **New sessions** can open already personalized when a durable profile exists.
- **Return visits** avoid re-asking known basics and produce more relevant first recommendations.

### Why this is the central thing

| Concern | How preferences address it |
|---------|----------------------------|
| Personalization | Experience, department, and goal steer what the advisor surfaces first |
| Continuity | Returning visitors skip re-stating basics when a profile exists |
| Intent capture | Structured data for catalog planning and marketing without relying only on raw transcripts |
| Future recommendations | Goals, topics, and course interest are already available as ranking inputs |
| Integration readiness | The same learner profile model can connect later to CRM, LMS, and identity systems |
| Efficiency | Early onboarding steps do not require a full AI recommendation; the first recs fire when the profile is ready |

---

## Technical Architecture (overview)

### How the pieces fit together

```text
┌──────────────────────────────┐
│  Website / portal / LMS      │
│  Branded floating chat       │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  MC AI Course Advisor        │
│  Conversational service      │
│  • Sessions & history        │
│  • Preference memory         │
│  • Catalog-grounded answers  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  Knowledge & memory store    │
│  • Course catalog content    │
│  • Conversation history      │
│  • Learner preferences       │
└──────────────────────────────┘
```

### Integration options

| Approach | When it fits |
|----------|--------------|
| **Standalone service** (recommended) | Deploy the advisor independently; any host app talks to it over HTTP |
| **Embed in an existing backend** | Mount the advisor into a larger application stack when preferred |
| **Chat widget** | Drop-in branded UI for website, portal, or LMS surfaces |

Host applications never need to own catalog search or model plumbing — they open a session, stream answers, and optionally pass registered user identity.

### Technology stack (summary)

| Layer | Approach |
|-------|----------|
| User experience | React floating chat widget |
| Service layer | Modern web API service |
| Recommendation engine | Retrieval-augmented generation over the real catalog (search + language model) |
| Catalog grounding | Vector search combined with keyword search and ranking |
| Memory | Conversation history + durable learner preferences |
| Models | Configurable LLM and embedding providers |
| Deployment | Container-ready microservice; can also run as a local service |

### How a recommendation is produced

1. **Catalog knowledge** is kept current by ingesting course materials (documents or web content) into the knowledge store.
2. **Learner context** comes from the short onboarding profile and ongoing chat.
3. **Search** finds relevant catalog entries (not invented courses).
4. **Generation** produces a concise, streaming answer with course titles, links, and key details when known.
5. **Memory** saves the exchange and updates preferences for the next visit.

### Guardrails built into the system

- Answers stay scoped to Management Concepts course discovery.
- Course identifiers, titles, costs, and durations are taken from catalog context — not invented.
- Off-topic questions are redirected.
- Empty or unusable model responses fall back to a safe, on-brand reply.
- Preferences update continuously in the background without requiring a separate “save profile” step from the learner.

---

## Audiences, Benefits, and Current Limitations

The advisor is designed to serve multiple groups simultaneously:

| Audience | Primary benefit |
|----------|-----------------|
| Website visitors | Instant guidance with no account creation required; guest preferences still persist across visits in the same browser. |
| Logged-in users | Advice and durable profile that follow them across visits. |
| Internal teams | Consistent guidance layer on web, portal, or LMS through the same service. |
| Catalog owners | Recommendations stay current as courses change, without rebuilding the product for each update. |
| Product / analytics | Structured preference data (experience, department, goal, topics, course interest) without waiting for CRM integration. |

### Current limitations (intentional scope)

- It does not replace human advisors for complex or unusual situations; those cases remain best handled by people.
- It does not answer random questions outside course discovery and redirects conversations that drift outside that lane.
- It does not invent or recommend courses that are not present in the catalog; all suggestions are grounded in real, current offerings.
- It does not yet read from or write to CRM or LMS records directly; the preference model is the intentional bridge for that work.
- Guest continuity depends on the same browser; clearing site data starts a new guest identity unless the learner later logs in.
- Preference capture from free chat is intentionally lightweight and reliable, not a full advanced intent graph.

---

## Roadmap

The current release is intentionally scoped as a focused first step. Future opportunities are staged as follows:

| Horizon | Opportunities |
|---------|----------------|
| **Near term** | Automatic catalog refresh so new or changed courses flow into recommendations without manual steps; analytics on conversation patterns and preference aggregates; richer use of durable profiles in ranking; smoother guest-to-registered continuity. |
| **Medium term** | LMS next-step suggestions for enrolled learners; CRM and sales assistance using condensed profiles; enrollment handoff; multi-course learning paths driven by stored goals and topics; human handoff; signals for catalog content gaps. |
| **Longer term** | Proactive notifications based on evolving learner profiles; team and organizational package recommendations for L&D buyers; partner portal integrations; mobile and voice access; full ROI tracking from first message through inquiry to completed enrollment. |

This staged approach begins with solving the immediate discovery problem, uses **saved preferences as the shared memory layer**, moves to deeper integration across digital touchpoints, and later positions the system as a broader learner intelligence layer that feeds signal into marketing, sales, and learning operations.

---

## Business Value and Success Indicators

The following table connects organizational needs to the capabilities that address them and suggests observable indicators for evaluating impact.

| Need | How addressed | Potential indicator |
|------|---------------|---------------------|
| Scale advising | Always-on help for common questions reduces dependence on staff availability and business hours. | Reduction in volume of repetitive advising tickets or inquiries. |
| Less catalog friction | Conversation replaces endless browsing and keyword guessing. | Increase in course page views originating from chat; lower rate of abandoned searches. |
| Better relevance | Structured onboarding combined with **saved preferences** produces suggestions tailored to the individual. | Higher learner-reported relevance or satisfaction; lower re-onboarding rate for return visits. |
| Capture intent | Every conversation collects structured data on experience level, department, goals, and topics of interest. | New dataset available to inform catalog planning and marketing; growth of complete profiles. |
| Embed where learners already are | The same advisor works across website, portal, and LMS. | Consistent experience and usage metrics across all surfaces. |
| Trustworthy offers | All recommendations are grounded in real, current catalog content. | Low rate of reported mismatches between recommendations and available courses. |
| Continuity without a login wall | Guest identity + durable preferences give personalization without forcing account creation first. | Return-visit completion rate; share of sessions that reuse an existing profile. |

---

## Bottom Line

**MC AI Live Chat** is an always-on, catalog-grounded course advisor with a **preference-centered design**:

1. **Discover** — conversational onboarding and free chat turn interest into a short list of real courses.  
2. **Remember** — full conversation history plus durable learner preferences for guests and registered users.  
3. **Integrate later** — the same preference model is the bridge to identity, CRM, LMS, analytics, and enrollment.

Today it solves discovery friction. The preference system is what makes every conversation an asset for the next visit and for the broader Management Concepts digital ecosystem.
