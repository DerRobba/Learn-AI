import os
from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

# In-memory conversation history
conversation_history = []
system_prompt = os.getenv("SYSTEM_PROMPT")
if system_prompt and not any(d.get('role') == 'system' for d in conversation_history):
    conversation_history.append({"role": "system", "content": system_prompt})


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    global conversation_history
    data = request.get_json()
    question = data.get('question')

    if not question:
        return jsonify({'answer': 'Bitte stellen Sie eine Frage.'}), 400

    # Add user question to history
    conversation_history.append({"role": "user", "content": question})

    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": conversation_history,
            "stream": False
        }
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        response_data = response.json()

        answer = response_data.get('message', {}).get('content', 'Ich konnte keine Antwort finden.')
        
        # Add model answer to history
        conversation_history.append({"role": "assistant", "content": answer})

        return jsonify({'answer': answer})
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Ollama API: {e}")
        return jsonify({'answer': 'Entschuldigung, es gab ein Problem mit der Verbindung zu Ollama. Bitte stellen Sie sicher, dass Ollama läuft und das Modell verfügbar ist.'}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({'answer': 'Ein unerwarteter Fehler ist aufgetreten.'}), 500

if __name__ == '__main__':
    app.run(debug=True)