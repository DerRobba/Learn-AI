import os
import base64
import uuid
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import requests
from dotenv import load_dotenv
from openai import OpenAI
from database import init_database, create_user, get_user, save_chat_message, get_chat_history, get_user_chat_sessions, delete_chat_session, rename_chat_session, create_assignment, get_assignments_for_class, get_assignment, delete_assignment, create_submission, get_submissions_for_assignment, get_submission_for_user, get_user_by_username, assign_teacher_to_class, add_student_to_class, get_teachers_for_school, get_students_for_school

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")

# Initialize database
init_database()

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


@app.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        return render_template('login.html', error='Alle Felder sind erforderlich.')

    user = get_user(username, password)
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['user_type'] = user['user_type']
        session['class_name'] = user['class_name']
        session['school'] = user['school']
        return redirect(url_for('index'))
    else:
        return render_template('login.html', error='Ungültige Anmeldedaten.')

@app.route('/register')
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register_post():
    username = request.form.get('username')
    password = request.form.get('password')
    user_type = request.form.get('user_type')
    school = request.form.get('school')

    if not username or not password or not user_type or not school:
        return render_template('register.html', error='Alle Felder sind erforderlich.')

    if not create_user(username, password, user_type, school):
        if user_type == 'it-admin':
            return render_template('register.html', error='Ein IT-Admin für diese Schule existiert bereits.')
        else:
            return render_template('register.html', error='Benutzername bereits vergeben.')
    
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/delete-chat/<session_id>', methods=['POST'])
def delete_chat_route(session_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    delete_chat_session(user_id, session_id)

    # If the deleted chat is the current one, clear it from session
    if session.get('chat_session_id') == session_id:
        session.pop('chat_session_id', None)

    return redirect(url_for('index'))

@app.route('/rename-chat/<session_id>', methods=['POST'])
def rename_chat_route(session_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401

    user_id = session['user_id']
    data = request.get_json()
    new_name = data.get('new_name')

    if not new_name:
        return jsonify({'error': 'Neuer Name ist erforderlich'}), 400

    if rename_chat_session(user_id, session_id, new_name):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Fehler beim Umbenennen des Chats'}), 500

@app.route('/new-chat', methods=['POST'])
def new_chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401

    # Create new chat session
    new_session_id = str(uuid.uuid4())
    session['chat_session_id'] = new_session_id

    return jsonify({'session_id': new_session_id})

@app.route('/load-chat/<session_id>', methods=['POST'])
def load_chat(session_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401

    user_id = session['user_id']

    # Load chat history
    chat_history = get_chat_history(user_id, session_id)

    # Set current session
    session['chat_session_id'] = session_id

    return jsonify({'chat_history': chat_history})

@app.route('/get-chat-history', methods=['GET'])
def get_current_chat_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401

    user_id = session['user_id']
    chat_session_id = session.get('chat_session_id')

    if not chat_session_id:
        return jsonify({'chat_history': []})

    chat_history = get_chat_history(user_id, chat_session_id)
    return jsonify({'chat_history': chat_history})

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_type = session.get('user_type')

    if user_type == 'it-admin':
        return redirect(url_for('admin_dashboard'))

    if user_type == 'teacher' and not session.get('class_name'):
        return render_template('message.html', title='Warte auf Zuweisung', message='Ihr Konto wurde noch keiner Klasse zugewiesen. Bitte wenden Sie sich an Ihren IT-Administrator.')

    # Create new chat session if not exists
    if 'chat_session_id' not in session:
        session['chat_session_id'] = str(uuid.uuid4())

    # Get user's chat sessions
    user_sessions = get_user_chat_sessions(session['user_id'])

    # Get assignments
    assignments = []
    class_name = session.get('class_name')
    if class_name:
        if user_type == 'teacher':
            assignments = get_assignments_for_class(class_name, session.get('school'))
        elif user_type == 'student':
            assignments = get_assignments_for_class(class_name, session.get('school'))

    return render_template('index.html',
                         user_type=user_type,
                         username=session.get('username'),
                         class_name=class_name,
                         chat_sessions=user_sessions,
                         current_session_id=session.get('chat_session_id'),
                         assignments=assignments)

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'it-admin':
        return redirect(url_for('login'))

    school = session.get('school')
    teachers = get_teachers_for_school(school)
    students = get_students_for_school(school)

    return render_template('admin_dashboard.html', teachers=teachers, students=students, school=school)

@app.route('/admin/assign-teacher', methods=['POST'])
def assign_teacher_route():
    if 'user_id' not in session or session.get('user_type') != 'it-admin':
        return redirect(url_for('login'))

    teacher_username = request.form.get('teacher_username')
    class_name = request.form.get('class_name')

    if teacher_username and class_name:
        assign_teacher_to_class(teacher_username, class_name)
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add-student', methods=['POST'])
def add_student_route():
    if 'user_id' not in session or session.get('user_type') != 'it-admin':
        return redirect(url_for('login'))

    student_username = request.form.get('student_username')
    class_name = request.form.get('class_name')

    if student_username and class_name:
        add_student_to_class(student_username, class_name)

    return redirect(url_for('admin_dashboard'))


@app.route('/ask', methods=['POST'])
def ask():
    if 'user_id' not in session:
        return jsonify({'answer': 'Bitte melden Sie sich an.'}), 401

    global system_prompt
    global cached_image
    data = request.get_json()
    question = data.get('question')

    if not question:
        return jsonify({'answer': 'Bitte stellen Sie eine Frage.'}), 400

    user_id = session['user_id']
    chat_session_id = session.get('chat_session_id')

    if not chat_session_id:
        chat_session_id = str(uuid.uuid4())
        session['chat_session_id'] = chat_session_id

    try:
        # Get existing chat history for context
        chat_history = get_chat_history(user_id, chat_session_id)

        # Build conversation context from database
        conversation_context = system_prompt if system_prompt else ""

        # Prepare messages with chat history
        messages = [
            {"role": "system", "content": conversation_context}
        ]

        # Add previous messages from database
        for msg in chat_history:
            if msg['message_type'] == 'user':
                messages.append({"role": "user", "content": msg['content']})
            elif msg['message_type'] == 'assistant':
                messages.append({"role": "assistant", "content": msg['content']})

        # Save user question to database
        image_data = None
        if cached_image:
            image_data = f"data:{cached_image['mime_type']};base64,{cached_image['base64']}"

        save_chat_message(user_id, chat_session_id, 'user', question, image_data)

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

        # Save assistant answer to database
        save_chat_message(user_id, chat_session_id, 'assistant', answer)

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
    vision_system_prompt = os.getenv("VISION_SYSTEM_PROMPT")

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
                    "content": vision_system_prompt
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

@app.route('/create-assignment', methods=['GET', 'POST'])
def create_assignment_route():
    if 'user_id' not in session or session['user_type'] != 'teacher':
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        class_name = session['class_name']
        school = session['school']
        created_by = session['user_id']

        if not title or not description:
            return render_template('create_assignment.html', error='Titel und Beschreibung sind erforderlich.')

        create_assignment(title, description, created_by, class_name, school)
        return redirect(url_for('index'))

    return render_template('create_assignment.html')

@app.route('/assignment/<int:assignment_id>', methods=['GET', 'POST'])
def view_assignment(assignment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    assignment = get_assignment(assignment_id)
    if not assignment:
        return "Assignment not found", 404

    if request.method == 'POST':
        if session['user_type'] == 'student':
            content = request.form.get('submission_content')
            if content:
                create_submission(assignment_id, session['user_id'], content)
                return redirect(url_for('view_assignment', assignment_id=assignment_id))
        return redirect(url_for('view_assignment', assignment_id=assignment_id))

    submission = None
    if session['user_type'] == 'student':
        submission = get_submission_for_user(assignment_id, session['user_id'])
    
    submissions = None
    if session['user_type'] == 'teacher':
        submissions = get_submissions_for_assignment(assignment_id)

    return render_template('view_assignment.html', assignment=assignment, submission=submission, submissions=submissions, user_type=session.get('user_type'))

@app.route('/delete-assignment/<int:assignment_id>', methods=['POST'])
def delete_assignment_route(assignment_id):
    if 'user_id' not in session or session['user_type'] != 'teacher':
        return redirect(url_for('login'))

    delete_assignment(assignment_id)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
