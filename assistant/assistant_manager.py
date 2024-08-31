import json
import re
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

def initialize_client():
    """
    Interacts with the OpenAI assistant to extract payment information,
    prompt for missing details, and generate the final JSON.

    Parameters:
    transcribed_text (str): The text transcribed from the audio.

    Returns:
    str: A JSON string representing the payment information.
    """
    # Load OpenAI API key from environment variable
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        # # Initial conversation loop
        # instructions = (
        #     "You are an assistant helping with cryptocurrency payments. The user "
        #     "will provide some information about the payment they want to make. "
        #     "Your task is to: \n"
        #     "1. Extract the action (send or request payment).\n"
        #     "2. Extract the amount.\n"
        #     "3. Extract the currency (e.g., XRP, BTC, ETH).\n"
        #     "4. Extract the recipient's Telegram handle (e.g., @username).\n"
        #     "5. If any information is missing or unclear, ask the user for clarification.\n"
        #     "6. When a name is mentioned, assume that it is the telegram handle first, and ask for confirmation\n"
        #     "7. Once all information is gathered, generate a JSON object containing "
        #     "all the necessary payment information for processing on the XRP ledger."
        # )

        # # Call the OpenAI API with the prompt
        # assistant = client.beta.assistants.create(
        #     name="PayPaladin",
        #     model="gpt-4o-mini",
        #     instructions=instructions,
        # )
        assistant_id = os.getenv("ASSISTANT_ID")
        
        thread = client.beta.threads.create()
        return client, assistant_id, thread
    except Exception as e:
        print(f"Error initializing client: {e}")
        return None, None, None
    
def add_message_to_thread(client, thread, message):
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=message
    )
