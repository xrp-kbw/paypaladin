from flask import Flask, request
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import os
from dotenv import load_dotenv
from xrpl.clients import JsonRpcClient
from bot import create_mongo_connection, get_user_wallet, save_user_wallet, generate_faucet_wallet_sync, send_xrp, start, echo, status, send

JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/"
client = JsonRpcClient(JSON_RPC_URL)

# Get the token from environment variables
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Initialize Flask app
app = Flask(__name__)

# Initialize the bot with your token
bot = Bot(token=TOKEN)

# Initialize the application
application = Application.builder().token(TOKEN).build()

async def initialize_and_run():
    # Initialize the application
    await bot.initialize()
    await application.initialize()

    # Run the Flask server
    app.run(port=8443)

# Add handlers to the application
application.add_handler(CommandHandler('start', start))
application.add_handler(CommandHandler('status', status))
application.add_handler(CommandHandler('send', send))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

@app.route('/webhook', methods=['POST'])
async def webhook():
    # Process the incoming update
    update = Update.de_json(request.get_json(force=True), bot)
    await application.process_update(update)
    return "ok", 200

if __name__ == '__main__':
    # Run the Flask server
    asyncio.run(initialize_and_run())
