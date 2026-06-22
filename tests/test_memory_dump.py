import sys
import os
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# fix windows encoding for print
sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.ERROR)

from src.chatbot.chatbot import create_chat_engine

chat_history = []
engine = create_chat_engine(chat_history)

msg1 = "My experience level is: Entry-level (0-2 years). Please acknowledge."
resp1 = engine.chat(msg1)

msg2 = "My department is: Finance. Please acknowledge."
resp2 = engine.chat(msg2)

print("\n--- IN-MEMORY HISTORY ---")
for m in engine.memory.get():
    print(f"{m.role}: {repr(m.content)}")
