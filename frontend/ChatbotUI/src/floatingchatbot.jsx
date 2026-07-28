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
  .bubble a { color: #2563eb; text-decoration: underline; }
  .bubble.user a { color: #bfdbfe; }
  .bubble ul, .bubble ol { padding-left: 20px; margin: 8px 0; }
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
  .icon-btn {
    background: transparent; border: none; cursor: pointer;
    color: #a1a1aa; display: flex; align-items: center; justify-content: center;
    padding: 0; margin: 0;
  }
  .icon-btn:hover { color: #71717a; }
  
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

  /* —— Preference memory (subtle, always-on cues) —— */
  .pref-bar {
    flex: 0 0 auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 16px 12px;
    background: linear-gradient(180deg, #fafafa 0%, #ffffff 100%);
    border-bottom: 1px solid #f0f0f1;
    position: relative;
    z-index: 20;
  }
  .pref-bar-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .pref-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: #71717a;
    font-weight: 500;
    min-width: 0;
  }
  .pref-status-icon {
    width: 14px;
    height: 14px;
    flex-shrink: 0;
    color: #9A1B22;
    opacity: 0.75;
  }
  .pref-status strong {
    color: #52525b;
    font-weight: 600;
  }
  .pref-saved-flash {
    font-size: 10px;
    font-weight: 600;
    color: #166534;
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 999px;
    padding: 2px 8px;
    white-space: nowrap;
    animation: pref-flash-in 0.25s ease both;
  }
  @keyframes pref-flash-in {
    from { opacity: 0; transform: translateY(-2px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .pref-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .pref-chip-wrap {
    position: relative;
    display: inline-flex;
    max-width: 100%;
  }
  .pref-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    max-width: 100%;
    font-family: inherit;
    font-size: 10px;
    line-height: 1.3;
    color: #3f3f46;
    background: #f4f4f5;
    border: 1px solid #e4e4e7;
    border-radius: 999px;
    padding: 3px 8px 3px 6px;
    animation: pref-chip-in 0.28s cubic-bezier(.4,0,.2,1) both;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
  }
  .pref-chip:hover:not(:disabled) {
    background: #ececef;
    border-color: #d4d4d8;
  }
  .pref-chip:focus-visible {
    outline: 2px solid rgba(154, 27, 34, 0.35);
    outline-offset: 2px;
  }
  .pref-chip.open {
    border-color: #9A1B22;
    background: #faf7f7;
    box-shadow: 0 0 0 2px rgba(154, 27, 34, 0.12);
  }
  .pref-chip.empty {
    color: #a1a1aa;
    background: #fafafa;
    border-style: dashed;
  }
  .pref-chip.empty:hover:not(:disabled) {
    background: #f4f4f5;
    border-color: #c4c4c8;
    border-style: dashed;
  }
  .pref-chip:disabled {
    cursor: not-allowed;
    opacity: 0.7;
  }
  .pref-chip-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #9A1B22;
    flex-shrink: 0;
    opacity: 0.7;
  }
  .pref-chip.empty .pref-chip-dot {
    background: #d4d4d8;
    opacity: 1;
  }
  .pref-chip-label {
    color: #a1a1aa;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-size: 9px;
  }
  .pref-chip-value {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 140px;
    font-weight: 600;
  }
  .pref-chip-caret {
    width: 10px;
    height: 10px;
    flex-shrink: 0;
    color: #a1a1aa;
    opacity: 0.85;
    transition: transform 0.15s ease;
  }
  .pref-chip.open .pref-chip-caret {
    transform: rotate(180deg);
    color: #9A1B22;
  }
  .pref-chip-menu {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    z-index: 40;
    min-width: 200px;
    max-width: min(280px, 70vw);
    padding: 6px;
    background: #ffffff;
    border: 1px solid #e4e4e7;
    border-radius: 12px;
    box-shadow: 0 10px 28px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06);
    display: flex;
    flex-direction: column;
    gap: 2px;
    animation: pref-menu-in 0.16s ease both;
  }
  .pref-chip-menu-title {
    font-size: 10px;
    font-weight: 600;
    color: #71717a;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 4px 10px 6px;
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
  @keyframes pref-chip-in {
    from { opacity: 0; transform: scale(0.94); }
    to   { opacity: 1; transform: scale(1); }
  }
  @keyframes pref-menu-in {
    from { opacity: 0; transform: translateY(-4px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .pref-welcome {
    margin: 0 0 4px;
    padding: 10px 12px;
    border-radius: 10px;
    background: #faf7f7;
    border: 1px solid #f0e4e5;
    color: #52525b;
    font-size: 11px;
    line-height: 1.45;
    animation: msg-in 0.28s both;
  }
  .pref-welcome strong {
    color: #9A1B22;
    font-weight: 600;
  }
  .pref-note {
    align-self: flex-end;
    margin-top: 2px;
    font-size: 10px;
    color: #a1a1aa;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    animation: pref-flash-in 0.3s ease both;
  }
  .pref-note svg {
    width: 11px;
    height: 11px;
    color: #9A1B22;
    opacity: 0.65;
  }
  .pref-footer {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    font-size: 10px;
    color: #a1a1aa;
    letter-spacing: 0.01em;
    padding: 0 4px;
  }
  .pref-footer svg {
    width: 11px;
    height: 11px;
    flex-shrink: 0;
    opacity: 0.7;
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
    lower.includes("speak with agent below") ||
    lower.includes("certificate request has been received") ||
    lower.includes("will be generated shortly") ||
    // legacy copy from older sessions
    lower.includes("sent to our support team") ||
    lower.includes("password change request has been sent") ||
    lower.includes("speak with an agent has been sent")
  );
}

/** True when the bot already confirmed agent/certificate — no Speak with Agent chip. */
function isSupportConfirmationOnly(text) {
  if (!text) return false;
  const lower = text.toLowerCase();
  // Password/generic tickets include "select Speak with Agent below" → show the chip.
  if (lower.includes("select speak with agent below")) return false;
  return (
    lower.includes("certificate request has been received") ||
    lower.includes("will be generated shortly") ||
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
    const step = m.metadata?.step;
    const text = m.display_content || m.content;
    const prefSaved =
      m.role === "user" &&
      (step === "experience" ||
        step === "department" ||
        step === "goal" ||
        step === "free" ||
        m.metadata?.type === "onboarding_selection");
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
      prefSaved: !!prefSaved,
      prefLabel:
        step === "experience"
          ? "Experience saved"
          : step === "department"
            ? "Department saved"
            : step === "goal"
              ? "Goal saved"
              : prefSaved
                ? "Noted in your preferences"
                : null,
    };
  });
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

const PREF_CHIP_TITLES = {
  experience: "Experience level",
  department: "Department",
  goal: "Career goal",
};

function PreferenceBar({ profile, saveFlash, identityLabel, onSelectPreference, disabled }) {
  const [openKey, setOpenKey] = useState(null);
  const barRef = useRef(null);

  const chips = [
    { key: "experience", label: "Exp", value: profile.experience },
    { key: "department", label: "Dept", value: profile.department },
    { key: "goal", label: "Goal", value: profile.goal },
  ];
  const filled = chips.filter((c) => c.value).length;
  const statusText =
    filled === 0
      ? "Click a chip to set preferences"
      : filled < 3
        ? `${filled} of 3 · click a chip to change`
        : "Click a chip to change anytime";

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
    <div className="pref-bar" aria-live="polite" ref={barRef}>
      <div className="pref-bar-top">
        <div className="pref-status">
          <svg className="pref-status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
            <polyline points="17 21 17 13 7 13 7 21" />
            <polyline points="7 3 7 8 15 8" />
          </svg>
          <span>
            <strong>{statusText}</strong>
            {identityLabel ? ` · ${identityLabel}` : ""}
          </span>
        </div>
        {saveFlash ? <span className="pref-saved-flash">{saveFlash}</span> : null}
      </div>
      <div className="pref-chips">
        {chips.map((chip) => {
          const isOpen = openKey === chip.key;
          const options = PREF_CHIP_OPTIONS[chip.key] || [];
          return (
            <div key={chip.key} className="pref-chip-wrap">
              <button
                type="button"
                className={`pref-chip${chip.value ? "" : " empty"}${isOpen ? " open" : ""}`}
                title={
                  chip.value
                    ? `Change ${PREF_CHIP_TITLES[chip.key]}`
                    : `Set ${PREF_CHIP_TITLES[chip.key]}`
                }
                aria-haspopup="listbox"
                aria-expanded={isOpen}
                aria-label={`${PREF_CHIP_TITLES[chip.key]}: ${chip.value || "not set"}. Click to change.`}
                disabled={disabled}
                onClick={() => handleChipClick(chip.key)}
              >
                <span className="pref-chip-dot" />
                <span className="pref-chip-label">{chip.label}</span>
                <span className="pref-chip-value">
                  {chip.value || "—"}
                </span>
                <svg className="pref-chip-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              {isOpen ? (
                <div className="pref-chip-menu" role="listbox" aria-label={PREF_CHIP_TITLES[chip.key]}>
                  <div className="pref-chip-menu-title">{PREF_CHIP_TITLES[chip.key]}</div>
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
    </div>
  );
}

function PrefSavedNote({ label }) {
  if (!label) return null;
  return (
    <span className="pref-note">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="20 6 9 17 4 12" />
      </svg>
      {label}
    </span>
  );
}

function MessageContent({ msg }) {
  if (msg.sender === "user" || msg.streaming) {
    return <p className="stream-plain">{msg.text}</p>;
  }

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
      {msg.text}
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
  const [saveFlash, setSaveFlash] = useState(null);
  const [welcomeBack, setWelcomeBack] = useState(null);
  const stepRef = useRef("experience");
  const profileRef = useRef({});
  const sendingRef = useRef(false);
  const streamAbortRef = useRef(null);
  const sessionInitStarted = useRef(false);
  const timeoutsRef = useRef([]);
  const saveFlashTimerRef = useRef(null);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);
  const isMobile = useIsMobile();

  const identityLabel = getRegisteredUserId() ? "Signed in" : "Guest";

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

  const flashPreferenceSaved = (label) => {
    if (saveFlashTimerRef.current) clearTimeout(saveFlashTimerRef.current);
    setSaveFlash(label);
    saveFlashTimerRef.current = setTimeout(() => {
      setSaveFlash(null);
      saveFlashTimerRef.current = null;
    }, 2200);
  };

  useEffect(() => {
    return () => {
      abortActiveStream();
      timeoutsRef.current.forEach(clearTimeout);
      if (saveFlashTimerRef.current) clearTimeout(saveFlashTimerRef.current);
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

  const flashLabels = {
    experience: "Experience updated",
    department: "Department updated",
    goal: "Goal updated",
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

    const applyBotMessage = (text, streaming) => {
      // Only offer Speak with Agent after password/generic tickets — not after
      // agent or certificate confirmations (those are final in-chat acks).
      const supportOpts =
        !streaming &&
        isSupportHandoffText(text) &&
        !isSupportConfirmationOnly(text) &&
        !isSpeakWithAgentSelection(supportCheckText)
          ? [SPEAK_WITH_AGENT_OPTION]
          : undefined;

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
            options: supportOpts,
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
                ...(supportOpts ? { options: supportOpts } : {}),
                ...(!streaming && !supportOpts && msg.options
                  ? { options: undefined }
                  : {}),
              }
            : msg
        )
      );
    };

    const flushStreamUpdate = () => {
      streamRafId = null;
      applyBotMessage(pendingStreamText, true);
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
      applyBotMessage(fullText, false);
      return { ok: true, aborted: false, text: fullText };
    } catch (err) {
      if (streamRafId !== null) {
        cancelAnimationFrame(streamRafId);
        streamRafId = null;
      }
      if (err.name === "AbortError") {
        return { ok: false, aborted: true, text: "" };
      }
      applyBotMessage("Sorry, something went wrong.", false);
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
    flashPreferenceSaved(
      shouldRecommend
        ? "Goal updated — refreshing recommendations"
        : flashLabels[key] || "Preference updated"
    );

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
            prefSaved: true,
            prefLabel: "Goal updated — refreshing recommendations",
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
        flashPreferenceSaved("Recommendations updated");
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
      "Welcome! I'm here to help you find the perfect courses. I'll quietly save your preferences as we go so next time can pick up where you left off.";
    setMessages([{
      id: newMessageId(),
      sender: "bot",
      time: getTime(),
      text: welcomeText,
    }]);
    persistBotMessage(sid, welcomeText, { step: "welcome", type: "onboarding" });

    scheduleMsg(1000, {
      sender: "bot",
      text: "To get started, what's your current experience level?",
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
    setSaveFlash(null);
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
            if (profileHasAny(restored)) {
              setWelcomeBack(
                profileIsComplete(restored)
                  ? "Welcome back — your conversation and preferences were restored."
                  : "Welcome back — we restored what we already know about your preferences."
              );
            } else {
              setWelcomeBack("Welcome back — your conversation was restored.");
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
        setWelcomeBack(
          profileIsComplete(data.profile)
            ? "We remembered your preferences from earlier visits."
            : "Some of your preferences were restored from earlier visits."
        );
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

    const prefLabel =
      currentStep === "experience"
        ? "Experience saved"
        : currentStep === "department"
          ? "Department saved"
          : currentStep === "goal"
            ? "Goal saved"
            : "Noted in your preferences";

    const userMessage = {
      id: newMessageId(),
      text: messageToSend,
      sender: "user",
      time: getTime(),
      prefSaved: true,
      prefLabel,
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
        flashPreferenceSaved(
          currentStep === "experience" ? "Experience saved" : "Department saved"
        );

        if (currentStep === "experience") {
          scheduleMsg(600, {
            sender: "bot",
            text: "Got it — saved. Which department are you in?",
            options: DEPARTMENT_OPTIONS,
            metadata: { step: "department", type: "onboarding", options: DEPARTMENT_OPTIONS },
          }, sessionId);
          setConversationStep("department");
          stepRef.current = "department";
        } else {
          scheduleMsg(600, {
            sender: "bot",
            text: "Noted. Are you looking to earn a specific certification, get a promotion, or just upskill?",
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
      flashPreferenceSaved("Goal saved — profile ready");
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
      } else if (currentStep === "free") {
        flashPreferenceSaved("Preferences updated");
      }
    } finally {
      sendingRef.current = false;
    }
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, welcomeBack, saveFlash]);

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
          saveFlash={saveFlash}
          identityLabel={identityLabel}
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
            <div className="pref-welcome" role="status">
              <strong>Preferences</strong> — {welcomeBack}
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
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', width: '100%', alignItems: msg.sender === "user" ? "flex-end" : "flex-start" }}>
                  <div className={`bubble ${msg.sender}`}>
                    <MessageContent msg={msg} />
                  </div>
                  {msg.sender === "user" && msg.prefSaved ? (
                    <PrefSavedNote label={msg.prefLabel || "Saved to your preferences"} />
                  ) : null}
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
            <button className="icon-btn" title="Attach file">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
              </svg>
            </button>
            <button className="icon-btn" title="Add emoji">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
                <line x1="9" y1="9" x2="9.01" y2="9"/>
                <line x1="15" y1="9" x2="15.01" y2="9"/>
              </svg>
            </button>
            <input
              ref={inputRef}
              className="chat-input"
              type="text"
              placeholder={
                conversationStep === "free" || profileIsComplete(profile)
                  ? "Ask anything — preferences stay with you"
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
          <div className="pref-footer" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span>
              {profileIsComplete(profile)
                ? "Click chips above to change preferences anytime"
                : "Click chips above or answer prompts — both save"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}