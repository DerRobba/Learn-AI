import os
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

# In-memory conversation history
conversation_history = ""
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
    data = request.get_json()
    question = data.get('question')

    if not question:
        return jsonify({'answer': 'Bitte stellen Sie eine Frage.'}), 400

    # Add user question to history
    tmp_user_q = "User Question: " + question
    conversation_history += tmp_user_q

    try:
#        payload = {
#            "model": OLLAMA_MODEL,
#            "messages": conversation_history,
#            "stream": False
#        }
#        response = requests.post(OLLAMA_API_URL, json=payload)
#        response.raise_for_status()
#        response_data = response.json()
        print(conversation_history)
        system_prompt += str(conversation_history)
        response = client.chat.completions.create(
          model=MODEL,
          messages=[
            {"role": "system", "content": conversation_history},
            {"role": "user", "content": question}
          ]
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
@app.route('/download')
def download_file():
    file_path="output.pdf"
    return send_file(
        file_path,
        as_attachment=True,
        download_name="Arbeitsblatt.pdf"
    )
if __name__ == '__main__':
    app.run(debug=True
