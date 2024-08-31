# scripts/run_assistant.py

from assistant.audio_processing import convert_audio_to_text
from assistant.assistant_interaction import interact_with_assistant

def main(audio_file_path):
    print("Running the assistant...")
    # Step 1: Convert audio to text
    transcribed_text = convert_audio_to_text(audio_file_path)
    
    if not transcribed_text:
        print("Failed to transcribe audio. Exiting.")
        return
    
    # Step 2: Interact with the OpenAI assistant to get the payment JSON
    payment_json = interact_with_assistant(transcribed_text)
    
    if payment_json:
        print("Generated Payment JSON:")
        print(payment_json)
    else:
        print("Failed to generate payment JSON.")
    
if __name__ == "__main__":
    # audio_file_path = input("Enter the path to the audio file: ")
    audio_file_path = "/Users/junmtan/Desktop/test.ogg"
    main(audio_file_path)
