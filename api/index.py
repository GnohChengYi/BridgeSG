from flask import Flask, request, Response
from http import HTTPStatus
from flask.cli import load_dotenv
from telegram.ext import Application
import os
import sys
import logging
import traceback

# Add the api directory to the Python module search path so local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dummy_bot import process_update_sync

app = Flask(__name__)

# Enable logging early
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Load environment variables and validate minimal config
load_dotenv()
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("TELEGRAM_TOKEN not set; exiting with code 1")
    sys.exit(1)

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    """Entrypoint for Telegram webhooks.

    For serverless deployments we process updates synchronously using
    helpers in `dummy_bot` so the function stays short and deterministic.
    """
    try:
        logger.info("Raw request data: %s", request.data)
        logger.info("Request headers: %s", request.headers)
        update_json = request.get_json(force=True)
        logger.info("Received update: %s", update_json)

        status, body = process_update_sync(update_json)
        return Response(body or "", status=status)
    except Exception as e:
        logger.error("Error in telegram_webhook: %s", e)
        logger.error("Traceback: %s", traceback.format_exc())
        return Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)


@app.route('/')
def home():
    return 'Hello, World!'


@app.route('/about')
def about():
    return 'About'


if __name__ == '__main__':
    app.run()
