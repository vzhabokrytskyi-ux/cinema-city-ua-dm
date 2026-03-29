import os
import re
import json
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

CINEMA_PAGES = [
    "https://www.cinema-city.pl/kina/bonarka/1090",
    "https://www.cinema-city.pl/kina/kazimierz/1076",
    "https://www.cinema-city.pl/kina/zakopianka/1064",
]

UA_KEYWORDS = [
    "ukrai",
    "dubbing ukrai",
    "napisy ukrai",
    "wersja ukrai",
    "ua dubb",
    "ua nap",
]

STATE_FILE = "state.json"

def fetch_text(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    text = re.sub(r"(?is)<.*?>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def find_hits(text):
    low = text.lower()
    return [kw for kw in UA_KEYWORDS if kw in low]

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"seen": []}
    with open(STATE_FILE) as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()

def send(msg):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": msg
    }).encode()

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    urllib.request.urlopen(url, data=data)

def main():
    state = load_state()
    seen = set(state.get("seen", []))

    lines = []
    found = False

    for url in CINEMA_PAGES:
        try:
            text = fetch_text(url)
        except:
            continue

        hits = find_hits(text)
        if hits:
            found = True
            lines.append(f"{url} ({', '.join(hits)})")

    if not found:
        return

    payload = "\n".join(lines)
    h = sha(payload)

    if h in seen:
        return

    seen.add(h)
    state["seen"] = list(seen)
    save_state(state)

    now = datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M")

    send(f"🇺🇦 Є українські покази!\n{now}\n\n{payload}")

if __name__ == "__main__":
    main()
