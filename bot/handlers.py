from telegram import Update
from telegram.ext import ContextTypes
from .database import save_user_wallet, get_user_wallet
from .wallet import generate_faucet_wallet_sync, send_xrp
from xrpl.wallet import Wallet  # Import Wallet class
from concurrent.futures import ThreadPoolExecutor
import asyncio

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I'm your bot.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)

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
