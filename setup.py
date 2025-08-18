import asyncio
from dotenv import load_dotenv
import os
from telegram.ext import Application


# Load environment variables
load_dotenv()
URL = os.environ.get("URL")
TOKEN = os.environ.get("TELEGRAM_TOKEN")


# Create the application
application = Application.builder().token(TOKEN).build()


async def main():
    """Set up the Telegram bot webhook."""
    await application.bot.set_webhook(url=f"{URL}/telegram")


if __name__ == "__main__":
    asyncio.run(main())
