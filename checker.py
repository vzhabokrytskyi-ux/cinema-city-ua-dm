import os
import re
import json
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CINEMAS = {
    "Bonarka": 1090,
    "Kazimierz": 1076,
    "Zakopianka": 1064,
}

DAYS_AHEAD = 7
STATE_FILE = "state.json"

UA_KEYWORDS = [
    "ukraiński dubbing",
    "ukrainski dubbing",
    "film z dubbingiem:ua",
    "film z dubbingiem: ua",
    "dubbingiem:ua",
    "dubbingiem: ua",
    "napisy ukraińskie",
    "napisy ukrainskie",
    "ukraińskie napisy",
    "ukrainskie napisy",
    "ua dubbing",
    "ua subtitles",
    "ua napisy",
]

BASE_URL_TEMPLATE = (
    "https://www.cinema-city.pl/kina/{cinema_slug}/{cinema_id}"
    "#/buy-tickets-by-cinema?in-cinema={cinema_id}&at={date}"
    "&filtered=dubbed&view-mode=list"
)

CINEMA_SLUGS = {
    "Bonarka": "bonarka",
    "Kazimierz": "kazimierz",
    "Zakopianka": "zakopianka",
}


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    text = re.sub(r"(?is)<.*?>", " ", html)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def build_urls():
    today = datetime.now(ZoneInfo("Europe/Warsaw")).date()
    urls = []

    for cinema_name, cinema_id in CINEMAS.items():
        slug = CINEMA_SLUGS[cinema_name]
        for i in range(DAYS_AHEAD):
            d = today + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            url = BASE_URL_TEMPLATE.format(
                cinema_slug=slug,
                cinema_id=cinema_id,
                date=ds,
            )
            urls.append(
                {
                    "cinema_name": cinema_name,
                    "cinema_id": cinema_id,
                    "date": ds,
                    "url": url,
                }
            )
    return urls


def extract_contexts(text: str, keywords: list[str]) -> list[str]:
    contexts = []
    for kw in keywords:
        for m in re.finditer(re.escape(kw), text):
            start = max(0, m.start() - 120)
            end = min(len(text), m.end() + 120)
            snippet = text[start:end].strip()
            snippet = re.sub(r"\s+", " ", snippet)
            contexts.append(snippet)
    return contexts[:5]


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"seen": []}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"seen": []}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def send_telegram(message: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": False,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def main():
    state = load_state()
    seen = set(state.get("seen", []))

    findings = []

    for item in build_urls():
        try:
            text = fetch_text(item["url"])
        except Exception:
            continue

        hits = [kw for kw in UA_KEYWORDS if kw in text]
        if not hits:
            continue

        contexts = extract_contexts(text, hits)
        finding_key = sha(
            f'{item["cinema_name"]}|{item["date"]}|{"|".join(sorted(hits))}|{"|".join(contexts)}'
        )
        if finding_key in seen:
            continue

        findings.append(
            {
                "key": finding_key,
                "cinema": item["cinema_name"],
                "date": item["date"],
                "url": item["url"],
                "hits": hits,
                "contexts": contexts,
            }
        )

    if not findings:
        return

    now = datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M")

    chunks = []
    for f in findings:
        part = [
            f'🎬 {f["cinema"]}',
            f'📅 {f["date"]}',
            f'🏷 {", ".join(sorted(set(f["hits"])))}',
            f'🔗 {f["url"]}',
        ]
        if f["contexts"]:
            part.append(f'ℹ️ {f["contexts"][0][:250]}')
        chunks.append("\n".join(part))

    message = "🇺🇦 Cinema City Kraków — знайдено українські сеанси\n"
    message += f"⏱ {now}\n\n"
    message += "\n\n--------------------\n\n".join(chunks)

    # Telegram має ліміт, ріжемо якщо треба
    if len(message) > 3900:
        message = message[:3900] + "\n\n…обрізано"

    send_telegram(message)

    for f in findings:
        seen.add(f["key"])

    state["seen"] = sorted(seen)
    save_state(state)


if __name__ == "__main__":
    main()
