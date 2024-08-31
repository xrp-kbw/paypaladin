from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import os
from dotenv import load_dotenv
from xrpl.clients import JsonRpcClient
from bot import create_mongo_connection, get_user_wallet, save_user_wallet, generate_faucet_wallet_sync, send_xrp, start, echo, status, send
from assistant.audio_processing import convert_audio_to_text
from assistant.assistant_interaction import interact_with_assistant
from telegram.error import NetworkError, TelegramError
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
from openai import OpenAI
import json

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
            return

        # Interact with the assistant
        payment_info = None
        while not payment_info:
            assistant_message = interact_with_assistant(transcribed_text)
            
            if assistant_message:
                # Send the assistant's response back to the user
                await context.bot.send_message(chat_id=update.effective_chat.id, text=assistant_message)

                # Check if the assistant's response contains payment information
                validation_result = validate_response(assistant_message)
                if validation_result["valid"]:
                    payment_info = extract_json_from_response(assistant_message)
                else:
                    # Wait for user's response
                    user_reply = await context.bot.wait_for_message(chat_id=update.effective_chat.id)
                    transcribed_text = user_reply.text
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="I'm sorry, but I couldn't process your request. Can you please try again?"
                )
                break

        if payment_info:
            await send_confirmation_message(context, update.effective_chat.id, payment_info)

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
