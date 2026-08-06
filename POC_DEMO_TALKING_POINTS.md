# MC AI Chatbot — POC Demo Talking Points & Must-Show Cases

Use this as a **checklist**, not a script. Cover every **must-show** case so nothing important is skipped. Optional cases if time allows.

**Audience framing (open with this):**

> This is a proof-of-concept for a **course discovery and advising assistant** on the Management Concepts site. Learners get guided recommendations from the real catalog, can ask follow-ups in free chat, and can request support without leaving the widget. Live agent transfer and certificate fulfillment are **scripted acknowledgments** in this POC — not yet wired to CRM/ticketing.

---

## 0. Pre-demo setup (do before the call)

- [ ] Backend is running and `GET /health` returns `{"status":"ok"}`
- [ ] Frontend `VITE_API_BASE_URL` points at the **same host/port** as the API
- [ ] Widget opens; FAB visible; first open starts a session without errors
- [ ] Network tab (optional): confirm `/session/start` and `/chat/stream` succeed
- [ ] Use a **fresh browser profile / clear site data** if you need a clean first-time journey
- [ ] Keep one tab ready for **session restore** (do not clear storage mid-demo unless intentional)

**Suggested local start (adjust ports to match your env):**

```bash
# API
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# UI
cd frontend/ChatbotUI
# ensure VITE_API_BASE_URL matches API
npm run dev
```

---

## 1. Opening talking points (1–2 minutes)

Say these early so the rest of the demo lands:

| # | Point | Why it matters |
|---|--------|----------------|
| 1 | **Drop-in widget** on a site-like page — same pattern as embedding on managementconcepts.com | Integration story |
| 2 | **RAG over the real course catalog** (Postgres/pgvector) — not inventing courses | Trust / accuracy |
| 3 | **Guided onboarding** (experience → department → goal) then **personalized recommendations** | Conversion / UX |
| 4 | **Free chat** after onboarding for natural questions | Flexibility |
| 5 | **Course cards** with title, duration, credits, cost (when known), **Register Now** deep link | Actionable |
| 6 | **Support stays in-chat** (password, login, agent, certificates) with MC phone/email | Deflection + handoff path |
| 7 | **Sessions + guest identity** so history can restore on return | Continuity |
| 8 | **API-first service** — FastAPI microservice; host apps call HTTP; optional React widget | Architecture / buy-in |

**Do not oversell:**

- “Speak with Agent” = in-chat confirmation + contact info, **not** a live queue.
- Certificate “generated shortly” = acknowledgment only in this POC.
- LLM answers for free chat can vary slightly; structured recs are more deterministic.

---

## 2. Must-show demo cases (in recommended order)

Complete these in order for a clean narrative (~8–12 minutes).

### Case A — First impression & widget UX

| | |
|--|--|
| **Goal** | Show polish and embeddability |
| **Steps** | Load demo page → point out site backdrop → click FAB → open panel |
| **Call out** | MC branding (colors/logo), header, message timestamps, smooth open animation |
| **Pass criteria** | Widget opens; welcome + experience chips appear; no error toast/blank screen |

**Talking point:** *“This is the learner-facing surface. Backend is separate, so the same API can power LMS, portal, or marketing site.”*

---

### Case B — Guided onboarding (experience → department → goal)

| | |
|--|--|
| **Goal** | Show structured intake without free-text friction |
| **Suggested path** | Experience: **Mid-level (3–7 years)** → Department: **Finance** → Goal: **Get a promotion** |
| **Alternate path** (if client cares about IT/entry) | Entry-level → IT → Earn a certification |
| **Call out** | Chips lock free-text until a step is chosen; each selection is saved as a real chat turn; profile bar can fill as prefs land |
| **Pass criteria** | Three steps advance cleanly; after goal, recommendations stream in |

**Talking points:**

- *“We capture experience, department, and career goal so recommendations match level and domain.”*
- *“Selections are persisted on the session so we can personalize later turns and restore state.”*

