from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from xrpl.wallet import Wallet
import asyncio
import os
from dotenv import load_dotenv
from xrpl.clients import JsonRpcClient
from bot import create_mongo_connection, get_user_wallet, get_user_wallet_by_username, save_user_wallet, generate_faucet_wallet_sync, send_xrp, start, echo, status, send
from assistant.audio_processing import convert_audio_to_text
from assistant.assistant_manager import initialize_client, add_message_to_thread
from telegram.error import NetworkError, TelegramError
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
from openai import OpenAI
import json
import time
from concurrent.futures import ThreadPoolExecutor

# Load environment variables from .env file
load_dotenv()

# Configuration
JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/"
client = JsonRpcClient(JSON_RPC_URL)
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize the bot with your token
bot = Bot(token=TOKEN)

# Create a new event loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Initialize the application
application = Application.builder().token(TOKEN).build()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def download_voice_file(context, voice_file, voice_file_path):
    try:
        await voice_file.download_to_drive(voice_file_path)
    except asyncio.CancelledError:
        # If the task was cancelled, we need to re-raise this specific error
        raise
    except Exception as e:
        print(f"Error downloading voice file: {e}")
        raise

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle both voice and text messages with improved error handling."""
    try:

        transcribed_text = await process_message(update, context)
        if transcribed_text is None:
            return
    
        client, assistant_id, _ = initialize_client()
        thread_file = "thread_id.json"

        if os.path.exists(thread_file):
            with open(thread_file, "r") as file:
                user_data = json.load(file)
            
            if str(update.effective_user.id) in user_data:
                thread_id = user_data[str(update.effective_user.id)]["thread_id"]
                thread = client.beta.threads.retrieve(thread_id=thread_id)
            else:
                thread = client.beta.threads.create()
                user_data[str(update.effective_user.id)] = {
                    "thread_id": thread.id,
                    "username": update.effective_user.username
                }
        else:
            thread = client.beta.threads.create()
            user_data = {
                str(update.effective_user.id): {
                    "thread_id": thread.id,
                    "username": update.effective_user.username
                }
            }

        with open(thread_file, "w") as file:
            json.dump(user_data, file)     
            
        # Add user message to thread
        add_message_to_thread(client, thread, transcribed_text)
    
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id
        )
         # Poll for the response (this could be improved with async calls)
        while True:
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            print(run.status)
            if run.status == "completed":
                break
            time.sleep(1)

        messages = client.beta.threads.messages.list(thread_id=thread.id)
        assistant_message = messages.dict()["data"][0]["content"][0]["text"]["value"]
        
        if assistant_message:
            if context.user_data.get('awaiting_confirmation') and context.user_data.get('payment_info'):
                # TODO: Send transaction with payment info
                payment_info = context.user_data.get('payment_info')
                # Check if is send or request payment
                if payment_info['action'] == 'send':
                    # TODO: Send transaction with payment info
                    # if recipient is not set up reply else send the funds
                    user_data = get_user_wallet(update.effective_user.id)
                    recipient_data = get_user_wallet_by_username(payment_info["recipient"])
                    
                    if recipient_data:
                        recipient_wallet = Wallet.from_seed(recipient_data['private_key']) 
                        user_wallet = Wallet.from_seed(user_data['private_key']) 
                        loop = asyncio.get_event_loop()
                        with ThreadPoolExecutor() as pool:
                            response = await loop.run_in_executor(
                                pool, send_xrp, user_wallet.seed, payment_info["amount"],recipient_wallet.address
                            )

                        # Check if the response is an error message or a successful transaction result
                        if isinstance(response, str) and response.startswith("Submit failed:"):
                            await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
                        else:
                            
                            await context.bot.send_message(chat_id=update.effective_chat.id, text="XRP sent successfully!")
                            # Send a message to another user as well
                            await context.bot.send_message(chat_id=recipient_data['user_id'], text="XRP received successfully!")                        
                    else:        
                        await context.bot.send_message(chat_id=update.effective_chat.id, text="Recipient is not registered yet")
                    pass
                elif payment_info['action'] == 'request':
                    user_data = get_user_wallet(update.effective_user.id)
                    recipient_data = get_user_wallet_by_username(payment_info["recipient"])
                    if recipient_data:
                        await context.bot.send_message(chat_id=recipient_data['user_id'], text=f"{user_data["username"]} is requesting Amount: {payment_info['amount']} {payment_info['currency']} from you\n")                        
                    else:        
                        await context.bot.send_message(chat_id=update.effective_chat.id, text="Recipient is not registered yet")
                    pass
            else:
                validation_result = validate_response(assistant_message)
                if validation_result["valid"]:
                    payment_info = extract_json_from_response(assistant_message)
                    await send_confirmation_message(context, update.effective_chat.id, payment_info)
                else:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=assistant_message
                    )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="I'm sorry, but I couldn't process your request. Can you please try again?"
            )

    except NetworkError as e:
        print(f"NetworkError occurred: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="I'm experiencing network issues. Please try sending your message again in a few moments."
        )
    except TelegramError as e:
        print(f"TelegramError occurred: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="An error occurred while processing your message. Please try again later."
        )
    except Exception as e:
        print(f"Unexpected error occurred: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="An unexpected error occurred. Please try again later."
        )

# In your main application setup
def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)
    if isinstance(context.error, NetworkError):
        # Attempt to restart the event loop
        try:
            asyncio.get_event_loop().close()
            asyncio.set_event_loop(asyncio.new_event_loop())
            logger.info("Event loop restarted due to NetworkError")
        except Exception as e:
            logger.error(f"Failed to restart event loop: {e}")

async def send_confirmation_message(context, chat_id, payment_info):
    confirmation_message = (
        f"I understood the following payment information:\n"
        f"Action: {payment_info['action']}\n"
        f"Amount: {payment_info['amount']} {payment_info['currency']}\n"
        f"Recipient: {payment_info['recipient']}\n"
        f"Is this correct? Please reply with 'Yes' or 'No'."
    )
    await context.bot.send_message(chat_id=chat_id, text=confirmation_message)
    
    # Set the conversation state to wait for confirmation
    context.user_data['awaiting_confirmation'] = True
    context.user_data['payment_info'] = payment_info

def validate_response(assistant_response):
    """
    Validates the response from the assistant to check if all necessary information is present.

    Parameters:
    response (str): The assistant's response containing the JSON or missing information.

    Returns:
    dict: A dictionary with 'valid' as a boolean indicating if the response is complete,
          and 'missing_info' as a list of missing details if any.
    """
    required_keys = ["action", "amount", "currency", "recipient"]
    validation_result = {"valid": True, "missing_info": []}
    
    for key in required_keys:
        if key not in assistant_response:
            validation_result["valid"] = False
            validation_result["missing_info"].append(key)
    
    return validation_result

def extract_json_from_response(assistant_response):
    try:
        # Find the JSON object in the response
        json_start = assistant_response.find('{')
        json_end = assistant_response.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_str = assistant_response[json_start:json_end]
            return json.loads(json_str)
        else:
            print("No JSON object found in the response.")
            return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None
    
async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.voice:
            # Handle voice message
            voice_file_id = update.message.voice.file_id
            voice_file = await context.bot.get_file(voice_file_id)
            voice_file_path = os.path.join(".", f"{voice_file_id}.ogg")
            
            # Download the file to the current directory with retry logic
            await download_voice_file(context, voice_file, voice_file_path)

            transcribed_text = convert_audio_to_text(voice_file_path)

            # Clean up the downloaded file
            if os.path.exists(voice_file_path):
                os.remove(voice_file_path)

        elif update.message.text:
            # Handle text message
            transcribed_text = update.message.text
        else:
            # Unsupported message type
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Unsupported message type. Please send either a text or voice message."
            )
            return None

        return transcribed_text

# Add handlers to the application
application.add_handler(CommandHandler('start', start))
application.add_handler(CommandHandler('status', status))
application.add_handler(CommandHandler('send', send))
application.add_handler(MessageHandler(filters.TEXT | filters.VOICE, handle_message))
application.add_error_handler(error_handler)

@app.route('/webhook', methods=['POST'])
def webhook():
    async def process_update():
        # Deserialize the incoming update
        update = Update.de_json(request.get_json(force=True), bot)
        
        # Process the update with the application
        await application.process_update(update)

    loop.run_until_complete(process_update())
    return "ok", 200

def run_app():
    # Initialize the application
    loop.run_until_complete(application.initialize())
    
    # Start the Flask server
    app.run(port=8443)

if __name__ == '__main__':
    run_app()
