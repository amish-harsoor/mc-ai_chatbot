import { useState, useRef, useEffect } from "react";
import img from "./assets/img.png"
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";


export default function FloatingChatbot() {
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [sessionId, setSessionId] = useState(null);
    const [loading, setLoading] = useState(false);
    const chatEndRef = useRef(null);

    // ✅ Initialize session when component mounts
    useEffect(() => {
        const initSession = async () => {
            try {
                const res = await fetch("http://10.169.21.26:8000/session/start", {
                    method: "POST",
                });

                const data = await res.json();
                setSessionId(data.session_id);

                setMessages([
                    {
                        text: "Welcome! How can I help you today?",
                        sender: "bot",
                    },
                ]);
            } catch (error) {
                setMessages([
                    {
                        text: "Error connecting to server. Make sure backend is running.",
                        sender: "bot",
                    },
                ]);
            }
        };

        initSession();
    }, []);

    // ✅ Send Message with Streaming Response
    const sendMessage = async () => {
        if (!input.trim() || !sessionId) return;

        const messageToSend = input; // store before clearing
        const userMessage = { text: messageToSend, sender: "user" };
        const botMessage = { text: "", sender: "bot" };

        setMessages((prev) => [...prev, userMessage, botMessage]);
        setInput("");
        setLoading(true);

        try {
            const res = await fetch("http://10.169.21.26:8000/chat/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: sessionId,
                    message: messageToSend,
                }),
            });

            if (!res.ok) throw new Error("Failed to connect");

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let fullText = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                fullText += chunk;

                setMessages((prev) => {
                    const updated = [...prev];
                    updated[updated.length - 1] = {
                        text: fullText,
                        sender: "bot",
                    };
                    return updated;
                });
            }
        } catch (error) {
            setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                    text: "Sorry, something went wrong.",
                    sender: "bot",
                };
                return updated;
            });
        }

        setLoading(false);
    };

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    return (
        <div
            style={{
                fontFamily: "Source Sans 3, Helvetica, Arial, sans-serif",
            }}
        >
            {/* Floating Button */}
            <button
                onClick={() => setOpen(!open)}
                className="fixed bottom-6 right-6 w-14 h-14 text-white rounded-full shadow-lg flex items-center justify-center hover:scale-105 transition"
                style={{ backgroundColor: "#90182A" }}
            >
                <img src={img} alt="chat icon" className="w-8 h-8" />
            </button>

            {/* Chat Window */}
            <div
                className={`fixed bottom-24 right-6 w-80 bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden transition-all duration-300 ${
                    open
                        ? "opacity-100 scale-100"
                        : "opacity-0 scale-95 pointer-events-none"
                }`}
            >
                {/* Header */}
                <div
                    className="text-white p-4 flex justify-between items-center"
                    style={{ backgroundColor: "#25358E" }}
                >
                    <span className="font-medium">Support Chat</span>
                    <button onClick={() => setOpen(false)}>✕</button>
                </div>

                {/* Messages */}
                <div className="flex-1 p-4 space-y-3 overflow-y-auto bg-gray-50 max-h-[350px]">
                    {messages.map((msg, index) => (
                        <div
                            key={index}
                            className={`flex ${
                                msg.sender === "user"
                                    ? "justify-end"
                                    : "justify-start"
                            }`}
                        >
                            <div
                                className="px-3 py-2 text-sm rounded-2xl max-w-[70%]"
                                style={{
                                    backgroundColor:
                                        msg.sender === "user"
                                            ? "#90182A"
                                            : "#25358E",
                                    color: "#ffffff",
                                }}
                            >
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {msg.text}
                                </ReactMarkdown>
                            </div>
                        </div>
                    ))}

                    {loading && (
                        <div className="text-xs text-gray-500">
                            Bot is thinking...
                        </div>
                    )}

                    <div ref={chatEndRef} />
                </div>

                {/* Input */}
                <div className="p-3 border-t flex gap-2">
                    <input
                        type="text"
                        placeholder="Type message..."
                        value={input}
                        disabled={!sessionId || loading}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                        className="flex-1 px-3 py-2 text-sm border rounded-full outline-none"
                        style={{ borderColor: "#25358E" }}
                    />
                    <button
                        onClick={sendMessage}
                        disabled={!sessionId || loading}
                        className="text-white px-4 py-2 text-sm rounded-full disabled:opacity-50"
                        style={{ backgroundColor: "#90182A" }}
                    >
                        Send
                    </button>
                </div>
            </div>
        </div>
    );
}