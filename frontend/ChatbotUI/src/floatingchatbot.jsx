import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');

  .chatbot-root {
    font-family: 'Source Sans 3', Helvetica, Arial, sans-serif;
    color: #18181b;
  }

  .chat-fab {
    position: fixed;
    bottom: 28px;
    right: 28px;
    width: 56px;
    height: 56px;
    border-radius: 14px;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #9A1B22;
    box-shadow: 0 8px 32px rgba(154,27,34,0.35), 0 2px 8px rgba(0,0,0,0.18);
    transition: transform 0.25s cubic-bezier(.34,1.56,.64,1), box-shadow 0.25s ease;
    z-index: 9999;
    padding: 0;
  }
  .chat-fab:hover {
    transform: scale(1.05);
    box-shadow: 0 12px 40px rgba(154,27,34,0.45), 0 4px 12px rgba(0,0,0,0.2);
  }

  .chat-window {
    position: fixed;
    bottom: 100px;
    right: 28px;
    width: 400px;
    height: 640px;
    max-height: calc(100vh - 120px);
    background: #ffffff;
    border-radius: 18px;
    box-shadow:
      0 12px 48px rgba(0,0,0,0.15),
      0 4px 16px rgba(0,0,0,0.08),
      0 0 0 1px rgba(0,0,0,0.05);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    z-index: 9998;
    transform-origin: bottom right;
    transition: opacity 0.28s cubic-bezier(.4,0,.2,1),
                transform 0.28s cubic-bezier(.34,1.56,.64,1),
                width 0.2s ease, height 0.2s ease, bottom 0.2s ease, right 0.2s ease;
  }
  .chat-window.open   { opacity: 1; transform: scale(1) translateY(0); pointer-events: all; }
  .chat-window.closed { opacity: 0; transform: scale(0.88) translateY(16px); pointer-events: none; }
  .chat-window.expanded {
    width: min(720px, calc(100vw - 32px));
    height: min(860px, calc(100vh - 40px));
    bottom: 20px;
    right: 16px;
    max-height: calc(100vh - 40px);
  }

  .chat-header {
    background: #9A1B22;
    padding: 10px 12px 10px 10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex: 0 0 auto;
    color: white;
    gap: 8px;
  }
  .header-left { display: flex; align-items: center; gap: 8px; min-width: 0; }
  .header-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }

  .mode-toggle {
    display: flex;
    align-items: center;
    gap: 2px;
    background: rgba(255,255,255,0.12);
    border-radius: 999px;
    padding: 3px;
  }
  .mode-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    border: none;
    background: transparent;
    color: rgba(255,255,255,0.88);
    font: inherit;
    font-size: 12px;
    font-weight: 600;
    padding: 5px 10px;
    border-radius: 999px;
    cursor: pointer;
    line-height: 1;
  }
  .mode-btn.active {
    background: #ffffff;
    color: #9A1B22;
  }
  .mode-btn:disabled { opacity: 0.55; cursor: not-allowed; }

  .header-icon-btn {
    background: transparent;
    border: none;
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    opacity: 0.92;
    padding: 0;
  }
  .header-icon-btn:hover { opacity: 1; background: rgba(255,255,255,0.08); }

  .chat-messages {
    flex: 1 1 0;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 16px 14px 8px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    background: #ffffff;
    scroll-behavior: smooth;
  }
  .chat-messages::-webkit-scrollbar { width: 6px; }
  .chat-messages::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.12); border-radius: 8px; }

  .msg-wrapper {
    display: flex;
    flex-direction: column;
    gap: 8px;
    animation: msg-in 0.28s cubic-bezier(.4,0,.2,1) both;
  }
  @keyframes msg-in {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .bot-attr {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .bot-attr-label {
    font-size: 12px;
    font-weight: 600;
    color: #5b6577;
  }
  .bot-attr-spacer { flex: 1; }
  .thumb-btn {
    background: none;
    border: none;
    padding: 2px;
    cursor: pointer;
    color: #c5cad3;
    display: flex;
    line-height: 0;
  }
  .thumb-btn:hover { color: #7b8494; }
  .thumb-btn.active { color: #9A1B22; }

  .ai-avatar, .user-avatar {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    overflow: hidden;
  }
  .ai-avatar { background: #9A1B22; }
  .user-avatar { background: #1b2433; color: #fff; }

  .bot-stack {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-left: 36px;
  }

  .bubble {
    max-width: 88%;
    padding: 10px 14px;
    font-size: 14px;
    line-height: 1.45;
    word-break: break-word;
    border-radius: 14px;
  }
  .bubble.bot {
    background: #f4f4f5;
    color: #18181b;
    border-top-left-radius: 6px;
    max-width: 100%;
  }
  .bubble.bot.plain {
    background: transparent;
    padding: 0 2px;
    border-radius: 0;
    color: #3f3f46;
  }
  .bubble.user {
    background: #1e3a8a;
    color: #ffffff;
    border-top-right-radius: 6px;
    margin-left: auto;
  }
  .bubble p { margin: 0 0 8px; }
  .bubble p:last-child { margin-bottom: 0; }
  .bubble strong { font-weight: 700; }
  .bubble.bot strong { color: #18181b; }
  .bubble a { color: #2563eb; font-weight: 600; }
  .bubble.user a { color: #bfdbfe; }
  .bubble.user strong { color: #ffffff; }
  .bubble ul, .bubble ol {
    margin: 6px 0 8px;
    padding-left: 1.3em;
    list-style-position: outside;
  }
  .bubble ul { list-style-type: disc; }
  .bubble ol { list-style-type: decimal; }
  .bubble li { display: list-item; margin: 3px 0; }
  .bubble li > p { margin: 0; }
  .stream-plain { margin: 0; white-space: pre-wrap; }

  .user-row {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 6px;
  }
  .user-seen {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: #7b8494;
  }

  .course-card {
    position: relative;
    background: #faf7f7;
    border: 1px solid #efe7e7;
    border-radius: 16px;
    padding: 16px 16px 14px;
    width: 100%;
    box-sizing: border-box;
  }
  .course-copy {
    position: absolute;
    top: 10px;
    right: 10px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    border: 1px solid #d7dee8;
    background: #fff;
    color: #5b6577;
    font: inherit;
    font-size: 11px;
    font-weight: 600;
    border-radius: 8px;
    padding: 4px 8px;
    cursor: pointer;
  }
  .course-copy:hover { background: #faf7f7; color: #9A1B22; }
  .course-title {
    margin: 0 36px 6px 0;
    font-size: 15px;
    font-weight: 700;
    line-height: 1.3;
    color: #18181b;
  }
  .course-desc {
    margin: 0 0 12px;
    font-size: 13px;
    line-height: 1.4;
    color: #4b5568;
  }
  .course-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px 16px;
    font-size: 13px;
    font-weight: 600;
    color: #334155;
    margin-bottom: 10px;
  }
  .course-meta-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .course-meta-item svg { color: #64748b; }
  .course-features {
    list-style: none;
    margin: 0 0 12px;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .course-features li {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 13px;
    color: #334155;
    line-height: 1.35;
  }
  .course-features li svg { flex-shrink: 0; margin-top: 1px; color: #16a34a; }
  .course-learn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: #9A1B22;
    font-size: 13px;
    font-weight: 700;
    text-decoration: none;
  }
  .course-learn:hover { text-decoration: underline; }

  .options-container {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding-left: 36px;
  }
  .option-btn {
    background: #f4f4f5;
    border: none;
    border-radius: 999px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 700;
    color: #18181b;
    cursor: pointer;
  }
  .option-btn:hover:not(:disabled) { background: #e4e4e7; }
  .option-btn:disabled { opacity: 0.55; cursor: not-allowed; }

  .typing-indicator { display: flex; align-items: flex-start; gap: 8px; animation: msg-in 0.28s both; }
  .typing-bubble {
    background: #f4f4f5; border-radius: 14px; border-top-left-radius: 6px;
    padding: 14px 16px; display: flex; gap: 5px; align-items: center;
  }
  .dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: #a0a8b6;
    animation: dot-bounce 1.4s ease-in-out infinite;
  }
  .dot:nth-child(2) { animation-delay: 0.2s; }
  .dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes dot-bounce {
    0%,80%,100% { transform: translateY(0); opacity: 0.5; }
    40% { transform: translateY(-4px); opacity: 1; }
  }

  .chat-footer {
    flex: 0 0 auto;
    padding: 8px 12px 12px;
    background: #fff;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .handoff-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    background: #f3f5f8;
    border-radius: 12px;
    padding: 10px 12px;
    border: none;
    width: 100%;
    text-align: left;
    cursor: pointer;
    font: inherit;
    color: inherit;
  }
  .handoff-banner:hover { background: #ebeef3; }
  .handoff-banner:disabled { opacity: 0.6; cursor: not-allowed; }
  .handoff-icon {
    width: 28px; height: 28px; border-radius: 50%;
    background: #e2e8f0; color: #475569;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  }
  .handoff-copy {
    flex: 1;
    font-size: 13px;
    color: #3a4558;
  }
  .handoff-cta {
    font-size: 13px;
    font-weight: 700;
    color: #9A1B22;
    white-space: nowrap;
    display: inline-flex;
    align-items: center;
    gap: 2px;
  }

  .input-wrapper {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #fff;
    border: 1.5px solid #e4e4e7;
    border-radius: 999px;
    padding: 6px 8px 6px 16px;
  }
  .input-wrapper:focus-within { border-color: #d4d4d8; }
  .chat-input {
    flex: 1;
    border: none;
    background: transparent;
    outline: none;
    font-family: inherit;
    font-size: 14px;
    color: #18181b;
    padding: 6px 0;
  }
  .chat-input::placeholder { color: #8b93a2; }
  .chat-input:disabled { cursor: not-allowed; }
  .attach-icon {
    color: #9aa3b2;
    display: flex;
    flex-shrink: 0;
  }
  .send-btn {
    width: 34px; height: 34px; border-radius: 50%; border: none; cursor: pointer;
    background: #e8eaee;
    color: #8b93a2;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }
  .send-btn.active { background: #9A1B22; color: #fff; }
  .send-btn:disabled { opacity: 0.55; cursor: not-allowed; }

  .welcome-back {
    margin: 0;
    padding: 6px 10px;
    border-radius: 8px;
    background: #f7f8fb;
    color: #6b7384;
    font-size: 12px;
  }

  @media (max-width: 600px) {
    .chat-window {
      position: fixed;
      top: 0; right: 0; bottom: 0; left: 0;
      width: 100%; height: 100%; max-height: 100%;
      border-radius: 0;
    }
    .chat-window.expanded { width: 100%; height: 100%; bottom: 0; right: 0; }
    .chat-window.open   { transform: translateY(0); }
    .chat-window.closed { transform: translateY(100%); }
    .chat-header { padding-top: max(10px, env(safe-area-inset-top, 10px)); }
    .chat-footer { padding-bottom: max(12px, env(safe-area-inset-bottom, 12px)); }
  }
`;

const SESSION_STORAGE_KEY = "mc_chat_session_id";
const GUEST_STORAGE_KEY = "mc_guest_id";
const SPEAK_WITH_AGENT_OPTION = "Speak with Agent";
const WELCOME_TEXT =
  "Hi — ask me about Management Concepts courses, certifications, or training. I'll recommend options as we go.";

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
    lower.includes("sent to our support team") ||
    lower.includes("password change request has been sent") ||
    lower.includes("speak with an agent has been sent")
  );
}

function offersSpeakWithAgentChip(text) {
  if (!text) return false;
  const lower = text.toLowerCase();
  return (
    lower.includes("select") &&
    lower.includes("speak with agent") &&
    lower.includes("below")
  );
}

function isSupportConfirmationOnly(text) {
  if (!text) return false;
  const lower = text.toLowerCase();
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

function mapHistoryToMessages(apiMessages) {
  const visible = apiMessages.filter((m) => m.metadata?.visible !== false);
  return visible.map((m, i, arr) => {
    const hasReplyAfter = arr.slice(i + 1).some((next) => next.role === "user");
    const text = m.display_content || m.content;
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

const TITLE_RE = /^\*\*(?!(?:Duration|Credits|Cost|Level)\b)(.+?)\*\*\s*$/;
const FACT_RE = /^\*{0,2}(Duration|Credits|Cost|Level)\*{0,2}:\s*(.+)$/i;
const LINK_RE = /^\[(Register Now|Learn more)\]\((https?:\/\/[^)]+)\)/i;

function tryParseCourseCard(lines, start) {
  const titleMatch = String(lines[start] || "").trim().match(TITLE_RE);
  if (!titleMatch) return null;

  const card = {
    title: titleMatch[1].trim(),
    duration: null,
    credits: null,
    cost: null,
    level: null,
    url: null,
  };
  let j = start + 1;
  while (j < lines.length) {
    const t = String(lines[j] || "").trim();
    if (!t) {
      j += 1;
      continue;
    }
    const fact = t.match(FACT_RE);
    if (fact) {
      const key = fact[1].toLowerCase();
      card[key === "cost" ? "cost" : key] = fact[2].trim();
      j += 1;
      continue;
    }
    const link = t.match(LINK_RE);
    if (link) {
      card.url = link[2].trim();
      j += 1;
      break;
    }
    break;
  }
  if (!card.url) return null;
  return { card, nextIndex: j };
}

/** Split a finished bot reply into prose vs recommended-course cards. */
function parseBotSegments(raw) {
  const text = String(raw || "").replace(/\r\n/g, "\n").trim();
  if (!text) return [];

  const lines = text.split("\n");
  const segments = [];
  let textBuf = [];
  let i = 0;

  const flushText = () => {
    const t = textBuf.join("\n").trim();
    textBuf = [];
    if (t) segments.push({ type: "text", text: t });
  };

  while (i < lines.length) {
    if (TITLE_RE.test(String(lines[i] || "").trim())) {
      const parsed = tryParseCourseCard(lines, i);
      if (parsed) {
        flushText();
        segments.push({ type: "course", card: parsed.card });
        i = parsed.nextIndex;
        continue;
      }
    }
    textBuf.push(lines[i]);
    i += 1;
  }
  flushText();
  return segments;
}

function promoteOutlineLinesToList(text) {
  const headerRe =
    /^(?:\*\*)?(?:course\s+)?(?:highlights?|key\s+points?|learning\s+objectives?|objectives?|topics?(?:\s+covered)?|what\s+you(?:'|’)?ll\s+learn|benefits?|includes?|features?|takeaways?)(?:\*\*)?\s*:?\s*$/i;
  const isListLine = (line) =>
    /^\s*(?:[-*+]|\d+[.)])\s+\S/.test(line) ||
    /^\s*[•●○◆◇▪▫■□‣∙·–—]\s+\S/.test(line);
  const isStopLine = (t) =>
    !t ||
    /^#{1,6}\s/.test(t) ||
    /^\[Register Now\]/i.test(t) ||
    /^\*{0,2}(?:Duration|Credits|Cost|Level)\*{0,2}:/i.test(t) ||
    (/^\*\*[^*].+\*\*\s*$/.test(t) && !/:\s*$/.test(t));

  const lines = text.split("\n");
  const out = [];
  for (let i = 0; i < lines.length; i++) {
    out.push(lines[i]);
    if (!headerRe.test(lines[i].trim())) continue;

    const block = [];
    let j = i + 1;
    while (j < lines.length) {
      const raw = lines[j];
      const t = raw.trim();
      if (isStopLine(t)) break;
      block.push(raw);
      j++;
    }
    if (block.length >= 2 && block.every((l) => !isListLine(l))) {
      for (const bl of block) out.push(`- ${bl.trim()}`);
      i = j - 1;
    }
  }
  return out.join("\n");
}

function normalizeBotMarkdown(raw) {
  let text = String(raw || "").replace(/\r\n/g, "\n");
  text = text.replace(
    /(^|\n)([ \t]*)(?:[•●○◆◇▪▫■□‣∙·])(?=\s+\S)/g,
    "$1$2-"
  );
  text = text.replace(
    /(^|\n)([ \t]*)(?:–|—)(?=\s+\S)/g,
    "$1$2-"
  );
  text = promoteOutlineLinesToList(text);
  text = text.replace(
    /(^|\n)(\*{0,2}(?:Duration|Credits|Cost|Level)\*{0,2}:|\[Register Now\])/g,
    "\n\n$2"
  );
  text = text.replace(
    /(^|\n)((?:[-*+]|\d+[.)]) [^\n]*)\n\n+(?=(?:[-*+]|\d+[.)]) )/g,
    "$1$2\n"
  );
  text = text.replace(
    /(^|\n)([^\n]+)\n((?:[-*+]|\d+[.)]) )/g,
    (match, lead, prevLine, marker) => {
      if (/^\s*(?:[-*+]|\d+[.)])\s/.test(prevLine)) return match;
      if (/^\s*$/.test(prevLine)) return match;
      return `${lead}${prevLine}\n\n${marker}`;
    }
  );
  return text.replace(/\n{3,}/g, "\n\n").trim();
}

function creditFeatures(credits) {
  if (!credits) return [];
  return credits
    .split("|")
    .map((part) => part.trim())
    .filter(Boolean);
}

function McFlag({ size = 32, radius = 8 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx={radius} fill="#ffffff" />
      <rect x="3" y="6" width="26" height="20" rx="1.5" fill="#0E2A5C" />
      <rect x="3" y="6" width="12" height="11" fill="#C8102E" />
      <path
        d="M15 8h14v1.7H15zm0 3.4h14v1.7H15zm0 3.4h14v1.7H15zM3 18.2h26v1.7H3zm0 3.4h26v1.7H3z"
        fill="#ffffff"
      />
    </svg>
  );
}

function PersonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 21a8 8 0 0 0-16 0" />
      <circle cx="12" cy="8" r="4" />
    </svg>
  );
}

function BotIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="4" y="8" width="16" height="12" rx="3" />
      <path d="M12 8V5" />
      <circle cx="12" cy="4" r="1.4" fill="currentColor" />
      <circle cx="9" cy="14" r="1" fill="currentColor" />
      <circle cx="15" cy="14" r="1" fill="currentColor" />
    </svg>
  );
}

function MarkdownBody({ text }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p>{children}</p>,
        ul: ({ children }) => <ul>{children}</ul>,
        ol: ({ children }) => <ol>{children}</ol>,
        li: ({ children }) => <li>{children}</li>,
        a: ({ href, children, ...props }) => {
          const isContact = Boolean(href && (href.startsWith("tel:") || href.startsWith("mailto:")));
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
      {normalizeBotMarkdown(text)}
    </ReactMarkdown>
  );
}

function CourseCard({ card }) {
  const [copied, setCopied] = useState(false);
  const features = creditFeatures(card.credits);
  if (card.level) features.push(`${card.level} level`);

  const copyCard = async () => {
    const snippet = [card.title, card.url].filter(Boolean).join("\n");
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  };

  return (
    <article className="course-card">
      <button type="button" className="course-copy" onClick={copyCard} title="Copy course">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <rect x="9" y="9" width="13" height="13" rx="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
        {copied ? "Copied" : "Copy"}
      </button>
      <h3 className="course-title">{card.title}</h3>
      {(card.duration || card.cost) && (
        <div className="course-meta">
          {card.duration ? (
            <span className="course-meta-item">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 7v5l3 2" />
              </svg>
              {card.duration}
            </span>
          ) : null}
          {card.cost ? <span className="course-meta-item">{card.cost}</span> : null}
        </div>
      )}
      {features.length > 0 && (
        <ul className="course-features">
          {features.map((feat) => (
            <li key={feat}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" aria-hidden="true">
                <path d="M5 12.5l4 4 10-10" />
              </svg>
              {feat}
            </li>
          ))}
        </ul>
      )}
      {card.url ? (
        <a className="course-learn" href={card.url} target="_blank" rel="noopener noreferrer">
          Learn more
          <span aria-hidden="true">→</span>
        </a>
      ) : null}
    </article>
  );
}

function BotMessageBody({ msg }) {
  if (msg.streaming) {
    return (
      <div className="bubble bot">
        <p className="stream-plain">{msg.text}</p>
      </div>
    );
  }

  const segments = parseBotSegments(msg.text);
  const hasCards = segments.some((s) => s.type === "course");
  if (!hasCards) {
    return (
      <div className="bubble bot">
        <MarkdownBody text={msg.text} />
      </div>
    );
  }

  const firstCardAt = segments.findIndex((s) => s.type === "course");
  return (
    <div className="bot-stack">
      {segments.map((seg, idx) => {
        if (seg.type === "course") {
          return <CourseCard key={`c-${idx}`} card={seg.card} />;
        }
        const plainAfterCard = firstCardAt !== -1 && idx > firstCardAt;
        return (
          <div key={`t-${idx}`} className={`bubble bot${plainAfterCard ? " plain" : ""}`}>
            <MarkdownBody text={seg.text} />
          </div>
        );
      })}
    </div>
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

export default function FloatingChatbot() {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sessionInitializing, setSessionInitializing] = useState(false);
  const [welcomeBack, setWelcomeBack] = useState(null);
  const [mode, setMode] = useState("ai");
  const [thumbs, setThumbs] = useState({});
  const sendingRef = useRef(false);
  const streamAbortRef = useRef(null);
  const sessionInitStarted = useRef(false);
  const welcomeTimerRef = useRef(null);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);
  const isMobile = useIsMobile();

  const abortActiveStream = () => {
    streamAbortRef.current?.abort();
    streamAbortRef.current = null;
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
      if (welcomeTimerRef.current) clearTimeout(welcomeTimerRef.current);
    };
  }, []);

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

  const showWelcome = (sid) => {
    setMessages([
      {
        id: newMessageId(),
        sender: "bot",
        time: getTime(),
        text: WELCOME_TEXT,
      },
    ]);
    persistBotMessage(sid, WELCOME_TEXT, { type: "welcome" });
  };

  const startNewChat = async () => {
    abortActiveStream();
    sendingRef.current = false;
    localStorage.removeItem(SESSION_STORAGE_KEY);
    setMessages([]);
    setWelcomeBack(null);
    setLoading(false);
    setInput("");
    setMode("ai");
    setThumbs({});
    setExpanded(false);

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
      showWelcome(newId);
    } catch {
      setSessionId(null);
      setMessages([
        {
          id: newMessageId(),
          text: "Error connecting to server. Make sure the backend is running.",
          sender: "bot",
          time: getTime(),
        },
      ]);
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
            showWelcomeBack("Welcome back — conversation restored.");
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
      showWelcome(newId);
    } catch {
      setMessages([
        {
          id: newMessageId(),
          text: "Error connecting to server. Make sure the backend is running.",
          sender: "bot",
          time: getTime(),
        },
      ]);
    } finally {
      setSessionInitializing(false);
    }
  };

  const sendMessage = async (overrideText) => {
    const messageToSend = typeof overrideText === "string" ? overrideText : input;
    if (!messageToSend.trim() || !sessionId || loading || sendingRef.current) return;

    sendingRef.current = true;

    const userMessage = {
      id: newMessageId(),
      text: messageToSend,
      sender: "user",
      time: getTime(),
    };

    setMessages((prev) => {
      const updatedPrev = prev.map((msg) =>
        msg.options && !msg.optionsDisabled ? { ...msg, optionsDisabled: true } : msg
      );
      return [...updatedPrev, userMessage];
    });
    setInput("");

    if (isSpeakWithAgentSelection(messageToSend)) {
      setMode("human");
    }

    try {
      await streamChatResponse({
        sid: sessionId,
        backendMessage: messageToSend,
        displayMessage: messageToSend,
        metadata: { step: "free" },
        supportCheckText: messageToSend,
      });
    } finally {
      sendingRef.current = false;
    }
  };

  const connectToHuman = () => {
    if (loading || sendingRef.current || !sessionId) return;
    if (mode === "human") return;
    setMode("human");
    sendMessage(SPEAK_WITH_AGENT_OPTION);
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

  const lastUserIndex = messages.reduce(
    (acc, msg, idx) => (msg.sender === "user" ? idx : acc),
    -1
  );
  const inputDisabled = sessionInitializing || !sessionId || loading;
  const canSend = !inputDisabled && Boolean(input.trim());

  return (
    <div className="chatbot-root">
      <style>{styles}</style>

      {(!isMobile || !open) && (
        <button className="chat-fab" onClick={handleOpen} title="Course advisor">
          <McFlag size={40} radius={10} />
        </button>
      )}

      <div className={`chat-window ${open ? "open" : "closed"}${expanded ? " expanded" : ""}`}>
        <div className="chat-header">
          <div className="header-left">
            <McFlag size={36} radius={9} />
          </div>
          <div className="header-right">
            <div className="mode-toggle" role="group" aria-label="Assistant mode">
              <button
                type="button"
                className={`mode-btn${mode === "ai" ? " active" : ""}`}
                onClick={() => setMode("ai")}
              >
                <BotIcon size={14} />
                AI
              </button>
              <button
                type="button"
                className={`mode-btn${mode === "human" ? " active" : ""}`}
                disabled={inputDisabled}
                onClick={connectToHuman}
              >
                <PersonIcon />
                Human
              </button>
            </div>
            <button
              className="header-icon-btn"
              onClick={startNewChat}
              title="New chat"
              aria-label="New chat"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 5v14" />
                <path d="M5 12h14" />
              </svg>
            </button>
            <button
              className="header-icon-btn"
              onClick={() => setExpanded((v) => !v)}
              title={expanded ? "Exit full view" : "Expand"}
              aria-label={expanded ? "Exit full view" : "Expand"}
            >
              {expanded ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <polyline points="4 14 10 14 10 20" />
                  <polyline points="20 10 14 10 14 4" />
                  <line x1="14" y1="10" x2="21" y2="3" />
                  <line x1="3" y1="21" x2="10" y2="14" />
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <polyline points="15 3 21 3 21 9" />
                  <polyline points="9 21 3 21 3 15" />
                  <line x1="21" y1="3" x2="14" y2="10" />
                  <line x1="3" y1="21" x2="10" y2="14" />
                </svg>
              )}
            </button>
            <button className="header-icon-btn" onClick={() => setOpen(false)} title="Close" aria-label="Close">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        <div className="chat-messages">
          {sessionInitializing && messages.length === 0 && (
            <div className="typing-indicator">
              <div className="ai-avatar">
                <McFlag size={22} radius={11} />
              </div>
              <div className="typing-bubble">
                <div className="dot" /><div className="dot" /><div className="dot" />
              </div>
            </div>
          )}

          {welcomeBack && !sessionInitializing && (
            <p className="welcome-back" role="status">{welcomeBack}</p>
          )}

          {messages.map((msg, i) => {
            if (msg.sender === "user") {
              return (
                <div key={msg.id} className="msg-wrapper user">
                  <div className="user-row">
                    <div className="bubble user">
                      <p className="stream-plain">{msg.text}</p>
                    </div>
                    {i === lastUserIndex && (
                      <div className="user-seen">
                        Seen
                        <span className="user-avatar" aria-hidden="true">
                          <PersonIcon />
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              );
            }

            const segments = msg.streaming ? [] : parseBotSegments(msg.text);
            const hasCards = segments.some((s) => s.type === "course");

            return (
              <div key={msg.id} className="msg-wrapper bot">
                <div className="bot-attr">
                  <span className="ai-avatar" aria-hidden="true">
                    <McFlag size={22} radius={11} />
                  </span>
                  <span className="bot-attr-label">AI</span>
                  <span className="bot-attr-spacer" />
                  <button
                    type="button"
                    className={`thumb-btn${thumbs[msg.id] === "up" ? " active" : ""}`}
                    aria-label="Helpful"
                    onClick={() =>
                      setThumbs((prev) => ({
                        ...prev,
                        [msg.id]: prev[msg.id] === "up" ? null : "up",
                      }))
                    }
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill={thumbs[msg.id] === "up" ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
                      <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3z" />
                      <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    className={`thumb-btn${thumbs[msg.id] === "down" ? " active" : ""}`}
                    aria-label="Not helpful"
                    onClick={() =>
                      setThumbs((prev) => ({
                        ...prev,
                        [msg.id]: prev[msg.id] === "down" ? null : "down",
                      }))
                    }
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill={thumbs[msg.id] === "down" ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
                      <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3z" />
                      <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
                    </svg>
                  </button>
                </div>
                {hasCards ? (
                  <BotMessageBody msg={msg} />
                ) : (
                  <div className="bot-stack">
                    <BotMessageBody msg={msg} />
                  </div>
                )}
                {msg.options && (
                  <div className="options-container">
                    {msg.options.map((opt) => {
                      const isDisabled = loading || msg.optionsDisabled;
                      return (
                        <button
                          key={opt}
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
            );
          })}

          {loading && (
            <div className="typing-indicator">
              <div className="ai-avatar">
                <McFlag size={22} radius={11} />
              </div>
              <div className="typing-bubble">
                <div className="dot" /><div className="dot" /><div className="dot" />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="chat-footer">
          <button
            type="button"
            className="handoff-banner"
            onClick={connectToHuman}
            disabled={inputDisabled}
          >
            <span className="handoff-icon" aria-hidden="true">
              <PersonIcon />
            </span>
            <span className="handoff-copy">Want to talk to a real person?</span>
            <span className="handoff-cta">
              Connect now
              <span aria-hidden="true">›</span>
            </span>
          </button>
          <div className="input-wrapper">
            <input
              ref={inputRef}
              className="chat-input"
              type="text"
              placeholder="Ask a question..."
              value={input}
              disabled={inputDisabled}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            />
            <span className="attach-icon" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M21.44 11.05l-8.49 8.49a6 6 0 0 1-8.49-8.49l8.49-8.49a4 4 0 0 1 5.66 5.66l-8.49 8.49a2 2 0 1 1-2.83-2.83l8.49-8.5" />
              </svg>
            </span>
            <button
              className={`send-btn${canSend ? " active" : ""}`}
              onClick={sendMessage}
              disabled={!canSend}
              title="Send"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
