import { useState, useRef, useEffect } from "react";

export default function FloatingChatbot() {
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState([
        { text: "Hi 👋 How can I help you?", sender: "bot" },
    ]);
    const [input, setInput] = useState("");
    const chatEndRef = useRef(null);

    const sendMessage = () => {
        if (!input.trim()) return;

        const newMessage = { text: input, sender: "user" };
        setMessages((prev) => [...prev, newMessage]);

        setTimeout(() => {
            setMessages((prev) => [
                ...prev,
                { text: "Thanks for your message!", sender: "bot" },
            ]);
        }, 600);

        setInput("");
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
                💬
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
                <div className="flex-1 p-4 space-y-3 overflow-y-auto bg-gray-50">
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
                                    borderBottomRightRadius:
                                        msg.sender === "user"
                                            ? "0.25rem"
                                            : undefined,
                                    borderBottomLeftRadius:
                                        msg.sender === "bot"
                                            ? "0.25rem"
                                            : undefined,
                                }}
                            >
                                {msg.text}
                            </div>
                        </div>
                    ))}
                    <div ref={chatEndRef} />
                </div>

                {/* Input */}
                <div className="p-3 border-t flex gap-2">
                    <input
                        type="text"
                        placeholder="Type message..."
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                        className="flex-1 px-3 py-2 text-sm border rounded-full outline-none"
                        style={{ borderColor: "#25358E" }}
                    />
                    <button
                        onClick={sendMessage}
                        className="text-white px-4 py-2 text-sm rounded-full"
                        style={{ backgroundColor: "#90182A" }}
                    >
                        Send
                    </button>
                </div>
            </div>
        </div>
    );
}