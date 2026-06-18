import requests
import json
import sys

# fix windows encoding for print
sys.stdout.reconfigure(encoding='utf-8')

base_url = "http://127.0.0.1:8000"

print("1. Starting session...")
res = requests.post(f"{base_url}/session/start")
session_id = res.json()["session_id"]
print(f"Session ID: {session_id}")

print("\n2. Sending Experience...")
res = requests.post(
    f"{base_url}/chat/stream",
    json={"session_id": session_id, "message": "My experience level is: Entry-level (0-2 years). Please acknowledge."},
    stream=True
)
resp1 = ""
for chunk in res.iter_content(chunk_size=None, decode_unicode=True):
    if chunk:
        resp1 += chunk
print(f"Bot: {resp1}")

print("\n3. Sending Department...")
res = requests.post(
    f"{base_url}/chat/stream",
    json={"session_id": session_id, "message": "My department is: Finance. Please acknowledge."},
    stream=True
)
resp2 = ""
for chunk in res.iter_content(chunk_size=None, decode_unicode=True):
    if chunk:
        resp2 += chunk
print(f"Bot: {resp2}")

print("\n4. Sending Goal...")
res = requests.post(
    f"{base_url}/chat/stream",
    json={"session_id": session_id, "message": "My career goal is: Get a promotion. Please recommend some courses based on my experience, department, and goal."},
    stream=True
)
resp3 = ""
for chunk in res.iter_content(chunk_size=None, decode_unicode=True):
    if chunk:
        resp3 += chunk
print(f"Bot: {resp3}")

print("\n5. Fetching History...")
history = requests.get(f"{base_url}/session/{session_id}/history").json()
print(json.dumps(history, indent=2))
