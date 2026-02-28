# webserver.py
from flask import Flask
import os
import threading

app = Flask("")

@app.route("/")
def home():
    return "🤖 Bot is alive!"

def run():
    port = int(os.environ.get("PORT", 8080))  # Render sets this automatically
    app.run(host="0.0.0.0", port=port)

def start():
    # Run the Flask server in a separate thread so your bot can run normally
    thread = threading.Thread(target=run)
    thread.start()