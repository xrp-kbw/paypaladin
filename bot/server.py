from flask import Flask, request
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import os
from dotenv import load_dotenv
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet, generate_faucet_wallet

JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/"
client = JsonRpcClient(JSON_RPC_URL)

# Load environment variables from .env file
load_dotenv()

# Get the token from environment variables
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Initialize Flask app
app = Flask(__name__)

# Initialize the bot with your token
bot = Bot(token=TOKEN)

# Initialize the application
application = Application.builder().token(TOKEN).build()

# In memory wallet store 
# wallet = Wallet.from_secret("sEdS6aGnXgXJ9kZmVQHpzTwqjPhXL1q")
user_wallets = {
    # <telegram_id>: wallet
}

async def initialize_and_run():
    # Initialize the application
    await bot.initialize()
    await application.initialize()

    # Run the Flask server
    app.run(port=8443)
# Define a command handler for the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I'm your bot.")

# Define a message handler for text messages
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)

def generate_faucet_wallet_sync(client, debug):
    # Call the synchronous function which internally uses asyncio.run()
    return generate_faucet_wallet(client, debug=debug)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Check if the user already has a wallet
    if user_id in user_wallets:
        test_wallet = user_wallets[user_id]
    else:
        # Use ThreadPoolExecutor to run the sync function in a separate thread
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            test_wallet = await loop.run_in_executor(pool, generate_faucet_wallet_sync, client, True)
        # Store the generated wallet in the dictionary
        user_wallets[user_id] = test_wallet

    # Extract the wallet address
    test_account = test_wallet.address

    # Send the wallet address to the user
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Your wallet address is: {test_account}")

# Add handlers to the application
application.add_handler(CommandHandler('start', start))
application.add_handler(CommandHandler('status', status))
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
