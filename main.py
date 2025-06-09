from flask import Flask, request
import requests
import os

app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.route('/')
def home():
    return "Bot is running!"

@app.route(f'/webhook/{BOT_TOKEN}', methods=['POST'])
def webhook():
    data = request.get_json()
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '')
        if text.startswith("http"):
            reply = "✅ Link received! Working on it..."
        else:
            reply = "📎 Please send me a link to an article."
        requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": reply})
    return "ok", 200

@app.before_first_request
def set_webhook():
    url = f"{APP_URL}/webhook/{BOT_TOKEN}"
    requests.get(f"{TELEGRAM_API}/setWebhook?url={url}")
