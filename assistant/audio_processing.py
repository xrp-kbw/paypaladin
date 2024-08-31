from dotenv import load_dotenv
import whisper


# Load environment variables from the .env file
load_dotenv()

def convert_audio_to_text(audio_file_path):
    """
    Converts an audio file to text using OpenAI's Whisper API.
    
    Parameters:
    audio_file_path (str): The path to the audio file.
    
    Returns:
    str: The transcribed text from the audio file.
    None: If the transcription fails.
    """
    # # Load OpenAI API key from environment variable
    # client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    # if not client.api_key:
    #     raise ValueError("OpenAI API key not found. Please set it in the .env file.")

    try:
        print("Processing audio...")
        model = whisper.load_model("base.en")
        result = model.transcribe(audio_file_path)
        print("Transcription: " + result["text"])
        return result["text"]

    except Exception as e:
        print(f"An error occurred during audio processing: {e}")
        return None
