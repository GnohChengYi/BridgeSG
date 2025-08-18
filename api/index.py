from flask import Flask, request, Response
from http import HTTPStatus
from flask.cli import load_dotenv
from telegram import Update
from telegram.ext import Application
import os
import sys
import logging

# Add the api directory to the Python module search path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dummy_bot import dummy_application

app = Flask(__name__)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.environ.get("TELEGRAM_TOKEN")
application = Application.builder().token(TOKEN).build()

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    """Handle incoming Telegram webhook requests."""
    try:
        update_json = request.get_json(force=True)
        logger.info("Received update: %s", update_json)
        update = Update.de_json(update_json, dummy_application.bot)
        dummy_application.update_queue.put(update)
        logger.info("Update successfully added to the queue.")
    except Exception as e:
        logger.error("Error processing update: %s", e)
    return Response(status=HTTPStatus.OK)

@app.route('/')
def home():
    return 'Hello, World!'

@app.route('/about')
def about():
    return 'About'

if __name__ == '__main__':
    app.run()
