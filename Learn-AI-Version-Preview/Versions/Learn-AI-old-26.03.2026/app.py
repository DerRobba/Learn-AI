import subprocess
import os
import base64
import uuid
import json
import re
import traceback
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, Response, abort, current_app, has_request_context
import requests
from dotenv import load_dotenv
from openai import OpenAI
from database import init_database, create_user, get_user, save_chat_message, get_chat_history, get_user_chat_sessions, delete_chat_session, rename_chat_session, create_assignment, get_assignments_for_class, get_assignment, delete_assignment, create_submission, get_submissions_for_assignment, get_submission_for_user, get_user_by_username, assign_teacher_to_class, add_student_to_class, get_teachers_for_school, get_students_for_school, get_unique_school_names, get_student_usernames_for_school, get_unique_class_names_for_school, get_teacher_usernames_for_school, create_homework, get_homework_for_user, delete_homework, toggle_homework_status, create_subject, get_subjects, delete_subject, get_single_homework, delete_old_completed_homework, update_homework, get_subject_id_by_name, delete_all_homework, add_memory, get_memories, delete_memory, delete_memory_by_content, set_math_solver_status, get_math_solver_status, update_chat_message_worksheet, update_chat_session_subject, get_unique_chat_subjects, get_chat_sessions_by_subject, get_all_previous_chats_summaries, get_session_name, get_first_login_status, set_first_login_status

load_dotenv()

# Global tracking for active generation sessions
# track active streaming responses per chat session.  
# we store a simple counter so that overlapping requests in the
# same session don't clear the flag prematurely.  
# key: chat_session_id, value: number of active generators
# (previously this was a boolean which could get stuck and prevented
# further worksheet requests in the same chat).

generating_sessions = {}

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")

def convert_to_iso_date(date_str):
    if not date_str:
        return date_str
    # Check if already ISO format (YYYY-MM-DD)
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    # Check if German format DD.MM.YYYY
    match = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$', date_str)
    if match:
        d, m, y = match.groups()
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return date_str

@app.template_filter('german_date')
def german_date_filter(date_str):
    if not date_str:
        return ""
    # Try to match YYYY-MM-DD (possibly with time)
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if match:
        y, m, d = match.groups()
        return f"{d}.{m}.{y}"
    return date_str

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

@app.route('/api/chat-subjects')
def api_get_chat_subjects():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    
    user_id = session['user_id']
    subjects = get_unique_chat_subjects(user_id)
    return jsonify(subjects)

@app.route('/api/chat-sessions-by-subject')
def api_get_chat_sessions_by_subject():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    
    user_id = session['user_id']
    subject = request.args.get('subject')
    
    if not subject:
        return jsonify({'error': 'Betreff ist erforderlich'}), 400
        
    sessions = get_chat_sessions_by_subject(user_id, subject)
    return jsonify(sessions)

# Initialize database
init_database()

# Ensure sheets directory exists
if not os.path.exists('sheets'):
    os.makedirs('sheets')

# Ensure uploads directory exists
if not os.path.exists('uploads'):
    os.makedirs('uploads')

BASE_URL = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "google/gemma-3-27b-it:free")
API_KEY = os.getenv("API_KEY")


