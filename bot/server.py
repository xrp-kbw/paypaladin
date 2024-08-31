from flask import Flask, request
import telegram
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters

# Initialize Flask app
app = Flask(__name__)

# Initialize the bot
TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
bot = telegram.Bot(token=TOKEN)

# Initialize the dispatcher
dispatcher = Dispatcher(bot, None, use_context=True)

# Define a command handler for the /start command
def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I'm your bot.")

# Define a message handler for text messages
def echo(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)

# Add handlers to the dispatcher
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

@app.route('/webhook', methods=['POST'])
def webhook():
    # Process the incoming update
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok", 200

if __name__ == '__main__':
    # Start the Flask server
    app.run(port=8443)
