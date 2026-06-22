// UNUSED / DEAD CODE (previously referenced in App.jsx but commented out).
// Safe to delete in future cleanup. Not part of active chatbot UI.
import { useState } from "react";

export default function PremiumChatUI() {
    const [input, setInput] = useState("");

    return (
        <div className="min-h-screen bg-[#f3f4f6] flex items-center justify-center px-6">
            <div className="w-full max-w-5xl text-center">

                {/* Floating Orb */}
                <div className="flex justify-center mb-6">
                    <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-purple-500 via-pink-500 to-blue-500 blur-xl opacity-40 absolute"></div>
                    <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-purple-500 via-pink-500 to-blue-500 relative"></div>
                </div>

                {/* Heading */}
                <h1 className="text-4xl md:text-5xl font-semibold text-gray-800">
                    Hi there, <span className="italic text-purple-600">Chethan</span>
                </h1>

                <p className="mt-3 text-xl md:text-2xl bg-gradient-to-r from-purple-600 via-pink-500 to-red-500 bg-clip-text text-transparent font-medium">
                    Ready to power up your ideas?
                </p>

                {/* Feature Cards */}
                <div className="grid md:grid-cols-3 gap-6 mt-12">
                    {[
                        {
                            title: "Create Cinematic 4K Videos",
                            desc: "AI-generated studio quality videos."
                        },
                        {
                            title: "Make Music, Voiceovers & FX",
                            desc: "Compose with AI in your style."
                        },
                        {
                            title: "Ask AI Assistant",
                            desc: "Get insights, automate work."
                        }
                    ].map((card, index) => (
                        <div
                            key={index}
                            className="bg-white/70 backdrop-blur-md p-6 rounded-2xl shadow-sm hover:shadow-md transition"
                        >
                            <h3 className="font-semibold text-gray-800 mb-2">
                                {card.title}
                            </h3>
                            <p className="text-sm text-gray-500">{card.desc}</p>
                        </div>
                    ))}
                </div>

                {/* Input */}
                <div className="mt-16 flex justify-center">
                    <div className="w-full max-w-2xl bg-white rounded-full shadow-md flex items-center px-6 py-3">
                        <input
                            type="text"
                            placeholder="Ask anything..."
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            className="flex-1 outline-none text-gray-700 bg-transparent"
                        />
                        <button className="bg-gradient-to-r from-purple-600 to-pink-500 text-white px-5 py-2 rounded-full text-sm hover:opacity-90 transition">
                            Send
                        </button>
                    </div>
                </div>

            </div>
        </div>
    );
}