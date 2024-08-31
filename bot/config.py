import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
MONGO_URI = os.getenv('MONGO_URI')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/"
