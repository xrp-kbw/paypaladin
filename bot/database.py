from pymongo import MongoClient, errors
from .config import MONGO_URI

def create_mongo_connection():
    try:
        client = MongoClient(MONGO_URI)
        db = client['user_wallets_db']
        client.admin.command('ping')
        print("Connected to MongoDB")
        return db['user_wallets']
    except errors.ConnectionFailure as e:
        print(f"Could not connect to MongoDB: {e}")
        return None

user_wallets_collection = create_mongo_connection()

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

def get_user_wallet_by_username(user_name):
    try:
        return user_wallets_collection.find_one({"username": user_name})
    except Exception as e:
        print(f"Error while retrieving user wallet: {e}")
        return None