client = OpenAI(
    base_url = BASE_URL if BASE_URL else "https://openrouter.ai/api/v1",
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
    agb_accept = request.form.get('agb_accept')
    privacy_accept = request.form.get('privacy_accept')

    if not username or not password or not password_confirm or not user_type or not school:
        return render_template('register.html', error='Alle Felder sind erforderlich.')

    if not agb_accept or not privacy_accept:
        return render_template('register.html', error='Du musst die Nutzungsbedingungen und die Datenschutzerklärung akzeptieren.')

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

    # Insert welcome message to persist session
    save_chat_message(session['user_id'], new_session_id, 'assistant', 'Hi! Ich bin dein persönlicher Lernassistent. Sprich mit mir oder schreibe mir deine Fragen!', session_name='Neuer Chat')

    return jsonify({'session_id': new_session_id})

@app.route('/ask')
def ask():
    user_id = session.get('user_id')
    question = request.args.get('question')

    if not question:
        return jsonify({'answer': 'Bitte stellen Sie eine Frage.'}), 400

    chat_session_id = session.get('chat_session_id')
    # make sure any stale "generating" flag from a previous request
    # is cleared before we start processing a new message.  this fixes a
    # situation where a worksheet stream hung or the client disconnected
    # and the flag remained set, blocking subsequent worksheet
    # creations in the same chat.
    if chat_session_id:
        generating_sessions.pop(chat_session_id, None)

    cached_image_filename = session.get('cached_image_filename')
    cached_image = None

    if cached_image_filename:
        try:
            image_path = os.path.join('uploads', cached_image_filename)
            with open(image_path, "rb") as f:
                image_data = f.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
            mime_type = 'image/' + os.path.splitext(cached_image_filename)[1][1:]
            cached_image = {'base64': base64_image, 'mime_type': mime_type, 'filename': cached_image_filename}
            session.pop('cached_image_filename', None)
        except Exception as e:
            print(f"Error reading cached image: {e}")

    # Determine user_id (0 for guests)
    db_user_id = user_id if user_id else 0

    if not chat_session_id:
        chat_session_id = str(uuid.uuid4())
        session['chat_session_id'] = chat_session_id

    # Save user message to database
    img_data = None
    if cached_image:
        img_data = f"data:{cached_image['mime_type']};base64,{cached_image['base64']}"
    
    save_chat_message(db_user_id, chat_session_id, 'user', question, image_data=img_data)

    # Get existing chat history and other context
    if user_id:
        existing_chat_history = get_chat_history(user_id, chat_session_id)
        current_chat_subject = existing_chat_history[0].get('chat_subject') if existing_chat_history else None
        earlier_chat_summaries = get_all_previous_chats_summaries(user_id, exclude_session_id=chat_session_id)
        current_homework = get_homework_for_user(user_id)[:15]
        current_subjects = get_subjects(user_id)
        user_memories = get_memories(user_id)
        memories_text = "\n".join([f"- {m['content']}" for m in user_memories])
        math_solver_enabled = get_math_solver_status(user_id)
    else:
        existing_chat_history = get_chat_history(0, chat_session_id)
        current_chat_subject = None
        earlier_chat_summaries = []
        current_homework = []
        current_subjects = []
        memories_text = ""
        math_solver_enabled = False

    # Capture static copy for generator
    chat_history_for_gen = list(existing_chat_history)

    def generate():
        nonlocal current_chat_subject

        def yield_sse(data):
            for line in str(data).split('\n'):
                yield f"data: {line}\n"
            yield "\n"

        # increment the counter for active generators in this session
        generating_sessions[chat_session_id] = generating_sessions.get(chat_session_id, 0) + 1
        client_disconnected = False
        full_answer = ""
        md_content = None # Sofort initialisieren
        homework_results = []
        
        try:
            # Sofort einen Ping senden, um Timeouts zu verhindern
            yield from yield_sse("PING")
            
            now = datetime.now()
            # ... (Rest der Kontext-Erstellung bleibt gleich) ...
            current_date_str = now.strftime("%Y-%m-%d")
            current_weekday = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][now.weekday()]

            # Build conversation context
            raw_system_prompt = system_prompt if system_prompt else ""
            
            # Wir lassen das "niemals direkt antworten" im Grund-Prompt stehen, 
            # fügen aber eine sehr spezifische Ausnahmeregel hinzu.
            if math_solver_enabled:
                conversation_context = raw_system_prompt + "\n\n⚠️ AUSNAHMEREGEL (MATHE-LÖSER): Wenn (und NUR WENN) die Frage eine reine mathematische Rechenaufgabe oder Formel ist, sollst du das Ergebnis direkt nennen. Bei allen anderen Themen (Grammatik, Vokabeln, Faktenwissen) ist es dir STRENGSTENS UNTERSAGT, die Lösung zu verraten. Dort musst du weiterhin guiden."
            else:
                conversation_context = raw_system_prompt

            conversation_context += f"\n\nHEUTE IST: {current_weekday}, der {current_date_str}"
            
            # --- STILLE HINTERGRUND-AKTIONEN ---
            conversation_context += "\n\nHINTERGRUND-AUFGABEN (STRENG GEHEIM):"
            conversation_context += "\n1. FACH-ZUORDNUNG: Entscheide stillschweigend über das Fach mit <action>{\"type\": \"set_chat_subject\", \"subject\": \"[FACH]\"}</action>. Erwähne dies NICHT im Text."
            
            if user_id:
                current_name = get_session_name(user_id, chat_session_id)
                if not current_name or current_name.strip() in ['Neuer Chat', 'None', '']:
                    conversation_context += "\n2. TITEL: Sende <action>{\"type\": \"chat_naming\", \"title\": \"[TITEL]\"}</action> stillschweigend."

            # Finaler Entscheidungs-Check
            if math_solver_enabled:
                 conversation_context += "\n\nENTSCHEIDUNGSMATRIX:\n- Mathe-Aufgabe? -> Lösung direkt nennen.\n- Deutsch/Sprachen/Sonstiges? -> Lösung NIEMALS nennen, nur Tipps geben (Guiding)."
            else:
                 conversation_context += "\n\nENTSCHEIDUNGSMATRIX: Alle Fächer -> Nur Tipps geben (Guiding)."

            processed_history = []
            for msg in chat_history_for_gen:
                # ... (Rest der History-Verarbeitung bleibt gleich)
                role = msg['message_type']
                if role not in ['user', 'assistant']: continue
                content = msg['content']
                img = msg.get('image_data')
                if role == 'user' and img:
                    msg_obj = {"role": "user", "content": [{"type": "text", "text": content}, {"type": "image_url", "image_url": {"url": img}}]}
                else:
                    msg_obj = {"role": role, "content": content}

                if not processed_history:
                    if role == 'user': processed_history.append(msg_obj)
                else:
                    if role != processed_history[-1]['role']: processed_history.append(msg_obj)
                    else: processed_history[-1]['content'] = str(processed_history[-1]['content']) + "\n" + content

            # Construct messages for the model
            messages = [{"role": "system", "content": conversation_context}]
            
            # Add final reminder for math solver or guiding
            final_reminder = ""
            if math_solver_enabled:
                final_reminder = "\n\n⚠️ ERINNERUNG: Der Mathe-Löser ist AKTIV. Löse NUR mathematische Aufgaben JETZT DIREKT. Für alle anderen Fächer (Deutsch, Sprachen, etc.) gilt weiterhin striktes GUIDING!"
            else:
                final_reminder = "\n\n⚠️ ERINNERUNG: Der Mathe-Löser ist AUS. Für ALLE Fächer gilt striktes GUIDING (keine Lösungen nennen)."

            for i, msg in enumerate(processed_history):
                role = msg['role']
                content = msg['content']
                
                # Wenn es die letzte User-Nachricht ist, hänge den Reminder an
                if i == len(processed_history) - 1 and role == 'user':
                    if isinstance(content, list):
                        content[0]['text'] += final_reminder
                    else:
                        content += final_reminder
                
                messages.append({"role": role, "content": content})

            if messages and messages[-1]['role'] == 'user':
                # Falls wir eine leere Antwort erzwingen wollten (aus altem Code)
                pass 

            # --- KI ANFRAGE MIT RETRY LOGIK ---
            max_retries = 3
            retry_delay = 2
            response_stream = None
            
            for attempt in range(max_retries):
                try:
                    response_stream = client.chat.completions.create(model=MODEL, messages=messages, stream=True)
                    break  # Erfolg!
                except Exception as api_error:
                    error_msg = str(api_error)
                    if ("429" in error_msg or "rate" in error_msg.lower()) and attempt < max_retries - 1:
                        print(f"DEBUG: Rate limit hit, retrying in {retry_delay}s... (Versuch {attempt+1}/{max_retries})")
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Wartezeit verdoppeln
                        continue
                    
                    # Wenn alle Versuche fehlgeschlagen sind oder kein Rate-Limit-Fehler
                    final_error = ""
                    if "429" in error_msg or "rate" in error_msg.lower():
                        final_error = "⚠️ Die KI-API ist momentan überlastet. Auch nach mehreren Versuchen konnte keine Verbindung hergestellt werden. Bitte warte eine Minute."
                        print(f"API Rate Limit Final: {api_error}")
                    elif "401" in error_msg or "unauthorized" in error_msg.lower():
                        final_error = "❌ API-Authentifizierungsfehler. Überprüfe deinen API-Schlüssel in den Einstellungen."
                        print(f"API Auth Error: {api_error}")
                    else:
                        final_error = f"❌ Fehler bei der KI-Anfrage: {api_error}"
                        print(f"API Error: {api_error}")
                    
                    # In DB speichern
                    save_chat_message(db_user_id, chat_session_id, 'assistant', final_error, chat_subject=current_chat_subject)
                    yield from yield_sse(final_error)
                    return

            try:
                for chunk in response_stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        full_answer += content
                        if not client_disconnected:
                            try:
                                yield from yield_sse(content)
                            except GeneratorExit:
                                client_disconnected = True
                                print(f"DEBUG: Client disconnected for session {chat_session_id}, finishing in background.")
            except Exception as e:
                print(f"Error in stream: {e}")
                full_answer += f"\n\n⚠️ [FEHLER IM STREAM: {str(e)}]"

            # --- POST-PROCESSING (EXTRACT ACTIONS) ---
            action_blocks = re.findall(r'<action>(.*?)</action>', full_answer, re.DOTALL | re.IGNORECASE)
            for block in action_blocks:
                try:
                    try:
                        res_data = json.loads(block)
                    except json.JSONDecodeError:
                        res_data = json.loads(block.replace('\n', '\\n').replace('\r', '\\r'))
                    
                    res_list = res_data if isinstance(res_data, list) else [res_data]
                    for res in res_list:
                        if not isinstance(res, dict): continue
                        if res.get('type') == 'homework_action':
                            action, hw_id = res.get('action'), res.get('id')
                            s_name = res.get('subject_name', '').strip()
                            s_id = get_subject_id_by_name(user_id, s_name) if s_name else None
                            if s_name and s_id is None:
                                s_id = create_subject(user_id, s_name)
                                if s_id is False: s_id = get_subject_id_by_name(user_id, s_name)
                            iso_due_date = convert_to_iso_date(res.get('due_date'))
                            
                            if action == 'create':
                                create_homework(user_id, res.get('title'), iso_due_date, res.get('notes'), s_id)
                                homework_results.append(f"'{res.get('title')}' erstellt")
                            elif action == 'update' and hw_id:
                                update_homework(hw_id, user_id, res.get('title'), iso_due_date, res.get('notes'), s_id)
                                homework_results.append(f"'{res.get('title')}' aktualisiert")
                            elif action == 'toggle' and hw_id:
                                toggle_homework_status(hw_id, user_id)
                            elif action == 'delete' and hw_id:
                                delete_homework(hw_id)
                        elif res.get('type') == 'worksheet_creation':
                             md_content = res.get('content')
                        elif res.get('type') == 'memory_action':
                            content, act = res.get('content'), res.get('action', 'add')
                            if content:
                                if act == 'add': add_memory(user_id, content)
                                elif act == 'delete': delete_memory_by_content(user_id, content)
                        elif res.get('type') == 'set_chat_subject':
                            subject = res.get('subject')
                            if subject:
                                update_chat_session_subject(user_id, chat_session_id, subject)
                                current_chat_subject = subject
                                if not client_disconnected: yield from yield_sse(f"SESSION_SUBJECT:{subject}")
                        elif res.get('type') == 'chat_naming':
                            new_title = res.get('title')
                            if user_id and new_title:
                                rename_chat_session(user_id, chat_session_id, new_title)
                                if not client_disconnected: yield from yield_sse(f"SESSION_TITLE:{new_title}")
                except Exception: continue

            # Cleanup display text - Remove only internal markup, not regular brackets in text
            display_text = re.sub(r'<action>[\s\S]*?</?action>', ' ', full_answer, flags=re.IGNORECASE)
            # Remove "thinking"/"thoughts" tags and similar internal markup only
            display_text = re.sub(r'\[(?:thinking|thoughts|gedanken|chain-of-thought|analysis)\][\s\S]*?\[/(?:thinking|thoughts|gedanken|chain-of-thought|analysis)\]', ' ', display_text, flags=re.IGNORECASE)
            display_text = re.sub(r'\{(?:gedanken|thoughts|thinking|internal)[^}]*\}', ' ', display_text, flags=re.IGNORECASE)
            display_text = re.sub(r'</?action/?>', ' ', display_text, flags=re.IGNORECASE)
            
            # Only remove incomplete brackets/tags at end of text
            display_text = re.sub(r'<action[\s\S]*$', ' ', display_text, flags=re.IGNORECASE)
            display_text = re.sub(r'\{[^{}]*$', ' ', display_text)
            
            redundant_phrases = [
                r'Bitte hab einen Moment Geduld, während ich es generiere\.', 
                r'Bitte gib mir einen Moment, damit es vollständig generiert wird\.',
                r'Bitte hab einen Moment Geduld\.',
                r'Bitte gib mir einen Moment\.',
                r'Ich habe das Arbeitsblatt erstellt!', 
                r'Das Arbeitsblatt wird gerade erstellt\.'
            ]
            for phrase in redundant_phrases: 
                display_text = re.sub(phrase, '', display_text, flags=re.IGNORECASE)
            
            # Clean up whitespace
            display_text = re.sub(r'\s+', ' ', display_text).strip()

            # --- SOFORTIGES SPEICHERN DER ANTWORT ---
            assistant_msg_id = None
            if display_text or md_content:
                initial_ws = 'PENDING' if md_content else None
                assistant_msg_id = save_chat_message(db_user_id, chat_session_id, 'assistant', display_text, worksheet_filename=initial_ws, chat_subject=current_chat_subject)
                print(f"DEBUG: Message saved to DB for session {chat_session_id}")

            # --- WORKSHEET GENERATION ---
            pdf_basename = None
            if md_content:
                has_context = has_request_context()
                if has_context and not client_disconnected: yield from yield_sse("START_WORKSHEET_GENERATION")
                
                worksheet_uuid = str(uuid.uuid4())
                md_filename, pdf_filename = f"sheets/{worksheet_uuid}.md", f"sheets/{worksheet_uuid}.pdf"
                with open(md_filename, "w", encoding='utf-8') as f: f.write(md_content.strip())
                
                try:
                    response = requests.post('https://api.md-to-pdf.l-ai.pro', data={'markdown': md_content.strip()}, timeout=30)
                    response.raise_for_status()
                    with open(pdf_filename, 'wb') as f: f.write(response.content)
                    pdf_basename = os.path.basename(pdf_filename)
                except Exception as e:
                    print(f"PDF generation failed: {e}")
                    if has_context and not client_disconnected: yield from yield_sse("Fehler bei der PDF-Erstellung.")
                    if os.path.exists(md_filename): pdf_basename = os.path.basename(md_filename)

                if assistant_msg_id and pdf_basename:
                    update_chat_message_worksheet(assistant_msg_id, pdf_basename)

            if not client_disconnected:
                if homework_results: yield from yield_sse("HOMEWORK_UPDATED")
                if pdf_basename: yield from yield_sse(f"WORKSHEET_DOWNLOAD_LINK:{pdf_basename}")

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            traceback.print_exc()
            error_msg = f"❌ Ein unerwarteter Fehler ist aufgetreten: {str(e)}"
            save_chat_message(db_user_id, chat_session_id, 'assistant', error_msg, chat_subject=current_chat_subject)
            if not client_disconnected: yield from yield_sse(error_msg)
        finally:
            if chat_session_id in generating_sessions:
                generating_sessions[chat_session_id] -= 1
                if generating_sessions[chat_session_id] <= 0:
                    generating_sessions.pop(chat_session_id, None)

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/check-chat-status')
def check_chat_status():
    session_id = request.args.get('session_id')
    if not session_id:
        session_id = session.get('chat_session_id')
    
    # treat any positive counter as generating
    is_generating = generating_sessions.get(session_id, 0) > 0
    return jsonify({'generating': is_generating})

