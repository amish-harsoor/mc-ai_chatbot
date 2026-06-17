import { useState, useRef, useEffect } from "react";
import img from "./assets/img.png";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&family=Sora:wght@400;600;700&display=swap');

  .chatbot-root {
    font-family: 'DM Sans', sans-serif;
  }

  .chat-fab {
    position: fixed;
    bottom: 28px;
    right: 28px;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #90182A 0%, #b8203a 100%);
    box-shadow: 0 8px 32px rgba(144,24,42,0.45), 0 2px 8px rgba(0,0,0,0.18);
    transition: transform 0.25s cubic-bezier(.34,1.56,.64,1), box-shadow 0.25s ease;
    z-index: 9999;
  }
  .chat-fab:hover {
    transform: scale(1.1) rotate(8deg);
    box-shadow: 0 12px 40px rgba(144,24,42,0.55), 0 4px 12px rgba(0,0,0,0.2);
  }
  .chat-fab img { width: 32px; height: 32px; object-fit: contain; }
  .chat-fab::after {
    content: '';
    position: absolute;
    inset: -4px;
    border-radius: 50%;
    border: 2px solid rgba(144,24,42,0.35);
    animation: fab-pulse 2.4s ease-out infinite;
  }
  @keyframes fab-pulse {
    0%   { transform: scale(1);    opacity: 0.8; }
    100% { transform: scale(1.55); opacity: 0; }
  }

  .chat-window {
    position: fixed;
    bottom: 104px;
    right: 28px;
    width: 370px;
    height: 560px;
    max-height: calc(100vh - 130px);
    background: #ffffff;
    border-radius: 20px;
    box-shadow:
      0 24px 64px rgba(37,53,142,0.18),
      0 4px 16px rgba(0,0,0,0.08),
      0 0 0 1px rgba(37,53,142,0.08);
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
    background: linear-gradient(120deg, #1c2b80 0%, #25358E 55%, #2e45b0 100%);
    padding: 16px 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex: 0 0 auto;
    position: relative;
    overflow: hidden;
  }
  .chat-header::before {
    content: ''; position: absolute;
    top: -40px; right: -40px;
    width: 120px; height: 120px;
    border-radius: 50%;
    background: rgba(255,255,255,0.06);
    pointer-events: none;
  }
  .chat-header::after {
    content: ''; position: absolute;
    bottom: -30px; left: 60px;
    width: 80px; height: 80px;
    border-radius: 50%;
    background: rgba(255,255,255,0.04);
    pointer-events: none;
  }
  .header-left {
    display: flex; align-items: center; gap: 11px; z-index: 1;
  }
  .header-avatar {
    width: 40px; height: 40px;
    border-radius: 50%;
    background: rgba(255,255,255,0.15);
    backdrop-filter: blur(4px);
    border: 1.5px solid rgba(255,255,255,0.25);
    display: flex; align-items: center; justify-content: center;
    overflow: hidden; flex-shrink: 0;
  }
  .header-avatar img { width: 26px; height: 26px; object-fit: contain; }
  .header-title {
    font-family: 'Sora', sans-serif;
    font-size: 15px; font-weight: 600;
    color: #fff; letter-spacing: -0.01em; line-height: 1.2;
  }
  .header-subtitle {
    font-size: 11.5px; color: rgba(255,255,255,0.65);
    font-weight: 400; margin-top: 1px;
  }
  .status-dot {
    display: inline-block; width: 7px; height: 7px;
    border-radius: 50%; background: #4ade80; margin-right: 5px;
    box-shadow: 0 0 0 2px rgba(74,222,128,0.25);
    animation: blink 2.2s ease-in-out infinite;
  }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.45} }
  .close-btn {
    background: rgba(255,255,255,0.12); border: none;
    color: rgba(255,255,255,0.8);
    width: 32px; height: 32px; border-radius: 50%; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px;
    transition: background 0.2s, color 0.2s, transform 0.2s;
    flex-shrink: 0; z-index: 1;
  }
  .close-btn:hover { background: rgba(255,255,255,0.22); color: #fff; transform: rotate(90deg); }

  .chat-messages {
    flex: 1 1 0;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 18px 16px 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    background: #f7f8fc;
    scroll-behavior: smooth;
  }
  .chat-messages::-webkit-scrollbar       { width: 4px; }
  .chat-messages::-webkit-scrollbar-track  { background: transparent; }
  .chat-messages::-webkit-scrollbar-thumb  { background: rgba(37,53,142,0.18); border-radius: 8px; }

  .msg-row {
    display: flex; align-items: flex-end; gap: 7px;
    animation: msg-in 0.28s cubic-bezier(.4,0,.2,1) both;
  }
  @keyframes msg-in {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .msg-row.user { flex-direction: row-reverse; }
  .msg-row.bot  { flex-direction: row; }

  .bot-icon {
    width: 28px; height: 28px; border-radius: 50%;
    background: linear-gradient(135deg, #25358E, #3347c4);
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(37,53,142,0.22); overflow: hidden;
  }
  .bot-icon img { width: 18px; height: 18px; object-fit: contain; }

  .bubble {
    max-width: 78%; padding: 10px 14px;
    font-size: 13.5px; line-height: 1.6;
    word-break: break-word; position: relative;
  }
  .bubble.bot {
    background: #ffffff; color: #1a1f3d;
    border-radius: 18px 18px 18px 4px;
    box-shadow: 0 2px 10px rgba(37,53,142,0.09), 0 1px 3px rgba(0,0,0,0.06);
    border: 1px solid rgba(37,53,142,0.08);
  }
  .bubble.user {
    background: linear-gradient(135deg, #90182A 0%, #b8203a 100%);
    color: #ffffff; border-radius: 18px 18px 4px 18px;
    box-shadow: 0 4px 16px rgba(144,24,42,0.28), 0 1px 4px rgba(0,0,0,0.1);
  }
  .bubble p { margin: 0 0 6px; }
  .bubble p:last-child { margin-bottom: 0; }
  .bubble a { color: #fcd34d; text-decoration: underline; font-weight: 500; word-break: break-all; }
  .bubble.bot a { color: #25358E; }
  .bubble ul, .bubble ol { padding-left: 18px; margin: 4px 0; }
  .bubble code {
    background: rgba(255,255,255,0.15); border-radius: 4px;
    padding: 1px 5px; font-size: 12px;
  }
  .bubble.bot code { background: rgba(37,53,142,0.08); color: #25358E; }

  .msg-time { font-size: 10.5px; color: #a0aabf; margin-top: 3px; }
  .msg-row.bot  .msg-time { text-align: left;  padding-left: 35px; }
  .msg-row.user .msg-time { text-align: right; padding-right: 2px; }

  .typing-indicator { display: flex; align-items: center; gap: 7px; animation: msg-in 0.28s both; }
  .typing-bubble {
    background: #fff; border-radius: 18px 18px 18px 4px;
    padding: 11px 16px; display: flex; gap: 5px; align-items: center;
    box-shadow: 0 2px 10px rgba(37,53,142,0.09);
    border: 1px solid rgba(37,53,142,0.08);
  }
  .dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: #25358E; opacity: 0.4;
    animation: dot-bounce 1.2s ease-in-out infinite;
  }
  .dot:nth-child(2) { animation-delay: 0.18s; }
  .dot:nth-child(3) { animation-delay: 0.36s; }
  @keyframes dot-bounce {
    0%,80%,100% { transform: translateY(0);   opacity: 0.4; }
    40%          { transform: translateY(-6px); opacity: 1; }
  }

  .chat-divider { display: flex; align-items: center; gap: 8px; margin: 6px 0; }
  .chat-divider span { font-size: 10.5px; color: #b0b8cc; white-space: nowrap; }
  .chat-divider::before, .chat-divider::after {
    content: ''; flex: 1; height: 1px; background: rgba(37,53,142,0.1);
  }

  .section-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #9aa3bb;
    padding: 10px 0 2px 35px;
  }

  .chat-input-area {
    background: #fff; padding: 12px 14px;
    border-top: 1px solid rgba(37,53,142,0.09);
    display: flex; align-items: center; gap: 9px;
    flex: 0 0 auto;
  }
  .input-wrapper {
    flex: 1; display: flex; align-items: center;
    background: #f2f4fb; border: 1.5px solid rgba(37,53,142,0.12);
    border-radius: 24px; padding: 0 14px;
    transition: border-color 0.2s, box-shadow 0.2s; gap: 8px;
  }
  .input-wrapper:focus-within {
    border-color: #25358E; box-shadow: 0 0 0 3px rgba(37,53,142,0.1);
  }
  .chat-input {
    flex: 1; border: none; background: transparent; outline: none;
    font-family: 'DM Sans', sans-serif;
    font-size: 13.5px; color: #1a1f3d; padding: 10px 0;
  }
  .chat-input::placeholder { color: #9aa3bb; }
  .chat-input:disabled { cursor: not-allowed; opacity: 0.6; }

  .send-btn {
    width: 40px; height: 40px; border-radius: 50%; border: none; cursor: pointer;
    background: linear-gradient(135deg, #90182A 0%, #b8203a 100%);
    color: #fff; display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 4px 14px rgba(144,24,42,0.35);
    transition: transform 0.2s cubic-bezier(.34,1.56,.64,1), box-shadow 0.2s, opacity 0.2s;
  }
  .send-btn:hover:not(:disabled) { transform: scale(1.12); box-shadow: 0 6px 20px rgba(144,24,42,0.45); }
  .send-btn:disabled { opacity: 0.45; cursor: not-allowed; transform: none; }
  .send-btn svg { width: 18px; height: 18px; }

  .chat-footer {
    background: #fff; padding: 6px 14px 10px;
    text-align: center; font-size: 10.5px; color: #b0b8cc;
    border-top: 1px solid rgba(37,53,142,0.06);
    flex: 0 0 auto;
  }

  @media (min-width: 601px) and (max-width: 900px) {
    .chat-window {
      width: min(370px, calc(100vw - 56px));
      right: 20px;
    }
  }

  @media (max-width: 600px) {
    .chat-fab { bottom: 18px; right: 18px; width: 54px; height: 54px; }
    .chat-fab img { width: 28px; height: 28px; }

    .chat-window {
      position: fixed;
      top: 0; right: 0; bottom: 0; left: 0;
      width: 100%; height: 100%; max-height: 100%;
      border-radius: 0; box-shadow: none;
      transform-origin: bottom center;
    }
    .chat-window.open   { opacity: 1; transform: translateY(0);    pointer-events: all; }
    .chat-window.closed { opacity: 0; transform: translateY(100%); pointer-events: none; transition: opacity 0.25s ease, transform 0.3s cubic-bezier(.4,0,.2,1); }

    .chat-header {
      flex: 0 0 auto; padding: 12px 16px;
      padding-top: max(12px, env(safe-area-inset-top, 12px));
    }
    .header-avatar { width: 36px; height: 36px; }
    .header-avatar img { width: 22px; height: 22px; }
    .header-title    { font-size: 15px; }
    .header-subtitle { font-size: 11px; }

    .chat-messages { flex: 1 1 0; min-height: 0; padding: 14px 14px 10px; }

    .bubble     { font-size: 14px; max-width: 85%; }
    .bot-icon   { width: 26px; height: 26px; }
    .bot-icon img { width: 16px; height: 16px; }

    .chat-input-area {
      flex: 0 0 auto; padding: 10px 14px;
      padding-bottom: max(10px, env(safe-area-inset-bottom, 10px));
    }
    .chat-input { font-size: 16px; }
    .send-btn   { width: 44px; height: 44px; }
    .send-btn svg { width: 20px; height: 20px; }

    .chat-footer { flex: 0 0 auto; padding-bottom: 6px; }
  }

  @media (max-width: 380px) {
    .bubble       { font-size: 13.5px; padding: 9px 12px; }
    .header-title { font-size: 14px; }
  }

  @media (max-width: 600px) and (orientation: landscape) {
    .chat-header { padding: 8px 16px; padding-top: max(8px, env(safe-area-inset-top, 8px)); }
    .chat-messages { padding: 8px 14px 6px; gap: 7px; }
    .chat-input-area { padding: 8px 14px; padding-bottom: max(8px, env(safe-area-inset-bottom, 8px)); }
  }
`;

function getTime() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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

function scheduleMsg(setMessages, delay, msg) {
  return setTimeout(() => setMessages((prev) => [...prev, { ...msg, time: getTime() }]), delay);
}

export default function FloatingChatbot() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  // Tracks which guided step we're on: 'experience' → 'department' → 'goal' → 'free'
  const [conversationStep, setConversationStep] = useState("experience");
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);
  const isMobile = useIsMobile();
  const sessionStarted = useRef(false);

  useEffect(() => {
    if (sessionStarted.current) return;
    sessionStarted.current = true;

    const initSession = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/session/start", { method: "POST" });
        const data = await res.json();
        setSessionId(data.session_id);

        // Only show welcome + first question; everything else follows user responses
        setMessages([{
          sender: "bot",
          time: getTime(),
          text: "Welcome! I'm here to help you find the perfect courses.",
        }]);

        scheduleMsg(setMessages, 1000, {
          sender: "bot",
          text: "To get started, what's your current experience level?",
        });

        scheduleMsg(setMessages, 1800, {
          sender: "bot",
          sectionLabel: "Experience",
          options: ["Entry-level (0–2 years)", "Mid-level (3–7 years)", "Senior/Manager (8+ years)"],
        });

      } catch {
        setMessages([{
          text: "Error connecting to server. Make sure the backend is running.",
          sender: "bot",
          time: getTime(),
        }]);
      }
    };

    initSession();
  }, []);

  const sendMessage = async (overrideText) => {
    const messageToSend = typeof overrideText === "string" ? overrideText : input;
    if (!messageToSend.trim() || !sessionId) return;

    const userMessage = { text: messageToSend, sender: "user", time: getTime() };
    const botMessage = { text: "", sender: "bot", time: getTime() };

    setMessages((prev) => [...prev, userMessage, botMessage]);
    setInput("");
    setLoading(true);

    let backendMessage = messageToSend;
    if (conversationStep === "experience") {
      backendMessage = `My experience level is: ${messageToSend}. Please acknowledge.`;
    } else if (conversationStep === "department") {
      backendMessage = `My department is: ${messageToSend}. Please acknowledge.`;
    } else if (conversationStep === "goal") {
      backendMessage = `My career goal is: ${messageToSend}. Please recommend some courses based on my experience, department, and goal.`;
    }

    try {
      const res = await fetch("http://127.0.0.1:8000/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: backendMessage }),
      });
      if (!res.ok) throw new Error("Failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        fullText += decoder.decode(value, { stream: true });
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = { text: fullText, sender: "bot", time: getTime() };
          return updated;
        });
      }

      // After bot finishes responding, inject the next guided question based on current step
      if (conversationStep === "experience") {
        scheduleMsg(setMessages, 600, {
          sender: "bot",
          text: "Got it! Which department are you in?",
        });
        scheduleMsg(setMessages, 1400, {
          sender: "bot",
          sectionLabel: "Department",
          options: ["Finance", "Management", "IT"],
        });
        setConversationStep("department");
      } else if (conversationStep === "department") {
        scheduleMsg(setMessages, 600, {
          sender: "bot",
          text: "Almost there! Let's talk about your career goals.",
        });
        scheduleMsg(setMessages, 1400, {
          sender: "bot",
          text: "Are you looking to earn a specific certification, get a promotion, or just upskill?",
        });
        scheduleMsg(setMessages, 2200, {
          sender: "bot",
          sectionLabel: "Career Goal",
          options: [
            "Earn a certification",
            "Get a promotion",
            "Upskill / personal growth",
            "Explore new areas",
          ],
        });
        setConversationStep("goal");
      } else if (conversationStep === "goal") {
        // 'goal' and beyond — open-ended conversation, no more guided prompts
        setConversationStep("free");
      }

    } catch {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          text: "Sorry, something went wrong.",
          sender: "bot",
          time: getTime(),
        };
        return updated;
      });
    }

    setLoading(false);
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const today = new Date().toLocaleDateString([], {
    weekday: "long", month: "short", day: "numeric",
  });

  const handleOpen = () => {
    setOpen((prev) => {
      if (!prev) setTimeout(() => inputRef.current?.focus(), 320);
      return !prev;
    });
  };

  return (
    <div className="chatbot-root">
      <style>{styles}</style>

      {(!isMobile || !open) && (
        <button className="chat-fab" onClick={handleOpen} title="Support Chat">
          <img src={img} alt="chat" />
        </button>
      )}

      <div className={`chat-window ${open ? "open" : "closed"}`}>

        {/* Header */}
        <div className="chat-header">
          <div className="header-left">
            <div className="header-avatar">
              <img src={img} alt="bot" />
            </div>
            <div>
              <div className="header-title">Support Chat</div>
              <div className="header-subtitle">
                <span className="status-dot" />
                Online · Typically replies instantly
              </div>
            </div>
          </div>
          <button className="close-btn" onClick={() => setOpen(false)} title="Close">
            {isMobile ? (
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
                strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="15 18 9 12 15 6" />
              </svg>
            ) : "✕"}
          </button>
        </div>

        {/* Messages */}
        <div className="chat-messages">
          <div className="chat-divider"><span>{today}</span></div>

          {messages.map((msg, i) => (
            <div key={i}>
              {msg.sectionLabel && (
                <div className="section-label">{msg.sectionLabel}</div>
              )}

              <div className={`msg-row ${msg.sender}`}>
                {msg.sender === "bot" && (
                  <div className="bot-icon">
                    <img src={img} alt="bot" />
                  </div>
                )}

                <div className={`bubble ${msg.sender}`}>
                  {msg.options ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "7px" }}>
                      {msg.options.map((opt, idx) => (
                        <button
                          key={idx}
                          onClick={() => sendMessage(opt)}
                          style={{
                            display: "flex", alignItems: "center", gap: "10px",
                            border: "1.5px solid rgba(37,53,142,0.18)",
                            borderRadius: "10px", padding: "8px 12px",
                            background: "#fff", cursor: "pointer",
                            fontSize: "13px", color: "#1a1f3d",
                            textAlign: "left", transition: "background 0.15s",
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = "#eef1fb")}
                          onMouseLeave={(e) => (e.currentTarget.style.background = "#fff")}
                        >
                          <span style={{
                            width: "22px", height: "22px", borderRadius: "50%",
                            background: "#25358E", color: "#fff",
                            fontSize: "11px", fontWeight: "600",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            flexShrink: 0,
                          }}>
                            {idx + 1}
                          </span>
                          {opt}
                        </button>
                      ))}
                      <div style={{ fontSize: "12px", color: "#9aa3bb", marginTop: "4px" }}>
                        Or type your answer below
                      </div>
                    </div>
                  ) : (
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
                  )}
                </div>
              </div>

              {msg.time && (
                <div className={`msg-time msg-row ${msg.sender}`}>{msg.time}</div>
              )}
            </div>
          ))}

          {loading && (
            <div className="typing-indicator">
              <div className="bot-icon"><img src={img} alt="bot" /></div>
              <div className="typing-bubble">
                <div className="dot" /><div className="dot" /><div className="dot" />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="chat-input-area">
          <div className="input-wrapper">
            <input
              ref={inputRef}
              className="chat-input"
              type="text"
              placeholder="Type a message…"
              value={input}
              disabled={!sessionId || loading}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            />
          </div>
          <button
            className="send-btn"
            onClick={sendMessage}
            disabled={!sessionId || loading}
            title="Send"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>

        {/* Footer */}
        <div className="chat-footer">Powered by your support team</div>
      </div>
    </div>
  );
}