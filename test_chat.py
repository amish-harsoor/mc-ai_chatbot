import sys
import os
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# fix windows encoding for print
sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO)

from src.chatbot.chatbot import create_chat_engine

chat_history = []
engine = create_chat_engine(chat_history)

print("\n--- STEP 1: Experience ---")
msg1 = "My experience level is: Entry-level (0-2 years). Please acknowledge."
print(f"User: {msg1}")
resp1 = engine.stream_chat(msg1)
s1 = ""
for t in resp1.response_gen:
    s1 += t
print(f"Bot: {s1}")

print("\n--- STEP 2: Department ---")
msg2 = "My department is: Finance. Please acknowledge."
print(f"User: {msg2}")
resp2 = engine.stream_chat(msg2)
s2 = ""
for t in resp2.response_gen:
    s2 += t
print(f"Bot: {s2}")

print("\n--- STEP 3: Goal ---")
msg3 = "My career goal is: Get a promotion. Please recommend some courses based on my experience, department, and goal."
print(f"User: {msg3}")
resp3 = engine.stream_chat(msg3)
s3 = ""
for t in resp3.response_gen:
    s3 += t
print(f"Bot: {repr(s3)}")
