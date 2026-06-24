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
  .bot-badge {
    font-size: 10px; background: #e5e7eb; color: #4b5563;
    padding: 2px 6px; border-radius: 4px; font-weight: 600;
  }
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
    return {
      id: newMessageId(),
      text: m.display_content || m.content,
      sender: m.role === "user" ? "user" : "bot",
      time: formatTimeFromIso(m.created_at),
      options: m.metadata?.options,
      optionsDisabled: m.metadata?.options ? hasReplyAfter : undefined,
    };
  });
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
        a: ({ node, ...props }) => (
          <a {...props} target="_blank" rel="noopener noreferrer" />
        ),
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
  const stepRef = useRef("experience");
  const profileRef = useRef({});
  const sendingRef = useRef(false);
  const streamAbortRef = useRef(null);
  const sessionInitStarted = useRef(false);
  const timeoutsRef = useRef([]);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);
  const isMobile = useIsMobile();

  const abortActiveStream = () => {
    streamAbortRef.current?.abort();
    streamAbortRef.current = null;
  };

  useEffect(() => {
    return () => {
      abortActiveStream();
      timeoutsRef.current.forEach(clearTimeout);
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
        }),
      });
    } catch {
      // Non-blocking — chat still works if persistence fails
    }
  };

  const persistUserSelection = async (sid, step, value) => {
    const content =
      step === "experience"
        ? `My experience level is: ${value}.`
        : `My department is: ${value}.`;
    await fetch(`${API_BASE}/session/${sid}/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        role: "user",
        content,
        display_content: value,
        metadata: { step, value, type: "onboarding_selection" },
      }),
    });
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
    const welcomeText = "Welcome! I'm here to help you find the perfect courses.";
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
    profileRef.current = {};
    setLoading(false);
    setInput("");

    try {
      const res = await fetch(`${API_BASE}/session/start`, { method: "POST" });
      const data = await res.json();
      const newId = data.session_id;
      setSessionId(newId);
      localStorage.setItem(SESSION_STORAGE_KEY, newId);
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
            profileRef.current = extractProfileFromHistory(historyData.messages);
            return;
          }
        }
      }

      const res = await fetch(`${API_BASE}/session/start`, { method: "POST" });
      const data = await res.json();
      const newId = data.session_id;
      setSessionId(newId);
      localStorage.setItem(SESSION_STORAGE_KEY, newId);
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
        profileRef.current[currentStep] = messageToSend;

        if (currentStep === "experience") {
          scheduleMsg(600, {
            sender: "bot",
            text: "Got it! Which department are you in?",
            options: DEPARTMENT_OPTIONS,
            metadata: { step: "department", type: "onboarding", options: DEPARTMENT_OPTIONS },
          }, sessionId);
          setConversationStep("department");
          stepRef.current = "department";
        } else {
          scheduleMsg(600, {
            sender: "bot",
            text: "Are you looking to earn a specific certification, get a promotion, or just upskill?",
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

    abortActiveStream();
    setLoading(true);

    let backendMessage = messageToSend;
    let stepMetadata = { step: currentStep };

    if (currentStep === "goal") {
      const profile = { ...profileRef.current, goal: messageToSend };
      profileRef.current = profile;
      backendMessage =
        `My experience level is: ${profile.experience}. ` +
        `My department is: ${profile.department}. ` +
        `My career goal is: ${profile.goal}. ` +
        `Please recommend courses based on my profile.`;
      stepMetadata = {
        step: "goal",
        value: messageToSend,
        profile_complete: true,
        profile: {
          experience: profile.experience,
          department: profile.department,
          goal: profile.goal,
        },
        experience: profile.experience,
        department: profile.department,
        goal: profile.goal,
      };
    } else {
      stepMetadata = { step: "free" };
    }

    const botMessageId = newMessageId();
    let streamStarted = false;
    let streamRafId = null;
    let pendingStreamText = "";

    const applyBotMessage = (text, streaming) => {
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
          },
        ]);
        return;
      }
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === botMessageId ? { ...msg, text, streaming } : msg
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
          session_id: sessionId,
          message: backendMessage,
          display_message: messageToSend,
          metadata: stepMetadata,
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

      if (currentStep === "goal") {
        setConversationStep("free");
        stepRef.current = "free";
      }
    } catch (err) {
      if (err.name === "AbortError") return;
      if (streamRafId !== null) {
        cancelAnimationFrame(streamRafId);
        streamRafId = null;
      }
      applyBotMessage("Sorry, something went wrong.", false);
    } finally {
      if (streamAbortRef.current === abortController) {
        streamAbortRef.current = null;
      }
      sendingRef.current = false;
      setLoading(false);
    }
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

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

          {messages.map((msg, i) => {
            const isConsecutive = i > 0 && messages[i - 1].sender === msg.sender;
            return (
            <div key={msg.id} className={`msg-wrapper ${msg.sender}`}>
              {msg.sender === "bot" && !isConsecutive && (
                <div className="msg-meta bot">
                  <span className="sender-name">MCAgent</span>
                  <span className="bot-badge">BOT</span>
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
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
                  <div className={`bubble ${msg.sender}`}>
                    <MessageContent msg={msg} />
                  </div>
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
              placeholder="Write a message"
              value={input}
              disabled={sessionInitializing || !sessionId || loading || (messages.length > 0 && messages[messages.length - 1].options && !messages[messages.length - 1].optionsDisabled)}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            />
            <button
              className={`send-btn ${input.trim() ? 'active' : ''}`}
              onClick={sendMessage}
              disabled={sessionInitializing || !sessionId || loading || (messages.length > 0 && messages[messages.length - 1].options && !messages[messages.length - 1].optionsDisabled)}
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