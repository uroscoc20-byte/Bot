# webserver.py
from flask import Flask
import os
import threading

app = Flask("")

@app.route("/")
def home():
    return "Bot is running!", 200

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def start():
    threading.Thread(target=run).start()
