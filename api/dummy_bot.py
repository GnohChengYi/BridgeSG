from telegram import Update
from telegram.ext import Application, CommandHandler
import logging
import os
from flask.cli import load_dotenv
import redis
from datetime import datetime

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Load Redis URL from environment variables
REDIS_URL = os.environ.get("REDIS_URL")
redis_client = redis.StrictRedis.from_url(REDIS_URL)

# Define a simple start command for the dummy bot
async def start(update: Update, context):
    logger.info("Processing /start command from user: %s", update.effective_user)

    # Store the current time in Redis
    current_time = datetime.now().isoformat()
    redis_client.set("last_start_time", current_time)

    # Retrieve the stored time from Redis
    retrieved_time = redis_client.get("last_start_time").decode("utf-8")

    # Reply to the user with the retrieved time
    await update.message.reply_text(f"The last start time was: {retrieved_time}")

# Create the dummy bot application
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))

# Expose the application for linking
dummy_application = application