**Chip values available (don’t invent others in demo):**

| Step | Options |
|------|---------|
| Experience | Entry-level (0–2 years), Mid-level (3–7 years), Senior/Manager (8+ years) |
| Department | Finance, Management, IT |
| Goal | Earn a certification, Get a promotion, Upskill / personal growth |

---

### Case C — Profile-based course recommendations

| | |
|--|--|
| **Goal** | Show the primary value: relevant catalog courses with actionable CTAs |
| **When** | Immediately after completing Case B (goal selection) |
| **Call out** | 3–5 courses; card layout (title, **Duration**, **Credits**, **Cost** when present); **[Register Now]** → managementconcepts.com product URL; no invented course IDs |
| **Pass criteria** | Real-looking courses for the chosen department/level; links work; cards are readable |

**Talking points:**

- *“Recommendations are grounded in catalog context — we require real course IDs from the knowledge base.”*
- *“For the completed profile turn we use a fast, structured recommendation path so the client sees low latency and consistent card formatting.”*
- *“Register Now is a direct product link, so the next step is enrollment, not more chat.”*

**If recs look weak:** retry with a different department (e.g. Management) rather than apologizing at length — then continue free chat.

---

### Case D — Preference bar (edit prefs without restarting)

| | |
|--|--|
| **Goal** | Show mid-conversation preference updates |
| **Steps** | With a complete profile, use the preference bar (experience / department / goal chips) → change **department** or **goal** → wait for updated recommendations or acknowledgment |
| **Call out** | Flash/highlight on save; no need to re-run full onboarding from scratch |
| **Pass criteria** | UI reflects new pref; bot responds with updated guidance/recs |

**Talking point:** *“Learners change their mind. Prefs are editable in place so the advisor stays in the flow.”*

---

### Case E — Free-chat follow-up (RAG)

| | |
|--|--|
| **Goal** | Show natural language Q&A after onboarding |
| **Prompts to try (pick 1–2)** | |
| | “What budgeting courses do you recommend for someone in finance?” |
| | “Do you have online project management courses?” |
| | “Something more entry-level / more advanced?” |
| | “How long is [a course title you just recommended]?” |
| **Call out** | Streaming tokens; markdown bullets; still catalog-grounded; conversational tone without long filler |
| **Pass criteria** | Relevant reply streams; courses (if listed) still have sensible cards/links |

**Talking point:** *“After intake, this behaves like a normal advisor — hybrid retrieval over the catalog, not a static FAQ.”*

---

### Case F — Single-course / catalog fact lookup

| | |
|--|--|
| **Goal** | Show precise catalog answers without hallucination |
| **Prompts** | “What is the cost of course 4606?” / “Tell me about course 4606” (or any ID visible from a prior card) |
| **Call out** | Deterministic catalog path when a concrete course ID is asked; official title/duration/price when available |
| **Pass criteria** | Specific course facts returned; no random unrelated courses |

**Talking point:** *“When the learner already has a course ID, we can answer from the official catalog data path rather than free-form invention.”*

---

### Case G — Support: password / login (in-chat ticket style)

| | |
|--|--|
| **Goal** | Show non-course issues stay in the widget |
| **Prompt** | “I forgot my password” or “I can’t log in to my account” |
| **Call out** | Fixed support copy with **844-876-7476** and **technicalsupport@managementconcepts.com**; **Speak with Agent** chip appears; free-text input remains usable |
| **Pass criteria** | Support message (not a list of courses); Speak with Agent option visible |

**Talking point:** *“Technical issues don’t dump the learner on a random help page mid-flow — they get contact paths and an agent option without leaving chat.”*

---

### Case H — Speak with Agent (scripted handoff)

