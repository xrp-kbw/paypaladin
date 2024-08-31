from flask import Flask, request
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import os
from dotenv import load_dotenv
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet, generate_faucet_wallet
import xrpl
from pymongo import MongoClient, errors

# Load environment variables from .env file
load_dotenv()
# Connect to MongoDB
def create_mongo_connection():
    try:
        print(os.getenv('MONGO_URI'))
        client = MongoClient(os.getenv('MONGO_URI'))  # Replace with your MongoDB URI
        db = client['user_wallets_db']  # The name of your database
        # Attempt to make a connection to the server
        client.admin.command('ping')
        print("Connected to MongoDB")
        return db['user_wallets']  # The name of your collection
    except errors.ConnectionFailure as e:
        print(f"Could not connect to MongoDB: {e}")
        return None

def save_user_wallet(user_id, username, private_key):
    try:
        user_wallets_collection.update_one(
            {"user_id": user_id},
            {"$set": {"username": username, "private_key": private_key}},
            upsert=True
        )
    except Exception as e:
        print(f"Error while saving user wallet: {e}")

def get_user_wallet(user_id):
    try:
        return user_wallets_collection.find_one({"user_id": user_id})
    except Exception as e:
        print(f"Error while retrieving user wallet: {e}")
        return None

# Establish connection to the collection
user_wallets_collection = create_mongo_connection()

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

# In memory wallet store 
wallet = Wallet.from_secret("sEdS6aGnXgXJ9kZmVQHpzTwqjPhXL1q")
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

def send_xrp(seed, amount, destination):
    sending_wallet = Wallet.from_seed(seed)
    payment = xrpl.models.transactions.Payment(
        account=sending_wallet.address,
        amount=xrpl.utils.xrp_to_drops(int(amount)),
        destination=destination,
    )
    try:	
        response = xrpl.transaction.submit_and_wait(payment, client, sending_wallet)	
    except xrpl.transaction.XRPLReliableSubmissionException as e:	
        response = f"Submit failed: {e}"

    return response

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username

    # Check if the user already has a wallet in the database
    user_data = get_user_wallet(user_id)
    if user_data:
        test_wallet = Wallet.from_seed(user_data['private_key'])  # Load wallet using the stored private key
    else:
        # Use ThreadPoolExecutor to run the sync function in a separate thread
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            test_wallet = await loop.run_in_executor(pool, generate_faucet_wallet_sync, client, True)
        # Save the new wallet to the database
        save_user_wallet(user_id, username, test_wallet.seed)

    # Extract the wallet address
    test_account = test_wallet.address

    # Send the wallet address to the user
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Your wallet address is: {test_account}")

async def send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Retrieve the user's wallet from the database
    user_data = get_user_wallet(user_id)
    if not user_data:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No wallet found for your user ID.")
        return

    test_wallet = Wallet.from_seed(user_data['private_key'])  # Load wallet using the stored private key

    # Use ThreadPoolExecutor to run the sync function in a separate thread
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        response = await loop.run_in_executor(
            pool, send_xrp, test_wallet.seed, 1, "raKQpxX2HC9RrVTX2gpyfun2f4QWnk5kez"
        )

    # Check if the response is an error message or a successful transaction result
    if isinstance(response, str) and response.startswith("Submit failed:"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="XRP sent successfully!")
        
        # Send a message to another user as well
        other_user_id = 123456789  # Replace with the actual Telegram user ID of the other user
        await context.bot.send_message(chat_id=other_user_id, text="XRP sent successfully to another account!")

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