@app.route('/get-user-chat-sessions')
def get_user_chat_sessions_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    
    user_id = session['user_id']
    sessions = get_user_chat_sessions(user_id)
    return jsonify(sessions)

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

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('legal/privacy_policy_page.html')

@app.route('/impressum')
def impressum():
    return render_template('legal/impressum_page.html')

@app.route('/agb')
def agb():
    return render_template('legal/agb_page.html')

@app.route('/get-chat-history', methods=['GET'])
def get_current_chat_history():
    user_id = session.get('user_id', 0)
    chat_session_id = session.get('chat_session_id')

    if not chat_session_id:
        return jsonify({'chat_history': []})

    chat_history = get_chat_history(user_id, chat_session_id)
    return jsonify({'chat_history': chat_history})

@app.route('/api/check-worksheet-status')
def check_worksheet_status():
    user_id = session.get('user_id', 0)
    chat_session_id = session.get('chat_session_id')
    
    if not chat_session_id:
        return jsonify({'generating': False})
    
    history = get_chat_history(user_id, chat_session_id)
    is_generating = any(msg.get('worksheet_filename') == 'PENDING' for msg in history)
    
    return jsonify({'generating': is_generating})

@app.route('/download-worksheet/<filename>')
def download_sheet(filename):
    try:
        # Sanitize filename to prevent directory traversal
        filename = os.path.basename(filename)
        return send_file(os.path.join('sheets', filename), as_attachment=True)
    except Exception as e:
        print(f"Error sending file: {e}")
        return abort(404)

