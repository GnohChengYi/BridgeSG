from flask import Flask, request, Response
from http import HTTPStatus
from flask.cli import load_dotenv
from telegram import Update
from telegram.ext import Application
import os
import sys
import logging
import asyncio
import traceback

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

# Flag to track if the application has been initialized
application_initialized = False

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    """Handle incoming Telegram webhook requests directly."""
    global application_initialized

    try:
        # Initialize the application if not already done
        if not application_initialized:
            logger.info("Initializing the application...")
            asyncio.run(dummy_application.initialize())
            application_initialized = True

        # Log raw request data
        logger.info("Raw request data: %s", request.data)
        logger.info("Request headers: %s", request.headers)

        update_json = request.get_json(force=True)
        logger.info("Received update: %s", update_json)
        update = Update.de_json(update_json, dummy_application.bot)

        # Process the update directly
        asyncio.run(dummy_application.process_update(update))

        logger.info("Update successfully processed.")
    except Exception as e:
        logger.error("Error processing update: %s", e)
        logger.error("Traceback: %s", traceback.format_exc())
    return Response(status=HTTPStatus.OK)

@app.route('/')
def home():
    return 'Hello, World!'

@app.route('/about')
def about():
    return 'About'

if __name__ == '__main__':
    app.run()
