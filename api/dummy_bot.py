from telegram import Update
from telegram.ext import Application, CommandHandler
import logging

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define a simple start command for the dummy bot
async def start(update: Update, context):
    logger.info("Processing /start command from user: %s", update.effective_user)
    await update.message.reply_text("This is a dummy bot for sanity checking!")

# Create the dummy bot application
application = Application.builder().token("TELEGRAM_TOKEN").build()
application.add_handler(CommandHandler("start", start))

# Expose the application for linking
dummy_application = application