@app.route('/preview-worksheet/<filename>')
def preview_worksheet(filename):
    """Dient das Arbeitsblatt inline zur Vorschau (immer MD gerendert als HTML, falls verfügbar)"""
    try:
        import markdown as md
        # Filename validieren um Directory-Traversal zu verhindern
        filename = os.path.basename(filename)
        
        # Basis-Name ohne Endung ermitteln
        base_name = os.path.splitext(filename)[0]
        md_filename = f"{base_name}.md"
        md_path = os.path.join('sheets', md_filename)
        
        # Wenn MD-Version existiert, diese rendern und anzeigen
        if os.path.exists(md_path):
            with open(md_path, 'r', encoding='utf-8') as f:
                markdown_inhalt = f.read()
            
            html_inhalt = md.markdown(markdown_inhalt, extensions=['tables', 'fenced_code'])
            
            # Stylische CSS-Klassen für ein besseres Aussehen im Preview
            html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{ 
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; 
    line-height: 1.6;
    color: #374151;
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem 1rem;
    background-color: #f9fafb;
}}
.preview-container {{
    background-color: white;
    padding: 2.5rem;
    border-radius: 1rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    border: 1px solid #e5e7eb;
}}
h1 {{ font-size: 2.25rem; font-weight: 800; color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; margin-top: 0; }}
h2 {{ font-size: 1.5rem; font-weight: 700; color: #1f2937; margin-top: 2rem; }}
h3 {{ font-size: 1.25rem; font-weight: 600; color: #374151; }}
p {{ margin-bottom: 1.25rem; }}
code {{ background-color: #f3f4f6; color: #ef4444; padding: 0.2rem 0.4rem; border-radius: 0.25rem; font-size: 0.875em; }}
pre {{ background-color: #1f2937; color: #f9fafb; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; }}
pre code {{ background-color: transparent; color: inherit; padding: 0; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; }}
th {{ background-color: #f3f4f6; font-weight: 600; text-align: left; }}
th, td {{ padding: 0.75rem; border: 1px solid #e5e7eb; }}
img {{ max-width: 100%; height: auto; border-radius: 0.5rem; }}
hr {{ border: 0; border-top: 1px solid #e5e7eb; margin: 2rem 0; }}
blockquote {{ border-left: 4px solid #3b82f6; padding-left: 1rem; font-style: italic; color: #4b5563; margin: 1.5rem 0; }}
</style>
</head>
<body>
    <div class="preview-container">
        {html_inhalt}
    </div>
</body>
</html>'''
            return Response(html, mimetype='text/html; charset=utf-8')
        
        # Falls MD nicht existiert, aber es eine PDF ist, diese als Fallback anzeigen
        dateiendung = os.path.splitext(filename)[1].lower()
        if dateiendung == '.pdf':
            pdf_path = os.path.join('sheets', filename)
            if os.path.exists(pdf_path):
                return send_file(pdf_path, mimetype='application/pdf')
        
        return abort(404)
    except Exception as e:
        print(f"Fehler beim Anzeigen der Vorschau: {e}")
        return abort(404)

@app.route('/')
def index():
    user_id = session.get('user_id')
    user_type = session.get('user_type', 'student') if user_id else 'guest'

    if user_type == 'it-admin':
        return redirect(url_for('admin_dashboard'))

    # Create new chat session
    if user_id:
        # For logged-in users, preserve session
        if 'chat_session_id' not in session:
            session['chat_session_id'] = str(uuid.uuid4())
    else:
        # For guests, always create a new session (no persistence on refresh)
        session['chat_session_id'] = str(uuid.uuid4())
    
    # Cleanup old completed homework (24h) if logged in
    if user_id:
        delete_old_completed_homework(user_id)

    # Get user's chat sessions (user_id=0 for guests)
    db_user_id = user_id if user_id else 0
    user_sessions = get_user_chat_sessions(db_user_id)

    # Get assignments
    assignments = []
    class_name = session.get('class_name')
    if user_id and class_name:
        assignments = get_assignments_for_class(class_name, session.get('school'))

    # Get homework
    homework = get_homework_for_user(user_id) if user_id else []

    # First login check
    is_first_login = False
    if user_id:
        is_first_login = get_first_login_status(user_id)
        if is_first_login:
            set_first_login_status(user_id, 0)

    return render_template('index.html',
                         user_type=user_type,
                         is_guest=not user_id,
                         username=session.get('username', 'Gast'),
                         class_name=class_name,
                         chat_sessions=user_sessions,
                         current_session_id=session.get('chat_session_id'),
                         assignments=assignments,
                         homework=homework,
                         is_first_login=is_first_login)

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

@app.route('/create-assignment', methods=['GET', 'POST'])
def create_assignment_route():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('user_type') != 'teacher':
        return redirect(url_for('index'))

    if not session.get('class_name'):
        return render_template('message.html', title='Fehler', message='Sie sind keiner Klasse zugewiesen.')

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        
        if not title or not description:
            return render_template('create_assignment.html', error='Titel und Beschreibung sind erforderlich.')

        user_id = session['user_id']
        class_name = session['class_name']
        school = session['school']

        create_assignment(title, description, user_id, class_name, school)
        return redirect(url_for('index'))

    return render_template('create_assignment.html')

@app.route('/view-assignment/<assignment_id>', methods=['GET', 'POST'])
def view_assignment(assignment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_type = session['user_type']
    assignment = get_assignment(assignment_id)

    if not assignment:
        return redirect(url_for('index'))

    # Check permissions (optional but good practice: ensure user belongs to same school/class)
    # For now relying on list filtering in index logic, but strict check could be added here.

    submission = None
    submissions = []

    if user_type == 'student':
        if request.method == 'POST':
            content = request.form.get('submission_content')
            if content:
                create_submission(assignment_id, user_id, content)
                return redirect(url_for('view_assignment', assignment_id=assignment_id))
        
        submission = get_submission_for_user(assignment_id, user_id)
    
    elif user_type == 'teacher':
        submissions = get_submissions_for_assignment(assignment_id)

    return render_template('view_assignment.html', 
                         assignment=assignment, 
                         user_type=user_type,
                         submission=submission,
                         submissions=submissions)

@app.route('/delete-assignment/<assignment_id>', methods=['POST'])
def delete_assignment_route(assignment_id):
    if 'user_id' not in session or session.get('user_type') != 'teacher':
        return jsonify({'error': 'Nicht autorisiert'}), 401
    
    delete_assignment(assignment_id)
    return jsonify({'success': True})

@app.route('/create-homework', methods=['GET', 'POST'])
def create_homework_route():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        title = request.form.get('title')
        due_date = request.form.get('due_date')
        notes = request.form.get('notes')
        subject_id = request.form.get('subject_id')

        if not title:
            return render_template('create_homework.html', error='Titel ist erforderlich.', subjects=get_subjects(user_id))
        
        # Convert empty string to None for subject_id
        if subject_id == '':
            subject_id = None

        create_homework(user_id, title, due_date, notes, subject_id)
        return redirect(url_for('index'))

    return render_template('create_homework.html', subjects=get_subjects(user_id))

@app.route('/view-homework/<homework_id>')
def view_homework(homework_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    homework = get_single_homework(homework_id)
    if not homework:
        return redirect(url_for('index'))

    return render_template('view_homework.html', homework=homework)

@app.route('/calendar')
def calendar_route():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # We reuse get_homework_for_user to get all homework with due dates
    homework = get_homework_for_user(session['user_id'])
    
    return render_template('calendar.html', homework=homework)

@app.route('/edit-homework/<homework_id>', methods=['GET', 'POST'])
def edit_homework_route(homework_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    homework = get_single_homework(homework_id)

    if not homework or homework['user_id'] != user_id:
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title')
        due_date = request.form.get('due_date')
        notes = request.form.get('notes')
        subject_id = request.form.get('subject_id')

        if not title:
            return render_template('edit_homework.html', homework=homework, subjects=get_subjects(user_id), error='Titel ist erforderlich.')
        
        if subject_id == '':
            subject_id = None

        update_homework(homework_id, user_id, title, due_date, notes, subject_id)
        return redirect(url_for('view_homework', homework_id=homework_id))

    return render_template('edit_homework.html', homework=homework, subjects=get_subjects(user_id))

@app.route('/toggle-homework/<homework_id>', methods=['POST'])
def toggle_homework_route(homework_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    
    toggle_homework_status(homework_id, session['user_id'])
    return jsonify({'success': True})

@app.route('/delete-homework/<homework_id>', methods=['POST'])
def toggle_homework_status_route(homework_id):
    # This was a duplicate or misnamed route in previous version, fixing to delete
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    
    delete_homework(homework_id)
    return jsonify({'success': True})

@app.route('/create-subject', methods=['POST'])
def create_subject_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    
    name = request.json.get('name')
    if not name:
        return jsonify({'error': 'Name ist erforderlich'}), 400
        
    subject_id = create_subject(session['user_id'], name)
    if subject_id:
        return jsonify({'success': True, 'subject_id': subject_id, 'name': name})
    else:
        return jsonify({'error': 'Fach existiert bereits'}), 400

@app.route('/delete-subject/<subject_id>', methods=['POST'])
def delete_subject_route(subject_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
        
    if delete_subject(subject_id, session['user_id']):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Fehler beim Löschen'}), 500



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

@app.route('/api/memories', methods=['GET'])
def get_user_memories_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    
    memories = get_memories(session['user_id'])
    return jsonify({'memories': memories})

@app.route('/api/memories', methods=['POST'])
def add_user_memory_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    
    data = request.get_json()
    content = data.get('content')
    
    if not content:
        return jsonify({'error': 'Inhalt ist erforderlich'}), 400
        
    if add_memory(session['user_id'], content):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Fehler beim Speichern oder Duplikat'}), 500

@app.route('/api/memories/<int:memory_id>', methods=['DELETE'])
def delete_user_memory_route(memory_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    
    if delete_memory(memory_id, session['user_id']):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Fehler beim Löschen'}), 500

@app.route('/api/settings/math-solver', methods=['GET'])
def get_math_solver_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    
    status = get_math_solver_status(session['user_id'])
    return jsonify({'enabled': status})

@app.route('/api/settings/math-solver', methods=['POST'])
def set_math_solver_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    
    data = request.get_json()
    enabled = data.get('enabled', False)
    
    if set_math_solver_status(session['user_id'], enabled):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Fehler beim Speichern'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
