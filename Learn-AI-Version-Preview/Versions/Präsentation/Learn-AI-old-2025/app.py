import subprocess
import os
import base64
import uuid
import json
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, Response, abort, current_app
import requests
from dotenv import load_dotenv
from openai import OpenAI
from database import init_database, create_user, get_user, save_chat_message, get_chat_history, get_user_chat_sessions, delete_chat_session, rename_chat_session, create_assignment, get_assignments_for_class, get_assignment, delete_assignment, create_submission, get_submissions_for_assignment, get_submission_for_user, get_user_by_username, assign_teacher_to_class, add_student_to_class, get_teachers_for_school, get_students_for_school, get_unique_school_names, get_student_usernames_for_school, get_unique_class_names_for_school, get_teacher_usernames_for_school

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")

@app.route('/api/schools')
def get_schools():
    schools = get_unique_school_names()
    return jsonify(schools)

@app.route('/api/students')
def get_students():
    if 'user_id' not in session or session.get('user_type') != 'it-admin':
        return jsonify([])
    school = session.get('school')
    students = get_student_usernames_for_school(school)
    return jsonify(students)

@app.route('/api/classes')
def get_classes():
    if 'user_id' not in session or session.get('user_type') != 'it-admin':
        return jsonify([])
    school = session.get('school')
    classes = get_unique_class_names_for_school(school)
    return jsonify(classes)

@app.route('/api/teachers')
def get_teachers():
    if 'user_id' not in session or session.get('user_type') != 'it-admin':
        return jsonify([])
    school = session.get('school')
    teachers = get_teacher_usernames_for_school(school)
    return jsonify(teachers)

# Initialize database
init_database()

# Ensure sheets directory exists
if not os.path.exists('sheets'):
    os.makedirs('sheets')

BASE_URL = os.getenv("BASE_URL")
MODEL = os.getenv("MODEL")
API_KEY = os.getenv("API_KEY")


client = OpenAI(
    base_url = BASE_URL,
    api_key=API_KEY
)

system_prompt = os.getenv("SYSTEM_PROMPT")

ip_ban_list = os.getenv("IP_BAN_LIST", "").split(",")


@app.before_request
def block_method():
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        ip = request.environ.get('HTTP_X_FORWARDED_FOR').split(', ')[0]
    else:
        ip = request.environ.get('REMOTE_ADDR')
    print(ip)
    if ip in ip_ban_list:
        abort(403)
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
    password_confirm = request.form.get('password_confirm')
    user_type = request.form.get('user_type')
    school = request.form.get('school')

    if not username or not password or not password_confirm or not user_type or not school:
        return render_template('register.html', error='Alle Felder sind erforderlich.')

    if password != password_confirm:
        return render_template('register.html', error='Die Passwörter stimmen nicht überein.')

    if not create_user(username, password, user_type, school):
        if user_type == 'it-admin':
            return render_template('register.html', error='Ein IT-Admin für diese Schule existiert bereits.')
        else:
            return render_template('register.html', error='Benutzername bereits vergeben.')
    
    # Automatically log in the user after registration
    user = get_user_by_username(username)
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['user_type'] = user['user_type']
        session['class_name'] = user['class_name']
        session['school'] = user['school']
        return redirect(url_for('index'))
    else:
        # This should not happen if create_user was successful
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
    
    # Clear cached image from session and filesystem
    filename = session.pop('cached_image_filename', None)
    if filename:
        try:
            os.remove(os.path.join('uploads', filename))
        except OSError as e:
            print(f"Error deleting cached image: {e}")

    return jsonify({'session_id': new_session_id})

