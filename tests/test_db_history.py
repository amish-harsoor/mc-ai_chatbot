import sys
import os
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# fix windows encoding for print
sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO)

from src.chatbot.chatbot import create_chat_engine
from llama_index.core.llms import ChatMessage, MessageRole

# simulate the history from the database exactly as it was printed in test_api.py
chat_history = [
    ChatMessage(role=MessageRole.USER, content="My experience level is: Entry-level (0-2 years). Please acknowledge."),
    ChatMessage(role=MessageRole.ASSISTANT, content="Gotit! Your experience level is **Entry‑level (0‑2 years)**. Let me know what you’d like to explore next—whether it’s a specific topic, career goal, or anything else you’re curious about. I’m here to help you find the perfect course!"),
    ChatMessage(role=MessageRole.USER, content="My department is: Finance. Please acknowledge."),
    ChatMessage(role=MessageRole.ASSISTANT, content="Got it! Your departmentis **Finance** and you’re at an **Entry‑level (0‑2 years)** stage.  \n\nWhenever you’re ready, let me know your career goal (e.g., “move into federal financial management,” “become a budget analyst,” etc.), and I’ll suggest the best courses to help you get there. 😊")
]

engine = create_chat_engine(chat_history)

print("\n--- STEP 3: Goal ---")
msg3 = "My career goal is: Get a promotion. Please recommend some courses based on my experience, department, and goal."
print(f"User: {msg3}")
resp3 = engine.stream_chat(msg3)
s3 = ""
for t in resp3.response_gen:
    s3 += t
print(f"Bot: {repr(s3)}")
