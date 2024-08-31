# bot/__init__.py

# Import key components for easier access at the package level
from .config import MONGO_URI, TELEGRAM_BOT_TOKEN, JSON_RPC_URL
from .database import create_mongo_connection, save_user_wallet, get_user_wallet, get_user_wallet_by_username
from .wallet import generate_faucet_wallet_sync, send_xrp
from .handlers import start, echo, status, send, handle_voice
# from .telegram_bot import initialize_and_run, application, bot
