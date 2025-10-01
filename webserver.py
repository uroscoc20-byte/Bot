# webserver.py
from flask import Flask
import threading

app = Flask("")

@app.route("/")
def home():
    return "Bot is running!", 200

def run():
    app.run(host="0.0.0.0", port=8080)

def start():
    threading.Thread(target=run).start()
