
import os
import json
import time
import requests
import feedparser
from urllib.parse import quote

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

SEEN_FILE = "seen.json"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

FEEDS = [
    "https://www.reddit.com/r/FUTMobile/new/.rss",
    "https://www.reddit.com/r/EASportsFCMobile/new/.rss",
    "https://news.google.com/rss/search?q=FC+Mobile+glitch+OR+exploit+OR+free+gems",
]

KEYWORDS = [
    "glitch", "exploit", "bug", "free gems", "free coins",
    "free fc points", "unlimited", "exchange", "market",
    "pack glitch", "event glitch", "bucks"
]

def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
        timeout=20,
    )
    response.raise_for_status()

def collect_items():
    items = []
    for feed_url in FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:30]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")
                text = f"{title} {summary}".lower()

                if any(word in text for word in KEYWORDS):
                    items.append({
                        "id": entry.get("id", link or title),
                        "title": title,
                        "summary": summary[:1200],
                        "link": link,
                    })
        except Exception as exc:
            print(f"Feed-Fehler: {exc}")
    return items

def classify(items):
    if not items:
        return []

    prompt = (
        "Du bist ein FC Mobile Recherche-Assistent. "
        "Bewerte die folgenden Fundmeldungen. Berücksichtige nur "
        "mögliche kostenlose Ressourcen, Glitches, Exploits, Bugs, "
        "Events, Exchanges, Packs und Market-Fehler. "
        "Erfinde keine Bestätigungen. Markiere unbestätigte Behauptungen "
        "als unverified. Antworte ausschließlich als JSON-Array. "
        "Jedes Element enthält: id, relevant (true/false), "
        "reason, status. Status ist unverified, multiple_reports, "
        "claimed_working, patched oder unknown.\n\n"
        + json.dumps(items, ensure_ascii=False)
    )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    response = requests.post(
        url,
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()
    answer = result["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(answer)

def main():
    seen = load_seen()
    items = collect_items()

    fresh = [item for item in items if item["id"] not in seen]
    print(f"Neue Kandidaten: {len(fresh)}")

    if not fresh:
        return

    try:
        results = classify(fresh)
    except Exception as exc:
        print(f"Gemini-Fehler: {exc}")
        return

    by_id = {item["id"]: item for item in fresh}

    for result in results:
        item = by_id.get(result.get("id"))
        if not item:
            continue

        if result.get("relevant"):
            message = (
                "⚽ FC MOBILE RADAR\n\n"
                f"Fund: {item['title']}\n"
                f"Status: {result.get('status', 'unknown')}\n"
                f"Bewertung: {result.get('reason', 'Keine Details')}\n\n"
                f"Quelle: {item['link']}"
            )
            try:
                send_telegram(message)
            except Exception as exc:
                print(f"Telegram-Fehler: {exc}")

    seen.update(item["id"] for item in fresh)
    save_seen(seen)

if __name__ == "__main__":
    main()
