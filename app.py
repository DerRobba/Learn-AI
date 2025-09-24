import os
import base64
from flask import Flask, render_template, request, jsonify, send_file
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

BASE_URL = os.getenv("BASE_URL")
MODEL = os.getenv("MODEL")
API_KEY = os.getenv("API_KEY")


client = OpenAI(
    base_url = BASE_URL,
    api_key=API_KEY
)

# In-memory conversation history and current image context
conversation_history = ""
cached_image = None  # Stores cached uploaded image data (base64 + mime_type)
system_prompt = os.getenv("SYSTEM_PROMPT")
if system_prompt and not any(d.get('role') == 'system' for d in conversation_history):
    tmp_sys_prompt = "System Prompt: " + system_prompt
    conversation_history += tmp_sys_prompt


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    global system_prompt
    global conversation_history
    global cached_image
    data = request.get_json()
    question = data.get('question')

    if not question:
        return jsonify({'answer': 'Bitte stellen Sie eine Frage.'}), 400

    # Add user question to history
    tmp_user_q = "User Question: " + question
    conversation_history += tmp_user_q

    try:
        print(conversation_history)
        system_prompt += str(conversation_history)

        # Prepare messages with optional image context
        messages = [
            {"role": "system", "content": conversation_history},
        ]

        # If there's a cached image, include it in the user message
        if cached_image:
            user_content = [
                {"type": "text", "text": question},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{cached_image['mime_type']};base64,{cached_image['base64']}"
                    }
                }
            ]
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": question})

        response = client.chat.completions.create(
          model=MODEL,
          messages=messages
        )
        answer = response.choices[0].message.content
        # Add model answer to history
        tmp_agent_a = "Your Answer: " + answer
        conversation_history += tmp_agent_a
        # Check if AI wants to create .md file
        if answer.lower().startswith("createmd:"):
            content = answer[9:]
            answer = "Sie können ihr Arbeitsblatt nun downloaden."
            print(content.strip())
            with open("output.md", "w") as f:
                f.write(content.strip())
            os.system('curl --data-urlencode "markdown=$(cat output.md)" --output output.pdf http://192.168.178.94:8002')
        return jsonify({'answer': answer})
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Ollama API: {e}")
        return jsonify({'answer': 'Entschuldigung, es gab ein Problem mit der Verbindung zu Ollama. Bitte stellen Sie sicher, dass Ollama läuft und das Modell verfügbar ist.'}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({'answer': 'Ein unerwarteter Fehler ist aufgetreten.'}), 500
@app.route('/cache-image', methods=['POST'])
def cache_image():
    global cached_image

    if 'image' not in request.files:
        return jsonify({'message': 'Kein Bild gefunden.'}), 400

    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'message': 'Kein Bild ausgewählt.'}), 400

    try:
        # Read image and encode to base64
        image_data = image_file.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')

        # Get the mime type
        mime_type = image_file.content_type
        if not mime_type.startswith('image/'):
            return jsonify({'message': 'Datei ist kein gültiges Bild.'}), 400

        # Store image in cache
        cached_image = {
            'base64': base64_image,
            'mime_type': mime_type,
            'filename': image_file.filename
        }

        return jsonify({'message': 'Bild wurde im Zwischenspeicher gespeichert. Du kannst nun Fragen dazu stellen!'})

    except Exception as e:
        print(f"Error caching image: {e}")
        return jsonify({'message': 'Es gab einen Fehler beim Zwischenspeichern des Bildes.'}), 500

@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    global cached_image
    cached_image = None
    return jsonify({'message': 'Zwischenspeicher wurde geleert.'})

@app.route('/analyze-image', methods=['POST'])
def analyze_image():
    if 'image' not in request.files:
        return jsonify({'analysis': 'Kein Bild gefunden.'}), 400

    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'analysis': 'Kein Bild ausgewählt.'}), 400

    try:
        # Read image and encode to base64
        image_data = image_file.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')

        # Get the mime type
        mime_type = image_file.content_type
        if not mime_type.startswith('image/'):
            return jsonify({'analysis': 'Datei ist kein gültiges Bild.'}), 400

        # Send to OpenAI Vision API
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Du bist ein hilfreicher Assistent, der Bilder analysiert und beschreibt. Antworte auf Deutsch."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analysiere dieses Bild und beschreibe detailliert, was du siehst. Falls es sich um Text handelt, extrahiere und erkläre den Inhalt. Falls es sich um ein Diagramm, eine Grafik oder ein wissenschaftliches Bild handelt, erkläre es so, dass es für Lernzwecke nützlich ist."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )

        analysis = response.choices[0].message.content
        return jsonify({'analysis': analysis})

    except Exception as e:
        print(f"Error analyzing image: {e}")
        return jsonify({'analysis': 'Es gab einen Fehler bei der Bildanalyse. Bitte versuche es später noch einmal.'}), 500

@app.route('/download')
def download_file():
    file_path="output.pdf"
    return send_file(
        file_path,
        as_attachment=True,
        download_name="Arbeitsblatt.pdf"
    )
if __name__ == '__main__':
    app.run(debug=True)
