import openai
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()


def interact_with_assistant(transcribed_text):
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
    if not client.api_key:
        raise ValueError("OpenAI API key not found. Please set it in the .env file.")

    try:
        # Define the initial prompt for the assistant
        prompt = (
            "You are an assistant helping with cryptocurrency payments. The user "
            "provided the following transcribed text: \n\n"
            f"{transcribed_text}\n\n"
            "Your task is to: \n"
            "1. Extract the action (send or request payment).\n"
            "2. Extract the amount.\n"
            "3. Extract the currency (e.g., XRP, BTC, ETH).\n"
            "4. Extract the recipient's Telegram handle (e.g., @username).\n"
            "5. If any information is missing or unclear, ask the user for clarification.\n"
            "6. Once all information is gathered, generate a JSON object containing "
            "all the necessary payment information for processing on the XRP ledger."
        )

        # Call the OpenAI API with the prompt
        response = client.chat.completions.create(model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ])

        # Extract the JSON result from the assistant's response
        json_result = response.choices[0].message.content
        return json_result

    except Exception as e:
        print(f"An error occurred during interaction with the assistant: {e}")
        return None