| | |
|--|--|
| **Goal** | Show explicit human-request path |
| **Steps** | Click **Speak with Agent** (or type “Speak with Agent”) after Case G |
| **Call out** | Confirmation message with phone/email; chip goes away after confirmation; **POC: no live agent queue yet** |
| **Pass criteria** | Clear confirmation; contact info present |

**Talking point (honest):** *“In production this would open a ticket or transfer to live chat. Today the POC proves the **intent detection and UX**; the CRM hook is the next integration step.”*

---

### Case I — Certificate request (service request)

| | |
|--|--|
| **Goal** | Show service requests distinct from course discovery |
| **Prompt** | “I need to print my certificate” or “Please generate my certificate of completion” |
| **Call out** | Acknowledgment that request was received / will be generated; contact info if needed; **not** a list of certification-prep courses |
| **Pass criteria** | Certificate-style reply, not catalog recs |

**Talking point:** *“We separate ‘I want training’ from ‘I need my cert document’ so the bot doesn’t recommend courses when the learner wants fulfillment.”*

**Note:** Prefer this **after** free chat, or in a **new session**, so it doesn’t interrupt the happy-path recs narrative.

---

### Case J — Out-of-domain guardrail

| | |
|--|--|
| **Goal** | Show the bot does not invent courses for nonsense topics |
| **Prompt** | “What’s the best recipe for lasagna?” or “Who won the Super Bowl?” |
| **Call out** | Short decline; invites a training-related question; **no fake courses** |
| **Pass criteria** | Brief redirect to MC training scope |

**Talking point:** *“Scope control protects brand trust — we won’t invent catalog content for off-topic chatter.”*

---

### Case K — Session restore / welcome back

| | |
|--|--|
| **Goal** | Show continuity for returning learners |
| **Steps** | After some history exists: **refresh the page** (or close/reopen widget without clearing storage) → open chat again |
| **Call out** | Guest id in `localStorage`; history reloads; optional welcome-back cue; preference bar / step restored when possible |
| **Pass criteria** | Previous messages visible; no full amnesia |

**Talking point:** *“Anonymous learners get a stable guest id; registered users can pass `user_id` from the host app for durable profiles across devices.”*

---

## 3. Optional showcase cases (if time / technical audience)

Use if stakeholders are engineering, product ops, or integration leads.

| Case | What to show | Sample / how |
|------|----------------|--------------|
| **L. Health & API docs** | Operability | Open `/health` and `/docs` (Swagger) |
| **M. Streaming contract** | Integration simplicity | Mention `POST /session/start` then `POST /chat/stream` (`text/plain` stream) |
| **N. Microservice options** | Fit to their stack | Standalone HTTP · mount FastAPI router · Django proxy · React widget |
| **O. Optional API key** | Basic service auth | `CHATBOT_API_KEY` + `X-API-Key` (if configured) |
| **P. Ingest path** | Content ops | `POST /ingest` file or URL / CLI ingest — “catalog can be refreshed without redeploying the UI” |
| **Q. Preference-driven re-rec after free chat** | Personalization depth | Change goal to “Earn a certification” and show shift in suggestions |
| **R. Billing / site issue support** | Broader support routing | “My payment failed” or “the website is not loading” → generic support + agent chip |
| **S. Empty / edge handling** | Robustness | Don’t demo empty message (API rejects); mention graceful model-unavailable messaging if asked |

---

## 4. Suggested live agenda (12-minute default)

| Min | Block | Cases |
|-----|--------|--------|
| 0–1 | Framing + architecture one-liner | Opening points |
| 1–2 | Widget open | **A** |
| 2–5 | Onboarding + recommendations | **B, C** |
| 5–6 | Preference bar | **D** |
| 6–8 | Free chat + one catalog fact | **E, F** |
| 8–10 | Support + Speak with Agent | **G, H** |
| 10–11 | Out-of-domain or certificate | **J** or **I** |
| 11–12 | Refresh / welcome back | **K** |
| Buffer | Tech deep-dive | **L–P** as needed |

