import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the token and webhook URL from environment variables
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Set the webhook
response = requests.get(f'https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}')

if response.ok:
    print('Webhook set successfully')
else:
    print(f'Failed to set webhook: {response.status_code}, {response.text}')
