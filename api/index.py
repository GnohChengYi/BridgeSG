from flask import Flask, request, Response
from http import HTTPStatus
from telegram import Update
from telegram.ext import Application
import os
from dummy_bot import dummy_application

app = Flask(__name__)

# Load environment variables
TOKEN = os.environ.get("TELEGRAM_TOKEN")
application = Application.builder().token(TOKEN).build()

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    """Handle incoming Telegram webhook requests."""
    update = Update.de_json(request.get_json(force=True), dummy_application.bot)
    dummy_application.update_queue.put(update)
    return Response(status=HTTPStatus.OK)

@app.route('/')
def home():
    return 'Hello, World!'

@app.route('/about')
def about():
    return 'About'

if __name__ == '__main__':
    app.run()
