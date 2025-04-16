import os
from flask import Flask, request, jsonify
from flask_cors import CORS # Import CORS
import openai
from livekit import api as livekit_api # Alias to avoid conflict if needed
from google.cloud import secretmanager

# --- Configuration ---
app = Flask(__name__)
CORS(app) # Enable CORS for all routes, restrict later if needed

# --- Helper Function to Get Secrets ---
def get_secret(secret_id, project_id="shrink-1", version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# --- Load Secrets ---
try:
    openai_api_key = get_secret("openai-api-key")
    livekit_host = "YOUR_LIVEKIT_HOST_URL" # e.g., https://your-project.livekit.cloud
    livekit_api_key = get_secret("livekit-api-key")
    livekit_api_secret = get_secret("livekit-api-secret")

    openai.api_key = openai_api_key
    # Initialize LiveKit API client (if the SDK requires it)
    # livekit_service = livekit_api.LiveKitAPI(livekit_host, livekit_api_key, livekit_api_secret) # Example structure, check SDK docs
    print("Secrets loaded successfully.")
except Exception as e:
    print(f"ERROR loading secrets: {e}")
    # Handle missing secrets appropriately - maybe exit or run in a limited mode
    openai_api_key = None
    livekit_api_key = None
    livekit_api_secret = None
    livekit_host = None


# --- API Endpoints ---

@app.route('/')
def hello():
    return "Backend is running!"

# Placeholder for LiveKit Token Generation
@app.route('/generate-livekit-token', methods=['POST'])
def generate_token():
    if not livekit_api_key or not livekit_api_secret:
         return jsonify({"error": "LiveKit configuration missing"}), 500

    # Get user identity from request (you'll send this from frontend)
    data = request.get_json()
    user_identity = data.get('identity', 'default-user')
    user_name = data.get('name', 'Default User') # Optional name

    # Create LiveKit Access Token
    # Consult the Python livekit-server-sdk documentation for the exact syntax
    # It will look something like this:
    try:
        token = livekit_api.AccessToken(livekit_api_key, livekit_api_secret) \
            .with_identity(user_identity) \
            .with_name(user_name) \
            .with_grants(livekit_api.VideoGrant(room_join=True, room='my-conversation-room')) # Define room name, permissions
            # .with_ttl(3600) # Optional: token validity duration (seconds)

        jwt_token = token.to_jwt()
        print(f"Generated token for {user_identity}")
        return jsonify({"identity": user_identity, "token": jwt_token})
    except Exception as e:
         print(f"Error generating LiveKit token: {e}")
         return jsonify({"error": "Could not generate LiveKit token"}), 500


# Placeholder for OpenAI Chat
@app.route('/chat', methods=['POST'])
def chat_endpoint():
    if not openai_api_key:
         return jsonify({"error": "OpenAI configuration missing"}), 500

    data = request.get_json()
    # Expecting 'messages': a list of {'role': 'user'/'assistant', 'content': '...'}
    messages = data.get('messages', [])
    system_prompt = "You are a helpful assistant." # Define your system prompt here

    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    # Prepend system prompt (if not already part of history management)
    full_conversation = [{"role": "system", "content": system_prompt}] + messages

    try:
        client = openai.OpenAI(api_key=openai_api_key) # Use the newer client instantiation
        response = client.chat.completions.create(
            model="gpt-4.1", # As specified
            messages=full_conversation
        )
        assistant_reply = response.choices[0].message.content
        print("Generated chat response.")
        return jsonify({"reply": assistant_reply})
    except Exception as e:
        print(f"Error calling OpenAI Chat: {e}")
        return jsonify({"error": "Failed to get response from OpenAI"}), 500


# Placeholder for OpenAI STT (Speech-to-Text)
@app.route('/transcribe', methods=['POST'])
def transcribe_endpoint():
    if not openai_api_key:
         return jsonify({"error": "OpenAI configuration missing"}), 500

    if 'audio_file' not in request.files:
         return jsonify({"error": "No audio file part"}), 400

    file = request.files['audio_file']
    if file.filename == '':
         return jsonify({"error": "No selected file"}), 400

    try:
        client = openai.OpenAI(api_key=openai_api_key)
        # Send the file directly to OpenAI API
        # Note: The 'file' object from Flask needs to be handled correctly.
        # OpenAI library expects a file-like object or tuple (filename, file_content)
        transcription = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe", # As specified
            file=(file.filename, file.stream, file.mimetype) # Pass as tuple
        )
        print("Generated transcription.")
        return jsonify({"text": transcription.text})
    except Exception as e:
        print(f"Error calling OpenAI STT: {e}")
        return jsonify({"error": "Failed to transcribe audio"}), 500


# Placeholder for OpenAI TTS (Text-to-Speech)
@app.route('/synthesize', methods=['POST'])
def synthesize_endpoint():
    if not openai_api_key:
         return jsonify({"error": "OpenAI configuration missing"}), 500

    data = request.get_json()
    text_to_speak = data.get('text')

    if not text_to_speak:
        return jsonify({"error": "No text provided"}), 400

    try:
        client = openai.OpenAI(api_key=openai_api_key)
        response = client.audio.speech.create(
            model="gpt-4o-mini-tts", # As specified
            voice="alloy", # Choose a voice
            input=text_to_speak,
            response_format="mp3" # Choose format (mp3, opus, aac, flac)
        )
        # Stream the audio back to the client
        # Flask doesn't handle streaming binary responses super easily out of the box
        # For simplicity here, we'll return the binary content directly.
        # The frontend will need to handle this.
        # For large files, streaming is better (using Flask Response object with generator)
        print("Generated speech.")
        # It's better to stream, but let's send the whole content for now
        # response.stream_to_file("output.mp3") # Example if saving needed
        audio_content = response.content # Get the binary content
        from flask import make_response
        resp = make_response(audio_content)
        resp.headers['Content-Type'] = 'audio/mpeg' # Set correct MIME type for MP3
        return resp

    except Exception as e:
        print(f"Error calling OpenAI TTS: {e}")
        return jsonify({"error": "Failed to synthesize speech"}), 500


# --- Run the App ---
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))