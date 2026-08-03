import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Open+Sans:ital,wght@0,400;0,600;0,700;1,400&display=swap');

  .chatbot-root {
    font-family: 'Open Sans', sans-serif;
  }

  .chat-fab {
    position: fixed;
    bottom: 28px;
    right: 28px;
    width: 60px;
    height: 60px;
    border-radius: 12px;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #9A1B22;
    box-shadow: 0 8px 32px rgba(154,27,34,0.35), 0 2px 8px rgba(0,0,0,0.18);
    transition: transform 0.25s cubic-bezier(.34,1.56,.64,1), box-shadow 0.25s ease;
    z-index: 9999;
  }
  .chat-fab:hover {
    transform: scale(1.05);
    box-shadow: 0 12px 40px rgba(154,27,34,0.45), 0 4px 12px rgba(0,0,0,0.2);
  }

  .chat-window {
    position: fixed;
    bottom: 104px;
    right: 28px;
    width: 428px;
    height: 620px;
    max-height: calc(100vh - 130px);
    background: #ffffff;
    border-radius: 12px;
    box-shadow:
      0 12px 48px rgba(0,0,0,0.15),
      0 4px 16px rgba(0,0,0,0.08),
      0 0 0 1px rgba(0,0,0,0.05);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    z-index: 9998;
    transform-origin: bottom right;
    transition: opacity 0.3s cubic-bezier(.4,0,.2,1),
                transform 0.3s cubic-bezier(.34,1.56,.64,1);
  }
  .chat-window.open   { opacity: 1; transform: scale(1) translateY(0);      pointer-events: all; }
  .chat-window.closed { opacity: 0; transform: scale(0.88) translateY(16px); pointer-events: none; }

  .chat-header {
    background: #9A1B22;
    padding: 16px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex: 0 0 auto;
    color: white;
  }
  .header-left {
    display: flex; align-items: center; gap: 10px;
  }
  .mc-logo-svg {
    width: 32px; height: 32px;
  }
  .mc-logo-text {
    display: flex; flex-direction: column; line-height: 1.1;
  }
  .mc-logo-top { font-weight: 700; font-size: 15px; font-style: italic; letter-spacing: 0.5px; }
  .mc-logo-bottom { font-weight: 600; font-size: 13px; letter-spacing: 1px; }

  .header-right {
    display: flex; align-items: center; gap: 12px;
  }
  .header-icon-btn {
    background: transparent; border: none;
    color: white; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    padding: 4px; opacity: 0.9;
  }
  .header-icon-btn:hover { opacity: 1; }

  .chat-messages {
    flex: 1 1 0;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 24px 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    background: #ffffff;
    scroll-behavior: smooth;
  }
  .chat-messages::-webkit-scrollbar       { width: 6px; }
  .chat-messages::-webkit-scrollbar-track  { background: transparent; }
  .chat-messages::-webkit-scrollbar-thumb  { background: rgba(0,0,0,0.1); border-radius: 8px; }

  .msg-wrapper {
    display: flex;
    flex-direction: column;
    gap: 4px;
    animation: msg-in 0.28s cubic-bezier(.4,0,.2,1) both;
  }
  @keyframes msg-in {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .msg-meta {
    display: flex; align-items: center; gap: 8px;
    margin-left: 56px; margin-bottom: 2px;
  }
  .msg-meta.user { margin-left: 0; margin-right: 4px; flex-direction: row-reverse; }
  
  .sender-name { font-size: 13px; color: #1a1a1a; font-weight: 600; }
  .msg-time { font-size: 12px; color: #888; }

  .msg-row {
    display: flex; align-items: flex-start; gap: 12px;
    width: 100%;
  }
  .msg-row.user { flex-direction: row-reverse; }

  .bot-icon {
    width: 44px; height: 44px; border-radius: 12px;
    background: #9A1B22;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    color: white;
  }

  .bubble {
    max-width: 85%; padding: 14px 16px;
    font-size: 11px; line-height: 1.5;
    word-break: break-word; position: relative;
    border-radius: 12px;
  }
  .bubble.bot {
    background: #f4f4f5; color: #18181b;
    border-top-left-radius: 4px;
  }
  .bubble.user {
    background: #1e3a8a; color: #ffffff;
    border-top-right-radius: 4px;
  }
  .bubble p { margin: 0 0 10px; }
  .bubble p:last-child { margin-bottom: 0; }
  .bubble strong { font-weight: 700; color: #18181b; }
  .bubble a { color: #2563eb; text-decoration: underline; font-weight: 600; }
  .bubble.user a { color: #bfdbfe; }
  .bubble.user strong { color: #ffffff; }
  .bubble ul, .bubble ol { padding-left: 20px; margin: 8px 0; }
  /* Preserve intentional line breaks if the model emits single newlines */
  .stream-plain { margin: 0; white-space: pre-wrap; }

  .options-container {
    display: flex; flex-direction: column; gap: 10px;
    width: 100%; max-width: 85%; margin-left: 56px; margin-top: 4px;
  }
  .option-btn {
    width: 100%;
    background: #f4f4f5;
    border: none;
    border-radius: 24px;
    padding: 14px 20px;
    font-size: 11px;
    font-weight: 700;
    color: #000;
    cursor: pointer;
    transition: background 0.2s;
    text-align: center;
  }
  .option-btn:hover:not(:disabled) { background: #e4e4e7; }
  .option-btn:disabled { opacity: 0.6; cursor: not-allowed; }

  .typing-indicator { display: flex; align-items: flex-start; gap: 12px; animation: msg-in 0.28s both; }
  .typing-bubble {
    background: #f4f4f5; border-radius: 12px; border-top-left-radius: 4px;
    padding: 16px 20px; display: flex; gap: 6px; align-items: center;
  }
  .dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: #a1a1aa;
    animation: dot-bounce 1.4s ease-in-out infinite;
  }
  .dot:nth-child(2) { animation-delay: 0.2s; }
  .dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes dot-bounce {
    0%,80%,100% { transform: translateY(0);   opacity: 0.5; }
    40%          { transform: translateY(-4px); opacity: 1; }
  }

  .chat-input-area {
    background: #fff; padding: 16px 20px;
    display: flex; flex-direction: column; gap: 8px;
    border-top: 1px solid #f4f4f5;
  }
  .input-wrapper {
    display: flex; align-items: center; gap: 12px;
    background: #ffffff; border: 1.5px solid #e4e4e7;
    border-radius: 24px; padding: 10px 16px;
    transition: border-color 0.2s;
  }
  .input-wrapper:focus-within {
    border-color: #d4d4d8;
  }
  .chat-input {
    flex: 1; border: none; background: transparent; outline: none;
    font-family: 'Open Sans', sans-serif;
    font-size: 11px; color: #18181b; padding: 4px 0;
  }
  .chat-input::placeholder { color: #a1a1aa; }
  .chat-input:disabled { cursor: not-allowed; }

  .send-btn {
    width: 32px; height: 32px; border-radius: 50%; border: none; cursor: pointer;
    background: #f4f4f5;
    color: #a1a1aa; display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    transition: background 0.2s, color 0.2s;
  }
  .send-btn.active {
    background: #e4e4e7; color: #52525b; /* Not as prominent based on design */
  }
  .send-btn:disabled { opacity: 0.6; cursor: not-allowed; }

  /* —— Preference chips (one compact row, no instructional chrome) —— */
  .pref-bar {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    background: #fafafa;
    border-bottom: 1px solid #f0f0f1;
    position: relative;
    z-index: 20;
    overflow-x: auto;
    overflow-y: visible;
    scrollbar-width: none;
  }
  .pref-bar::-webkit-scrollbar { display: none; }
  .pref-chip-wrap {
    position: relative;
    display: flex;
    flex: 1 1 0;
    min-width: 0;
  }
  .pref-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    width: 100%;
    min-width: 0;
    font-family: inherit;
    font-size: 11px;
    line-height: 1.25;
    color: #3f3f46;
    background: #ffffff;
    border: 1px solid #e4e4e7;
    border-radius: 999px;
    padding: 5px 8px 5px 10px;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease, color 0.15s ease;
  }
  .pref-chip:hover:not(:disabled) {
    background: #f4f4f5;
    border-color: #d4d4d8;
  }
  .pref-chip:focus-visible {
    outline: 2px solid rgba(154, 27, 34, 0.35);
    outline-offset: 2px;
  }
  .pref-chip.open {
    border-color: #9A1B22;
    background: #faf7f7;
    box-shadow: 0 0 0 2px rgba(154, 27, 34, 0.1);
  }
  .pref-chip.empty {
    color: #a1a1aa;
    border-style: dashed;
    background: #fafafa;
  }
  .pref-chip.saved {
    border-color: #86efac;
    background: #f0fdf4;
    color: #166534;
  }
  .pref-chip:disabled {
    cursor: not-allowed;
    opacity: 0.65;
  }
  .pref-chip-value {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 600;
    min-width: 0;
  }
  .pref-chip-caret {
    width: 10px;
    height: 10px;
    flex-shrink: 0;
    color: #a1a1aa;
    transition: transform 0.15s ease;
  }
  .pref-chip.open .pref-chip-caret,
  .pref-chip.saved .pref-chip-caret {
    color: inherit;
  }
  .pref-chip.open .pref-chip-caret {
    transform: rotate(180deg);
  }
  .pref-chip-menu {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    z-index: 40;
    min-width: 196px;
    max-width: min(280px, 72vw);
    padding: 4px;
    background: #ffffff;
    border: 1px solid #e4e4e7;
    border-radius: 12px;
    box-shadow: 0 10px 28px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06);
    display: flex;
    flex-direction: column;
    gap: 1px;
    animation: pref-menu-in 0.14s ease both;
  }
  .pref-chip-option {
    width: 100%;
    text-align: left;
    border: none;
    background: transparent;
    border-radius: 8px;
    padding: 9px 10px;
    font-family: inherit;
    font-size: 11px;
    font-weight: 600;
    color: #18181b;
    cursor: pointer;
    transition: background 0.12s ease;
  }
  .pref-chip-option:hover:not(:disabled) {
    background: #f4f4f5;
  }
  .pref-chip-option.selected {
    background: #faf7f7;
    color: #9A1B22;
  }
  .pref-chip-option:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
  @keyframes pref-menu-in {
    from { opacity: 0; transform: translateY(-4px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .pref-restore {
    margin: 0 0 2px;
    padding: 6px 10px;
    border-radius: 8px;
    background: #fafafa;
    border: 1px solid #f0f0f1;
    color: #71717a;
    font-size: 10px;
    line-height: 1.4;
    animation: msg-in 0.28s both;
  }

  @media (max-width: 600px) {
    .chat-window {
      position: fixed;
      top: 0; right: 0; bottom: 0; left: 0;
      width: 100%; height: 100%; max-height: 100%;
      border-radius: 0;
    }
    .chat-window.open   { transform: translateY(0); }
    .chat-window.closed { transform: translateY(100%); }
    .chat-header { padding-top: max(16px, env(safe-area-inset-top, 16px)); }
    .chat-input-area { padding-bottom: max(16px, env(safe-area-inset-bottom, 16px)); }
  }
`;

const SESSION_STORAGE_KEY = "mc_chat_session_id";
const GUEST_STORAGE_KEY = "mc_guest_id";

/** Optional host-app registered user (set window.__MC_USER_ID__ or VITE_USER_ID). */
function getRegisteredUserId() {
  if (typeof window !== "undefined" && window.__MC_USER_ID__) {
    return String(window.__MC_USER_ID__);
  }
  const fromEnv = import.meta.env && import.meta.env.VITE_USER_ID;
  return fromEnv ? String(fromEnv) : null;
}

function getOrCreateGuestId() {
  let guestId = localStorage.getItem(GUEST_STORAGE_KEY);
  if (!guestId) {
    guestId = `guest_${crypto.randomUUID()}`;
    localStorage.setItem(GUEST_STORAGE_KEY, guestId);
  }
  return guestId;
}

function identityPayload() {
  const userId = getRegisteredUserId();
  if (userId) return { user_id: userId };
  return { guest_id: getOrCreateGuestId() };
}

const EXPERIENCE_OPTIONS = [
  "Entry-level (0–2 years)",
  "Mid-level (3–7 years)",
  "Senior/Manager (8+ years)",
];
const DEPARTMENT_OPTIONS = ["Finance", "Management", "IT"];
const GOAL_OPTIONS = [
  "Earn a certification",
  "Get a promotion",
  "Upskill / personal growth",
];

const SPEAK_WITH_AGENT_OPTION = "Speak with Agent";

/** Detect fixed support/ticket acknowledgments so we can restore Speak with Agent when appropriate. */
function isSupportHandoffText(text) {
  if (!text) return false;
  const lower = text.toLowerCase();
  return (
    lower.includes("contact our technical support") ||
    lower.includes("technical support team at") ||
    lower.includes("844-876-7476") ||
    lower.includes("technicalsupport@managementconcepts.com") ||
    lower.includes("speak with agent") ||
    lower.includes("certificate request has been received") ||
    lower.includes("will be generated shortly") ||
    lower.includes("generated shortly") ||
    // legacy copy from older sessions
    lower.includes("sent to our support team") ||
    lower.includes("password change request has been sent") ||
    lower.includes("speak with an agent has been sent")
  );
}

/** Password / generic tickets CTA the Speak with Agent chip (markdown-safe). */
function offersSpeakWithAgentChip(text) {
  if (!text) return false;
  const lower = text.toLowerCase();
  return (
    lower.includes("select") &&
    lower.includes("speak with agent") &&
    lower.includes("below")
  );
}

/** True when the bot already confirmed agent/certificate — no Speak with Agent chip. */
function isSupportConfirmationOnly(text) {
  if (!text) return false;
  const lower = text.toLowerCase();
  // Password/generic tickets include a "select Speak with Agent below" CTA → show the chip.
  if (offersSpeakWithAgentChip(text)) return false;
  return (
    lower.includes("certificate request has been received") ||
    lower.includes("will be generated shortly") ||
    lower.includes("generated shortly") ||
    lower.includes("we'll connect you with a specialist") ||
    lower.includes("we’ll connect you with a specialist") ||
    lower.includes("speak with an agent has been sent") ||
    lower.includes("specialist will pick this up") ||
    lower.includes("specialist can help")
  );
}

/**
 * Onboarding option chips lock free-text until a choice is made.
 * Support chips (Speak with Agent) must not lock the input — learners can keep typing
 * password / certificate / other requests without leaving the chat.
 */
function optionsLockFreeText(msg) {
  if (!msg?.options?.length || msg.optionsDisabled) return false;
  const onlySupportChip = msg.options.every(
    (o) => String(o).trim().toLowerCase() === SPEAK_WITH_AGENT_OPTION.toLowerCase()
  );
  return !onlySupportChip;
}

function isSpeakWithAgentSelection(text) {
  const t = (text || "").trim().toLowerCase();
  return t === "speak with agent" || t === "speak with an agent";
}

function newMessageId() {
  return crypto.randomUUID();
}

function getTime() {
  return new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatTimeFromIso(iso) {
  if (!iso) return getTime();
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function inferConversationStep(apiMessages) {
  const userSteps = apiMessages
    .filter((m) => m.role === "user" && m.metadata?.step)
    .map((m) => m.metadata.step);
  if (userSteps.includes("goal")) return "free";
  if (userSteps.includes("department")) return "goal";
  if (userSteps.includes("experience")) return "department";
  return "experience";
}

function extractProfileFromHistory(apiMessages) {
  const profile = {};
  for (const m of apiMessages) {
    if (m.role !== "user") continue;
    const step = m.metadata?.step;
    const value = m.metadata?.value || m.display_content || m.content;
    if (step === "experience") profile.experience = value;
    if (step === "department") profile.department = value;
    if (step === "goal") profile.goal = value;
  }
  return profile;
}

function mapHistoryToMessages(apiMessages) {
  const visible = apiMessages.filter((m) => m.metadata?.visible !== false);
  return visible.map((m, i, arr) => {
    const hasReplyAfter = arr.slice(i + 1).some((next) => next.role === "user");
    const text = m.display_content || m.content;
    // Restore Speak with Agent on password/generic tickets when options were not stored.
    // Skip agent/certificate confirmations — those are already final in-chat acknowledgments.
    let options = m.metadata?.options;
    if (
      m.role === "assistant" &&
      !options &&
      isSupportHandoffText(text) &&
      !isSupportConfirmationOnly(text)
    ) {
      options = [SPEAK_WITH_AGENT_OPTION];
    }
    return {
      id: newMessageId(),
      text,
      sender: m.role === "user" ? "user" : "bot",
      time: formatTimeFromIso(m.created_at),
      options,
      optionsDisabled: options ? hasReplyAfter : undefined,
    };
  });
}

/** Compact chip label: drop parenthetical detail when present. */
function shortPrefDisplay(value) {
  if (!value) return null;
  const trimmed = String(value).replace(/\s*\([^)]*\)\s*$/, "").trim();
  return trimmed || String(value);
}

function profileHasAny(profile) {
  return !!(profile?.experience || profile?.department || profile?.goal);
}

function profileIsComplete(profile) {
  return !!(profile?.experience && profile?.department && profile?.goal);
}

const PREF_CHIP_OPTIONS = {
  experience: EXPERIENCE_OPTIONS,
  department: DEPARTMENT_OPTIONS,
  goal: GOAL_OPTIONS,
};

const PREF_CHIP_META = {
  experience: { title: "Experience level", empty: "Level" },
  department: { title: "Department", empty: "Dept" },
  goal: { title: "Career goal", empty: "Goal" },
};

function PreferenceBar({ profile, flashKey, onSelectPreference, disabled }) {
  const [openKey, setOpenKey] = useState(null);
  const barRef = useRef(null);

  const chips = [
    { key: "experience", value: profile.experience },
    { key: "department", value: profile.department },
    { key: "goal", value: profile.goal },
  ];

  useEffect(() => {
    if (!openKey) return undefined;
    const onPointerDown = (e) => {
      if (barRef.current && !barRef.current.contains(e.target)) {
        setOpenKey(null);
      }
    };
    const onKeyDown = (e) => {
      if (e.key === "Escape") setOpenKey(null);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [openKey]);

  useEffect(() => {
    if (disabled) setOpenKey(null);
  }, [disabled]);

  const handleChipClick = (key) => {
    if (disabled) return;
    setOpenKey((prev) => (prev === key ? null : key));
  };

  const handleOptionClick = (key, value) => {
    if (disabled) return;
    setOpenKey(null);
    if (value && value !== profile[key]) {
      onSelectPreference?.(key, value);
    }
  };

  return (
    <div className="pref-bar" ref={barRef} role="toolbar" aria-label="Your preferences">
      {chips.map((chip) => {
        const meta = PREF_CHIP_META[chip.key];
        const isOpen = openKey === chip.key;
        const isSaved = flashKey === chip.key;
        const options = PREF_CHIP_OPTIONS[chip.key] || [];
        const display = shortPrefDisplay(chip.value) || meta.empty;
        return (
          <div key={chip.key} className="pref-chip-wrap">
            <button
              type="button"
              className={`pref-chip${chip.value ? "" : " empty"}${isOpen ? " open" : ""}${isSaved ? " saved" : ""}`}
              title={chip.value ? `${meta.title}: ${chip.value}` : `Set ${meta.title}`}
              aria-haspopup="listbox"
              aria-expanded={isOpen}
              aria-label={`${meta.title}: ${chip.value || "not set"}`}
              disabled={disabled}
              onClick={() => handleChipClick(chip.key)}
            >
              <span className="pref-chip-value">{display}</span>
              <svg className="pref-chip-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            {isOpen ? (
              <div className="pref-chip-menu" role="listbox" aria-label={meta.title}>
                {options.map((opt) => {
                  const selected = chip.value === opt;
                  return (
                    <button
                      key={opt}
                      type="button"
                      role="option"
                      aria-selected={selected}
                      className={`pref-chip-option${selected ? " selected" : ""}`}
                      disabled={disabled}
                      onClick={() => handleOptionClick(chip.key, opt)}
                    >
                      {opt}
                    </button>
                  );
                })}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function MessageContent({ msg }) {
  if (msg.sender === "user" || msg.streaming) {
    return <p className="stream-plain">{msg.text}</p>;
  }

  // Ensure course fact rows stay on separate lines even if a reply uses
  // single newlines (Markdown otherwise collapses them into one paragraph).
  const text = String(msg.text || "").replace(
    /(^|\n)(\*{0,2}(?:Duration|Credits|Cost|Level)\*{0,2}:|\[Register Now\])/g,
    "\n\n$2"
  ).replace(/\n{3,}/g, "\n\n").trim();

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p>{children}</p>,
        a: ({ node, href, children, ...props }) => {
          const isContact =
            (href && (href.startsWith("tel:") || href.startsWith("mailto:"))) ||
            false;
          return (
            <a
              {...props}
              href={href}
              target={isContact ? undefined : "_blank"}
              rel={isContact ? undefined : "noopener noreferrer"}
            >
              {children}
            </a>
          );
        },
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== "undefined" && window.innerWidth <= 600
  );
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 600px)");
    const handler = (e) => setIsMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return isMobile;
}

const MCIcon = () => (
  <svg viewBox="0 0 24 24" fill="white" width="24" height="24">
    <path d="M4 20L4 8L8 12L12 6L16 12L20 8L20 20Z" stroke="white" strokeWidth="2" strokeLinejoin="round" />
  </svg>
);

export default function FloatingChatbot() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sessionInitializing, setSessionInitializing] = useState(false);
  const [conversationStep, setConversationStep] = useState("experience");
  const [profile, setProfile] = useState({});
  /** Which chip briefly highlights green after a save (`experience` | `department` | `goal`). */
  const [flashKey, setFlashKey] = useState(null);
  const [welcomeBack, setWelcomeBack] = useState(null);
  const stepRef = useRef("experience");
  const profileRef = useRef({});
  const sendingRef = useRef(false);
  const streamAbortRef = useRef(null);
  const sessionInitStarted = useRef(false);
  const timeoutsRef = useRef([]);
  const flashTimerRef = useRef(null);
  const welcomeTimerRef = useRef(null);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);
  const isMobile = useIsMobile();

  const abortActiveStream = () => {
    streamAbortRef.current?.abort();
    streamAbortRef.current = null;
  };

  const syncProfile = (next) => {
    const cleaned = {
      experience: next.experience || undefined,
      department: next.department || undefined,
      goal: next.goal || undefined,
    };
    profileRef.current = cleaned;
    setProfile(cleaned);
  };

  const flashChip = (key) => {
    if (!key) return;
    if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
    setFlashKey(key);
    flashTimerRef.current = setTimeout(() => {
      setFlashKey(null);
      flashTimerRef.current = null;
    }, 1400);
  };

  const showWelcomeBack = (text) => {
    if (welcomeTimerRef.current) clearTimeout(welcomeTimerRef.current);
    setWelcomeBack(text);
    welcomeTimerRef.current = setTimeout(() => {
      setWelcomeBack(null);
      welcomeTimerRef.current = null;
    }, 4500);
  };

  useEffect(() => {
    return () => {
      abortActiveStream();
      timeoutsRef.current.forEach(clearTimeout);
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
      if (welcomeTimerRef.current) clearTimeout(welcomeTimerRef.current);
    };
  }, []);

  // Support configurable backend for dev / docker / prod via Vite env
  // Set VITE_API_BASE_URL=http://your-host:8000 in .env (frontend/ChatbotUI/.env or root env loaded by Vite)
  const API_BASE = (import.meta.env && import.meta.env.VITE_API_BASE_URL) || "http://localhost:8000";

  const persistBotMessage = async (sid, text, metadata = {}) => {
    try {
      await fetch(`${API_BASE}/session/${sid}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: "assistant",
          content: text,
          display_content: text,
          metadata,
          ...identityPayload(),
        }),
      });
    } catch {
      // Non-blocking — chat still works if persistence fails
    }
  };

  const persistUserSelection = async (sid, step, value, { silent = false, profileSnapshot = null } = {}) => {
    const content =
      step === "experience"
        ? `My experience level is: ${value}.`
        : step === "department"
          ? `My department is: ${value}.`
          : step === "goal"
            ? `My career goal is: ${value}.`
            : value;
    const metadata = {
      step,
      value,
      type: silent ? "preference_update" : "onboarding_selection",
      [step]: value,
    };
    if (silent) metadata.visible = false;
    if (profileSnapshot && profileHasAny(profileSnapshot)) {
      metadata.profile = {
        experience: profileSnapshot.experience,
        department: profileSnapshot.department,
        goal: profileSnapshot.goal,
      };
      if (profileIsComplete(profileSnapshot)) {
        metadata.profile_complete = true;
      }
    }
    await fetch(`${API_BASE}/session/${sid}/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        role: "user",
        content,
        display_content: value,
        metadata,
        ...identityPayload(),
      }),
    });
  };

  const buildRecommendationPayload = (profile) => ({
    backendMessage:
      `My experience level is: ${profile.experience}. ` +
      `My department is: ${profile.department}. ` +
      `My career goal is: ${profile.goal}. ` +
      `Please recommend courses based on my profile.`,
    metadata: {
      step: "goal",
      value: profile.goal,
      profile_complete: true,
      profile: {
        experience: profile.experience,
        department: profile.department,
        goal: profile.goal,
      },
      experience: profile.experience,
      department: profile.department,
      goal: profile.goal,
    },
  });

  /** Parse X-MC-Options (pipe-separated, URL-encoded labels) from the stream response. */
  const parseOptionsHeader = (res) => {
    const raw = res.headers.get("X-MC-Options");
    if (!raw) return null;
    const opts = raw
      .split("|")
      .map((part) => {
        try {
          return decodeURIComponent(part);
        } catch {
          return part;
        }
      })
      .map((s) => s.trim())
      .filter(Boolean);
    return opts.length ? opts : null;
  };

  /**
   * Options for a finished bot message: prefer server header, else legacy text heuristics
   * for older sessions / providers that omit X-MC-Options.
   */
  const resolveBotOptions = (text, supportCheckText, headerOptions) => {
    if (headerOptions) return headerOptions;
    if (
      isSupportHandoffText(text) &&
      !isSupportConfirmationOnly(text) &&
      !isSpeakWithAgentSelection(supportCheckText)
    ) {
      return [SPEAK_WITH_AGENT_OPTION];
    }
    return undefined;
  };

  /** Stream a bot reply into the message list. Caller owns sendingRef. */
  const streamChatResponse = async ({
    sid,
    backendMessage,
    displayMessage,
    metadata,
    supportCheckText,
  }) => {
    abortActiveStream();
    setLoading(true);

    const botMessageId = newMessageId();
    let streamStarted = false;
    let streamRafId = null;
    let pendingStreamText = "";

    const applyBotMessage = (text, streaming, options) => {
      if (!streamStarted) {
        streamStarted = true;
        setMessages((prev) => [
          ...prev,
          {
            id: botMessageId,
            text,
            sender: "bot",
            time: getTime(),
            streaming,
            options,
          },
        ]);
        return;
      }
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === botMessageId
            ? {
                ...msg,
                text,
                streaming,
                ...(options ? { options } : {}),
                ...(!streaming && !options && msg.options ? { options: undefined } : {}),
              }
            : msg
        )
      );
    };

    const flushStreamUpdate = () => {
      streamRafId = null;
      applyBotMessage(pendingStreamText, true, undefined);
    };

    const scheduleStreamUpdate = (text) => {
      pendingStreamText = text;
      if (streamRafId === null) {
        streamRafId = requestAnimationFrame(flushStreamUpdate);
      }
    };

    const abortController = new AbortController();
    streamAbortRef.current = abortController;

    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abortController.signal,
        body: JSON.stringify({
          session_id: sid,
          message: backendMessage,
          display_message: displayMessage,
          metadata,
          ...identityPayload(),
        }),
      });
      if (!res.ok) throw new Error("Failed");

      const headerOptions = parseOptionsHeader(res);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        fullText += decoder.decode(value, { stream: true });
        scheduleStreamUpdate(fullText);
      }

      if (streamRafId !== null) {
        cancelAnimationFrame(streamRafId);
        streamRafId = null;
      }
      const finalOptions = resolveBotOptions(fullText, supportCheckText, headerOptions);
      applyBotMessage(fullText, false, finalOptions);
      return { ok: true, aborted: false, text: fullText };
    } catch (err) {
      if (streamRafId !== null) {
        cancelAnimationFrame(streamRafId);
        streamRafId = null;
      }
      if (err.name === "AbortError") {
        return { ok: false, aborted: true, text: "" };
      }
      applyBotMessage("Sorry, something went wrong.", false, undefined);
      return { ok: false, aborted: false, text: "" };
    } finally {
      if (streamAbortRef.current === abortController) {
        streamAbortRef.current = null;
      }
      setLoading(false);
    }
  };

  const updatePreferenceFromChip = async (key, value) => {
    if (!sessionId || loading || sendingRef.current) return;
    if (!["experience", "department", "goal"].includes(key)) return;
    if (!value || value === profileRef.current[key]) return;

    const nextProfile = { ...profileRef.current, [key]: value };
    const shouldRecommend = key === "goal" && profileIsComplete(nextProfile);

    syncProfile(nextProfile);
    flashChip(key);

    sendingRef.current = true;
    try {
      // Goal refresh is persisted by the chat/stream turn (visible in history).
      // Exp/dept-only chip edits stay silent so the thread is not cluttered.
      if (!shouldRecommend) {
        await persistUserSelection(sessionId, key, value, {
          silent: true,
          profileSnapshot: nextProfile,
        });
        return;
      }

      // Surface the new goal in the thread, then re-run course recommendations.
      setMessages((prev) => {
        const updatedPrev = prev.map((msg) =>
          msg.options && !msg.optionsDisabled ? { ...msg, optionsDisabled: true } : msg
        );
        return [
          ...updatedPrev,
          {
            id: newMessageId(),
            text: value,
            sender: "user",
            time: getTime(),
          },
        ];
      });

      const { backendMessage, metadata } = buildRecommendationPayload(nextProfile);
      const result = await streamChatResponse({
        sid: sessionId,
        backendMessage,
        displayMessage: value,
        metadata: {
          ...metadata,
          preference_refresh: true,
        },
        supportCheckText: value,
      });

      if (!result.aborted) {
        setConversationStep("free");
        stepRef.current = "free";
        flashChip("goal");
      }
    } catch {
      // Local state already updated; next chat turn can re-sync from server
      if (shouldRecommend) {
        setMessages((prev) => [
          ...prev,
          {
            id: newMessageId(),
            text: "Sorry, something went wrong refreshing recommendations.",
            sender: "bot",
            time: getTime(),
          },
        ]);
      }
    } finally {
      sendingRef.current = false;
    }
  };

  const scheduleMsg = (delay, msg, sid) => {
    const id = setTimeout(() => {
      const withTime = { ...msg, id: newMessageId(), time: getTime() };
      setMessages((prev) => [...prev, withTime]);
      if (sid) {
        persistBotMessage(sid, msg.text, msg.metadata || { type: "onboarding" });
      }
    }, delay);
    timeoutsRef.current.push(id);
  };

  const showWelcomeFlow = (sid) => {
    const welcomeText =
      "Welcome! I'll help you find the right Management Concepts courses.";
    setMessages([{
      id: newMessageId(),
      sender: "bot",
      time: getTime(),
      text: welcomeText,
    }]);
    persistBotMessage(sid, welcomeText, { step: "welcome", type: "onboarding" });

    scheduleMsg(800, {
      sender: "bot",
      text: "What's your experience level?",
      options: EXPERIENCE_OPTIONS,
      metadata: { step: "experience", type: "onboarding", options: EXPERIENCE_OPTIONS },
    }, sid);
  };

  const startNewChat = async () => {
    abortActiveStream();
    sendingRef.current = false;
    timeoutsRef.current.forEach(clearTimeout);
    timeoutsRef.current = [];
    localStorage.removeItem(SESSION_STORAGE_KEY);
    setMessages([]);
    setConversationStep("experience");
    stepRef.current = "experience";
    // Full reset: clear local prefs and tell the API to wipe durable profile.
    syncProfile({});
    setWelcomeBack(null);
    setFlashKey(null);
    setLoading(false);
    setInput("");

    try {
      getOrCreateGuestId();
      const res = await fetch(`${API_BASE}/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...identityPayload(), reset_profile: true }),
      });
      const data = await res.json();
      const newId = data.session_id;
      setSessionId(newId);
      localStorage.setItem(SESSION_STORAGE_KEY, newId);
      // Do not re-apply data.profile — New chat intentionally starts with empty prefs.
      showWelcomeFlow(newId);
    } catch {
      setSessionId(null);
      setMessages([{
        id: newMessageId(),
        text: "Error connecting to server. Make sure the backend is running.",
        sender: "bot",
        time: getTime(),
      }]);
    }
  };

  const initSession = async () => {
    if (sessionInitStarted.current) return;
    sessionInitStarted.current = true;
    setSessionInitializing(true);

    try {
      getOrCreateGuestId();
      const storedId = localStorage.getItem(SESSION_STORAGE_KEY);
      if (storedId) {
        const historyRes = await fetch(`${API_BASE}/session/${storedId}/history`);
        if (historyRes.ok) {
          const historyData = await historyRes.json();
          if (historyData.messages?.length > 0) {
            setSessionId(storedId);
            setMessages(mapHistoryToMessages(historyData.messages));
            const step = inferConversationStep(historyData.messages);
            setConversationStep(step);
            stepRef.current = step;
            const fromHistory = extractProfileFromHistory(historyData.messages);
            const expanded = historyData.session?.prefs_expanded || {};
            const restored = {
              experience: fromHistory.experience || expanded.experience,
              department: fromHistory.department || expanded.department,
              goal: fromHistory.goal || expanded.goal,
            };
            syncProfile(restored);
            if (profileHasAny(restored) || historyData.messages.length > 0) {
              showWelcomeBack(
                profileIsComplete(restored)
                  ? "Welcome back — conversation restored."
                  : "Welcome back."
              );
            }
            return;
          }
        }
      }

      const res = await fetch(`${API_BASE}/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(identityPayload()),
      });
      const data = await res.json();
      const newId = data.session_id;
      setSessionId(newId);
      localStorage.setItem(SESSION_STORAGE_KEY, newId);
      if (data.profile && profileHasAny(data.profile)) {
        syncProfile({
          experience: data.profile.experience,
          department: data.profile.department,
          goal: data.profile.goal,
        });
        showWelcomeBack("Preferences restored — edit anytime via the chips above.");
      }
      showWelcomeFlow(newId);
    } catch {
      setMessages([{
        id: newMessageId(),
        text: "Error connecting to server. Make sure the backend is running.",
        sender: "bot",
        time: getTime(),
      }]);
    } finally {
      setSessionInitializing(false);
    }
  };

  const sendMessage = async (overrideText) => {
    const messageToSend = typeof overrideText === "string" ? overrideText : input;
    if (!messageToSend.trim() || !sessionId || loading || sendingRef.current) return;

    sendingRef.current = true;
    const currentStep = stepRef.current;
    const isOnboardingKv = currentStep === "experience" || currentStep === "department";

    const userMessage = {
      id: newMessageId(),
      text: messageToSend,
      sender: "user",
      time: getTime(),
    };

    setMessages((prev) => {
      const updatedPrev = prev.map(msg =>
        msg.options && !msg.optionsDisabled ? { ...msg, optionsDisabled: true } : msg
      );
      return [...updatedPrev, userMessage];
    });
    setInput("");

    // Experience & department: store as KV pairs only — no LLM call, no typing indicator
    if (isOnboardingKv) {
      try {
        await persistUserSelection(sessionId, currentStep, messageToSend);
        syncProfile({ ...profileRef.current, [currentStep]: messageToSend });
        flashChip(currentStep);

        if (currentStep === "experience") {
          scheduleMsg(600, {
            sender: "bot",
            text: "Got it. Which department are you in?",
            options: DEPARTMENT_OPTIONS,
            metadata: { step: "department", type: "onboarding", options: DEPARTMENT_OPTIONS },
          }, sessionId);
          setConversationStep("department");
          stepRef.current = "department";
        } else {
          scheduleMsg(600, {
            sender: "bot",
            text: "Noted. Certification, promotion, or upskilling?",
            options: GOAL_OPTIONS,
            metadata: { step: "goal", type: "onboarding", options: GOAL_OPTIONS },
          }, sessionId);
          setConversationStep("goal");
          stepRef.current = "goal";
        }
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: newMessageId(),
            text: "Sorry, something went wrong saving your selection.",
            sender: "bot",
            time: getTime(),
          },
        ]);
      } finally {
        sendingRef.current = false;
      }
      return;
    }

    let backendMessage = messageToSend;
    let stepMetadata = { step: currentStep };

    if (currentStep === "goal") {
      const nextProfile = { ...profileRef.current, goal: messageToSend };
      syncProfile(nextProfile);
      flashChip("goal");
      const rec = buildRecommendationPayload(nextProfile);
      backendMessage = rec.backendMessage;
      stepMetadata = rec.metadata;
    } else {
      const currentProfile = profileRef.current;
      stepMetadata = { step: "free" };
      if (currentProfile.experience) stepMetadata.experience = currentProfile.experience;
      if (currentProfile.department) stepMetadata.department = currentProfile.department;
      if (currentProfile.goal) stepMetadata.goal = currentProfile.goal;
      if (currentProfile.experience && currentProfile.department && currentProfile.goal) {
        stepMetadata.profile = {
          experience: currentProfile.experience,
          department: currentProfile.department,
          goal: currentProfile.goal,
        };
      }
    }

    try {
      const result = await streamChatResponse({
        sid: sessionId,
        backendMessage,
        displayMessage: messageToSend,
        metadata: stepMetadata,
        supportCheckText: messageToSend,
      });

      if (result.aborted) return;

      if (currentStep === "goal") {
        setConversationStep("free");
        stepRef.current = "free";
      }
    } finally {
      sendingRef.current = false;
    }
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, welcomeBack]);

  const handleOpen = () => {
    setOpen((prev) => {
      const next = !prev;
      if (next && !sessionInitStarted.current) {
        initSession();
      }
      if (next) setTimeout(() => inputRef.current?.focus(), 320);
      return next;
    });
  };

  return (
    <div className="chatbot-root">
      <style>{styles}</style>

      {(!isMobile || !open) && (
        <button className="chat-fab" onClick={handleOpen} title="Support Chat">
          <MCIcon />
        </button>
      )}

      <div className={`chat-window ${open ? "open" : "closed"}`}>
        <div className="chat-header">
          <div className="header-left">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            <span style={{ fontSize: '18px', fontWeight: '600' }}>Support Assistant</span>
          </div>
          <div className="header-right">
            <button className="header-icon-btn" onClick={startNewChat} title="New chat">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                 <circle cx="5" cy="12" r="2"/>
                 <circle cx="12" cy="12" r="2"/>
                 <circle cx="19" cy="12" r="2"/>
              </svg>
            </button>
            <button className="header-icon-btn" onClick={() => setOpen(false)} title="Close">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        <PreferenceBar
          profile={profile}
          flashKey={flashKey}
          onSelectPreference={updatePreferenceFromChip}
          disabled={sessionInitializing || !sessionId || loading}
        />

        <div className="chat-messages">
          {sessionInitializing && messages.length === 0 && (
            <div className="typing-indicator">
              <div className="bot-icon">
                <MCIcon />
              </div>
              <div className="typing-bubble">
                <div className="dot" /><div className="dot" /><div className="dot" />
              </div>
            </div>
          )}

          {welcomeBack && !sessionInitializing && (
            <div className="pref-restore" role="status">
              {welcomeBack}
            </div>
          )}

          {messages.map((msg, i) => {
            const isConsecutive = i > 0 && messages[i - 1].sender === msg.sender;
            return (
            <div key={msg.id} className={`msg-wrapper ${msg.sender}`}>
              {msg.sender === "bot" && !isConsecutive && (
                <div className="msg-meta bot">
                  <span className="sender-name">MCAgent</span>
                  <span className="msg-time">{msg.time}</span>
                </div>
              )}
              {msg.sender === "user" && !isConsecutive && (
                <div className="msg-meta user">
                  <span className="msg-time">{msg.time}</span>
                </div>
              )}

              <div className={`msg-row ${msg.sender}`}>
                {msg.sender === "bot" && (
                  <div className="bot-icon" style={{ visibility: isConsecutive ? 'hidden' : 'visible' }}>
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="10" rx="2" />
                      <circle cx="12" cy="5" r="2" />
                      <path d="M12 7v4" />
                      <line x1="8" y1="16" x2="8.01" y2="16" />
                      <line x1="16" y1="16" x2="16.01" y2="16" />
                    </svg>
                  </div>
                )}
                
                <div className={`bubble ${msg.sender}`}>
                  <MessageContent msg={msg} />
                </div>
              </div>

              {msg.options && (
                <div className="options-container">
                  {msg.options.map((opt, idx) => {
                    const isDisabled = loading || msg.optionsDisabled;
                    return (
                      <button
                        key={idx}
                        className="option-btn"
                        disabled={isDisabled}
                        onClick={() => sendMessage(opt)}
                      >
                        {opt}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );})}

          {loading && (
            <div className="typing-indicator">
              <div className="bot-icon">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="10" rx="2" />
                  <circle cx="12" cy="5" r="2" />
                  <path d="M12 7v4" />
                  <line x1="8" y1="16" x2="8.01" y2="16" />
                  <line x1="16" y1="16" x2="16.01" y2="16" />
                </svg>
              </div>
              <div className="typing-bubble">
                <div className="dot" /><div className="dot" /><div className="dot" />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="chat-input-area">
          <div className="input-wrapper">
            <input
              ref={inputRef}
              className="chat-input"
              type="text"
              placeholder={
                conversationStep === "free" || profileIsComplete(profile)
                  ? "Ask about courses…"
                  : "Write a message"
              }
              value={input}
              disabled={
                sessionInitializing ||
                !sessionId ||
                loading ||
                (messages.length > 0 && optionsLockFreeText(messages[messages.length - 1]))
              }
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            />
            <button
              className={`send-btn ${input.trim() ? 'active' : ''}`}
              onClick={sendMessage}
              disabled={
                sessionInitializing ||
                !sessionId ||
                loading ||
                (messages.length > 0 && optionsLockFreeText(messages[messages.length - 1]))
              }
              title="Send"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="19" x2="12" y2="5"/>
                <polyline points="5 12 12 5 19 12"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}