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

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages with improved error handling."""
    try:
        # Get the voice message file ID
        voice_file_id = update.message.voice.file_id
        voice_file = await context.bot.get_file(voice_file_id)
        # Specify the path in the current directory with the appropriate extension
        voice_file_path = os.path.join(".", f"{voice_file_id}.ogg")
        
        # Download the file to the current directory with retry logic
        await download_voice_file(context, voice_file, voice_file_path)

        transcribed_text = convert_audio_to_text(voice_file_path)
        print(transcribed_text)

        # Process the transcribed text with the assistant
        payment_info = interact_with_assistant(transcribed_text)

        if payment_info:
            # Create a confirmation message
            confirmation_message = (
                f"I understood the following payment information:\n"
                f"Action: {payment_info['action']}\n"
                f"Amount: {payment_info['amount']} {payment_info['currency']}\n"
                f"Recipient: {payment_info['recipient']}\n"
                f"Is this correct? Please reply with 'Yes' or 'No'."
            )
            await context.bot.send_message(chat_id=update.effective_chat.id, text=confirmation_message)
            
            # Set the conversation state to wait for confirmation
            context.user_data['awaiting_confirmation'] = True
            context.user_data['payment_info'] = payment_info
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text="I'm sorry, I couldn't process the payment information from your voice message. Could you please try again?"
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
    finally:
        # Clean up the downloaded file
        if os.path.exists(voice_file_path):
            os.remove(voice_file_path)

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

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_response = update.message.text.lower()

    if context.user_data.get('awaiting_confirmation'):
        if user_response == 'yes':
            payment_info = context.user_data['payment_info']
            # Here you would add the logic to process the payment
            await context.bot.send_message(
                chat_id=chat_id, 
                text="Great! I'll process the payment now."
            )
            # Reset the confirmation state
            context.user_data['awaiting_confirmation'] = False
            context.user_data.pop('payment_info', None)
        elif user_response == 'no':
            await context.bot.send_message(
                chat_id=chat_id, 
                text="I'm sorry for the misunderstanding. Let's try to gather the information again."
            )
            # Reset the confirmation state
            context.user_data['awaiting_confirmation'] = False
            context.user_data.pop('payment_info', None)
            
            # Use the interact_with_assistant function to gather information again
            payment_info = await gather_payment_info(update, context)
            if payment_info:
                await send_confirmation_message(context, chat_id, payment_info)
            else:
                await context.bot.send_message(
                    chat_id=chat_id, 
                    text="I'm having trouble understanding the payment details. Could you please provide the information again?"
                )
        else:
            await context.bot.send_message(
                chat_id=chat_id, 
                text="Please respond with 'Yes' or 'No'."
            )
    else:
        # Handle regular text messages by attempting to extract payment information
        payment_info = await gather_payment_info(update, context)
        if payment_info:
            await send_confirmation_message(context, chat_id, payment_info)
        else:
            await context.bot.send_message(
                chat_id=chat_id, 
                text="I couldn't understand the payment details from your message. Could you please provide the information in a clear format?"
            )

async def gather_payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_message = update.message.text

    payment_info = interact_with_assistant(user_message)
    
    while payment_info is None:
        await context.bot.send_message(
            chat_id=chat_id,
            text="I need more information. Could you please provide the missing details?"
        )
        user_response = await context.bot.await_message(chat_id=chat_id)
        payment_info = interact_with_assistant(user_response.text)

    return payment_info

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

def interact_with_assistant(transcribed_text):
    # Load OpenAI API key from environment variable
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        # Initial conversation loop
        assistant_prompt = (
            "You are an assistant helping with cryptocurrency payments. The user "
            "provided the following transcribed text: \n\n"
            f"{transcribed_text}\n\n"
            "Your task is to: \n"
            "1. Extract the action (send or request payment).\n"
            "2. Extract the amount.\n"
            "3. Extract the currency (e.g., XRP, BTC, ETH).\n"
            "4. Extract the recipient's Telegram handle (e.g., @username).\n"
            "5. If any information is missing or unclear, ask the user for clarification.\n"
            "6. When a name is mentioned, assume that it is the telegram handle first, and ask for confirmation\n"
            "7. Once all information is gathered, generate a JSON object containing "
            "all the necessary payment information for processing on the XRP ledger."
        )

        # Call the OpenAI API with the prompt
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": assistant_prompt}
            ]
        )
        # Extract the assistant's message
        assistant_message = response.choices[0].message.content
        
        # Extract JSON from the assistant's message
        return extract_json_from_response(assistant_message)

    except Exception as e:
        print(f"An error occurred during interaction with the assistant: {e}")
        return None

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
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation))
application.add_handler(MessageHandler(filters.VOICE, handle_voice))
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