@app.route('/ask')
def ask():
    if 'user_id' not in session:
        return jsonify({'answer': 'Bitte melden Sie sich an.'}), 401

    question = request.args.get('question')

    if not question:
        return jsonify({'answer': 'Bitte stellen Sie eine Frage.'}), 400

    user_id = session['user_id']
    chat_session_id = session.get('chat_session_id')
    cached_image_filename = session.get('cached_image_filename')
    cached_image = None

    if cached_image_filename:
        try:
            image_path = os.path.join('uploads', cached_image_filename)
            with open(image_path, "rb") as f:
                image_data = f.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Get mime type from filename extension
            mime_type = 'image/' + os.path.splitext(cached_image_filename)[1][1:]

            cached_image = {
                'base64': base64_image,
                'mime_type': mime_type,
                'filename': cached_image_filename
            }
        except Exception as e:
            print(f"Error reading cached image: {e}")


    if not chat_session_id:
        chat_session_id = str(uuid.uuid4())
        session['chat_session_id'] = chat_session_id

    def generate():
        try:
            # Get existing chat history for context
            chat_history = get_chat_history(user_id, chat_session_id)

            # Build conversation context from database
            conversation_context = system_prompt if system_prompt else ""
            conversation_context += "\n\nWICHTIG: Wenn der Benutzer ein Arbeitsblatt möchte, antworte AUSSCHLIESSLICH mit einem JSON-Objekt in diesem Format: {\"type\": \"worksheet_creation\", \"content\": \"MARKDOWN_INHALT\"}. Schreibe keinen anderen Text."

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

            response_stream = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                stream=True
            )

            full_answer = ""
            for chunk in response_stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_answer += content
                    yield f"data: {content}\n\n"

            # Check if AI wants to create .md file (JSON or Legacy)
            md_content = None
            
            try:
                # Try to parse as JSON first
                # Handle potential leading/trailing whitespace or markdown code blocks if the model adds them
                clean_answer = full_answer.strip()
                if clean_answer.startswith("```json"):
                    clean_answer = clean_answer[7:]
                if clean_answer.startswith("```"):
                    clean_answer = clean_answer[3:]
                if clean_answer.endswith("```"):
                    clean_answer = clean_answer[:-3]
                
                json_response = json.loads(clean_answer.strip())
                if isinstance(json_response, dict) and json_response.get('type') == 'worksheet_creation':
                    md_content = json_response.get('content')
            except Exception as e:
                # Not valid JSON or other error
                pass
            
            if not md_content and full_answer.lower().startswith("createmd:"):
                md_content = full_answer[9:]

            if md_content:
                worksheet_uuid = str(uuid.uuid4())
                md_filename = f"sheets/{worksheet_uuid}.md"
                pdf_filename = f"sheets/{worksheet_uuid}.pdf"
                download_answer = "Sie können ihr Arbeitsblatt nun downloaden."

                print(md_content.strip())
                with open(md_filename, "w", encoding='utf-8') as f:
                    f.write(md_content.strip())
                
                # Convert MD to PDF using the external service
                try:
                    curl_command = [
                        'curl',
                        '--data-urlencode',
                        f'markdown=@{md_filename}',
                        '--output',
                        pdf_filename,
                        'https://md-to-pdf.fly.dev'
                    ]
                    result = subprocess.run(curl_command, capture_output=True, text=True, check=True)
                    print("Curl stdout:", result.stdout)
                    print("Curl stderr:", result.stderr)
                except subprocess.CalledProcessError as e:
                    print(f"Curl command failed with error: {e}")
                    print("Curl stdout:", e.stdout)
                    print("Curl stderr:", e.stderr)
                    # Optionally, handle the error more gracefully, e.g., yield an error message to the frontend
                    yield "data: Fehler beim Erstellen des Arbeitsblatts. Bitte versuchen Sie es später erneut.\n\n"
                    return

                # Save assistant answer and worksheet filename to database
                # Store only the basename in the database for cleaner paths
                pdf_basename = os.path.basename(pdf_filename)
                save_chat_message(user_id, chat_session_id, 'assistant', download_answer, worksheet_filename=pdf_basename)
                yield f"data: {download_answer}\n\n"
                yield f"data: WORKSHEET_DOWNLOAD_LINK:{pdf_basename}\n\n" # Special tag for frontend
            else:
                # Save full assistant answer to database
                save_chat_message(user_id, chat_session_id, 'assistant', full_answer)

        except requests.exceptions.RequestException as e:
            print(f"Error communicating with Ollama API: {e}")
            yield "data: Entschuldigung, es gab ein Problem mit der Verbindung zu Ollama. Bitte stellen Sie sicher, dass Ollama läuft und das Modell verfügbar ist.\n\n"
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            yield "data: Ein unerwarteter Fehler ist aufgetreten.\n\n"

    return Response(generate(), mimetype='text/event-stream')

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

@app.route('/download-worksheet/<filename>')
def download_sheet(filename):
    try:
        # Sanitize filename to prevent directory traversal
        filename = os.path.basename(filename)
        return send_file(os.path.join('sheets', filename), as_attachment=True)
    except Exception as e:
        print(f"Error sending file: {e}")
        return abort(404)

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



@app.route('/cache-image', methods=['POST'])
def cache_image():
    if 'image' not in request.files:
        return jsonify({'message': 'Kein Bild gefunden.'}), 400

    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'message': 'Kein Bild ausgewählt.'}), 400

    try:
        # Generate a unique filename
        filename = str(uuid.uuid4()) + os.path.splitext(image_file.filename)[1]
        image_path = os.path.join('uploads', filename)
        image_file.save(image_path)

        # Store filename in session
        session['cached_image_filename'] = filename

        return jsonify({'message': 'Bild wurde im Zwischenspeicher gespeichert. Du kannst nun Fragen dazu stellen!'})

    except Exception as e:
        print(f"Error caching image: {e}")
        return jsonify({'message': 'Es gab einen Fehler beim Zwischenspeichern des Bildes.'}), 500

@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    filename = session.pop('cached_image_filename', None)
    if filename:
        try:
            os.remove(os.path.join('uploads', filename))
        except OSError as e:
            print(f"Error deleting cached image: {e}")
    return jsonify({'message': 'Zwischenspeicher wurde geleert.'})