**If only 5 minutes:** **A → B → C → E → G → K**. Skip D, F, H, I, J verbally or show one screenshot.

---

## 5. Copy-paste prompt bank

Use these exact lines during the demo so routing stays reliable.

### Course discovery (free chat)

```
What budgeting courses do you recommend for finance?
Recommend project management courses for mid-level staff.
Do you have online leadership training?
Something more foundational for beginners.
```

### Catalog / facts

```
What is the cost of course 4606?
Tell me about course 4606.
```

### Support & handoff

```
I forgot my password.
I can't log in to my account.
Speak with Agent
I need to print my certificate.
My payment failed on the website.
```

### Out of domain

```
What's a good lasagna recipe?
Who won the World Cup?
```

### Avoid during live demo (can confuse the story)

- Vague one-word messages (“help”, “hi”) mid-onboarding before chips are done  
- Mixing “certificate of completion print” with “earn a certification” goal without explaining the difference  
- Promising live agent response times  

---

## 6. Architecture talking points (for technical stakeholders)

Keep to 30–60 seconds unless they dig in:

1. **Service boundary** — Chatbot is a FastAPI microservice; host app uses HTTP (or mounts the router).
2. **Session model** — `POST /session/start` → stream with `session_id` → `GET /session/{id}/history` on restore.
3. **Identity** — `guest_id` (widget) or `user_id` (registered host user); durable learner profile for prefs/stats.
4. **Answer paths (important)** — Support / out-of-domain / catalog lookup / template profile recs / LLM RAG — different paths for latency and accuracy.
5. **Retrieval** — Hybrid search + rerank over pgvector; catalog JSON + prices overlay for official fields.
6. **Streaming UX** — Tokens stream for free-chat; structured paths may return a full reply in one shot.
7. **Deploy** — Docker for API; React widget built with Vite (`VITE_API_BASE_URL`).

---

## 7. Honest limitations checklist (say if asked)

| Topic | POC reality | Future integration |
|-------|-------------|--------------------|
| Speak with Agent | Scripted confirmation + phone/email | CRM, Zendesk, live chat, queue |
| Certificates | Acknowledgment only | Fulfillment system / learner records |
| Auth | Optional API key; open CORS for demo | BFF + locked origins + SSO |
| Content freshness | Depends on last ingest / vector load | Scheduled catalog ingest pipeline |
| Multi-language | English-focused | Localization if required |
| Analytics | DB sessions/messages exist | Dashboards, conversion funnels |
| Human QA of every LLM free-chat answer | Not guaranteed | Evaluation harness, guardrails, human review |

---

## 8. Master checklist — “Did I show everything?”

Print or keep open during the call:

### Learner experience

- [ ] Widget open / branding (**A**)
- [ ] Full onboarding chips (**B**)
- [ ] Personalized course cards + Register Now (**C**)
- [ ] Preference bar edit (**D**)
- [ ] Free-chat follow-up streaming (**E**)
- [ ] Specific course ID / cost fact (**F**)
- [ ] Password/login support message (**G**)
- [ ] Speak with Agent confirmation (**H**)
- [ ] Certificate service request (**I**) *or* mention if skipped
- [ ] Out-of-domain refusal (**J**) *or* mention if skipped
- [ ] Refresh / session restore (**K**)

### Business / integration (at least mention)

- [ ] Real catalog grounding (not invented courses)
- [ ] In-chat support path with MC contact details
- [ ] API/microservice integration options
- [ ] POC vs production boundaries (agent, certs)

### Close

- [ ] Recap value: **discover → recommend → act (Register) → support without leaving chat**
- [ ] Ask: preferred host app (site / LMS / portal) and next pilot scope

---

## 9. One-line close

> *“This POC proves a branded, catalog-grounded course advisor with guided intake, free chat, and in-widget support routing — ready to plug into your site or LMS next, with live agent and certificate systems as the follow-on integrations.”*
)
