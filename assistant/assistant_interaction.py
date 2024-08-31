import json
import re
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

def extract_json_from_response(assistant_response):
    """
    Extracts the JSON object from the assistant's response.

    Parameters:
    assistant_response (str): The full response from the assistant.

    Returns:
    dict: The extracted JSON object as a Python dictionary.
    None: If no JSON object is found in the response.
    """
    try:
        # Regular expression to match the JSON object in the response
        json_match = re.search(r'{.*?}', assistant_response, re.DOTALL)
        
        if json_match:
            json_str = json_match.group(0)
            # Convert the JSON string to a Python dictionary
            json_obj = json.loads(json_str)
            return json_obj
        else:
            print("No JSON object found in the response.")
            return None
    except Exception as e:
        print(f"An error occurred while extracting JSON: {e}")
        return None

def validate_response(response):
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
        if key not in response:
            validation_result["valid"] = False
            validation_result["missing_info"].append(key)
    
    return validation_result

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

        while True:
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
            
            # Validate the assistant's response
            validation_result = validate_response(assistant_message)
            
            if validation_result["valid"]:
                # If the response is valid, extract the actual JSON file from the assistant's message
                return extract_json_from_response(assistant_message)
            else:
                # If information is missing, ask the user for the missing details
                missing_info_prompt = assistant_message
                user_input = input(missing_info_prompt + "\n")
                
                # Update the assistant prompt with the additional information
                assistant_prompt += f"\n\nThe user provided the following additional information: {user_input}\n"

    except Exception as e:
        print(f"An error occurred during interaction with the assistant: {e}")
        return None
