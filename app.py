import subprocess
import os
import io
import base64
import uuid
import json
import re
import traceback
import threading
import time as time_module
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, Response, abort, current_app, has_request_context
import requests
import firebase_admin
from firebase_admin import credentials as fb_credentials, messaging as fb_messaging
from dotenv import load_dotenv
from openai import OpenAI
from database import (
    init_database,
    create_assignment, get_assignments_for_class, get_assignment, delete_assignment,
    create_submission, get_submissions_for_assignment, get_submission_for_user,
)
import user_storage as us

load_dotenv()

# Initialize Firebase Admin SDK for FCM
_fb_key = os.path.join(os.path.dirname(__file__), "firebase-service-account.json")
if os.path.exists(_fb_key):
    firebase_admin.initialize_app(fb_credentials.Certificate(_fb_key))
else:
    print("[FCM] Warning: firebase-service-account.json not found, FCM disabled")

# Migrate existing SQLite data to file-based storage (runs once)
us.migrate_from_sqlite()

# Global tracking for active generation sessions
# track active streaming responses per chat session.  
# we store a simple counter so that overlapping requests in the
# same session don't clear the flag prematurely.  
# key: chat_session_id, value: number of active generators
# (previously this was a boolean which could get stuck and prevented
# further worksheet requests in the same chat).

generating_sessions = {}

# Brute-force protection: IP -> (attempts, last_attempt_time)
login_attempts = {}

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")

@app.context_processor
def inject_csrf_token():
    return {'csrf_token': generate_csrf_token()}

def check_password_strength(password):
    """Check if password meets requirements: min 8 chars, uppercase, lowercase, digit, special char."""
    if len(password) < 8:
        return False, "Passwort muss mindestens 8 Zeichen lang sein."
    if not re.search(r'[A-Z]', password):
        return False, "Passwort muss mindestens einen Großbuchstaben enthalten."
    if not re.search(r'[a-z]', password):
        return False, "Passwort muss mindestens einen Kleinbuchstaben enthalten."
    if not re.search(r'\d', password):
        return False, "Passwort muss mindestens eine Zahl enthalten."
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Passwort muss mindestens ein Sonderzeichen enthalten."
    return True, ""

def get_client_ip():
    """Get client IP address."""
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ.get('HTTP_X_FORWARDED_FOR').split(', ')[0]
    return request.environ.get('REMOTE_ADDR')

def generate_csrf_token():
    """Generate a CSRF token for the session."""
    if 'csrf_token' not in session:
        session['csrf_token'] = str(uuid.uuid4())
    return session['csrf_token']

def validate_csrf_token(token):
    """Validate the CSRF token."""
    return token and token == session.get('csrf_token')

def require_csrf(f):
    """Decorator to require CSRF token for POST requests."""
    def wrapper(*args, **kwargs):
        if request.method == 'POST':
            token = request.form.get('csrf_token')
            if not validate_csrf_token(token):
                abort(403, 'Invalid CSRF token')
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def convert_to_iso_date(date_str):
    """Get client IP address."""
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ.get('HTTP_X_FORWARDED_FOR').split(', ')[0]
    return request.environ.get('REMOTE_ADDR')

def convert_to_iso_date(date_str):
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
    if 'user_id' not in session or session.get('user_type') != 'it-admin':
        return jsonify([]), 401
    schools = us.get_unique_school_names()
    return jsonify(schools)

@app.route('/api/students')
def get_students():
    if 'user_id' not in session or session.get('user_type') != 'it-admin':
        return jsonify([]), 401
    school = session.get('school')
    students = us.get_student_usernames_for_school(school)
    return jsonify(students)

@app.route('/api/classes')
def get_classes():
    if 'user_id' not in session or session.get('user_type') != 'it-admin':
        return jsonify([]), 401
    school = session.get('school')
    classes = us.get_unique_class_names_for_school(school)
    return jsonify(classes)

@app.route('/api/teachers')
def get_teachers():
    if 'user_id' not in session or session.get('user_type') != 'it-admin':
        return jsonify([]), 401
    school = session.get('school')
    teachers = us.get_teacher_usernames_for_school(school)
    return jsonify(teachers)

@app.route('/api/chat-subjects')
def api_get_chat_subjects():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    subjects = us.get_unique_chat_subjects(session['user_id'])
    return jsonify(subjects)

@app.route('/api/chat-sessions-by-subject')
def api_get_chat_sessions_by_subject():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    subject = request.args.get('subject')
    if not subject:
        return jsonify({'error': 'Betreff ist erforderlich'}), 400
    sessions = us.get_chat_sessions_by_subject(session['user_id'], subject)
    return jsonify(sessions)

@app.route('/api/ntfy-topic')
def get_ntfy_topic_route():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'topic': None})
    return jsonify({'topic': get_user_ntfy_topic(user_id), 'global': NTFY_GLOBAL_CHANNEL})


@app.route('/api/fcm-token', methods=['POST'])
def register_fcm_token():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False}), 401
    data = request.get_json(silent=True) or {}
    token = data.get('token', '').strip()
    if token:
        us.set_fcm_token(user_id, token)
    return jsonify({'ok': True})


# Initialize databases
init_database()
us._ensure_users_dir()

# Ensure sheets directory exists
if not os.path.exists('sheets'):
    os.makedirs('sheets')

# Ensure uploads directory exists
if not os.path.exists('uploads'):
    os.makedirs('uploads')

BASE_URL = os.getenv("BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "google/gemma-3-27b-it:free")
API_KEY = os.getenv("API_KEY")
RATING_IN_MAIN_PAGE = os.getenv("RATING_IN_MAIN_PAGE", "true").lower() not in ("false", "0", "no")


client = OpenAI(
    base_url = BASE_URL if BASE_URL else "https://openrouter.ai/api/v1",
    api_key=API_KEY
)

system_prompt = os.getenv("SYSTEM_PROMPT")

ip_ban_list = os.getenv("IP_BAN_LIST", "").split(",")

NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.malte-hinrichs.de")
NTFY_GLOBAL_CHANNEL = "Learn-AI-Notifications"


def get_user_ntfy_topic(user_id: str) -> str:
    return f"Learn-AI-{user_id[:8]}"


def send_fcm_notification(user_id: str, title: str, body: str):
    """Send FCM push notification to a user's registered device (non-blocking)."""
    def _send():
        try:
            token = us.get_fcm_token(user_id)
            if not token:
                return
            msg = fb_messaging.Message(
                notification=fb_messaging.Notification(title=title, body=body),
                token=token,
            )
            fb_messaging.send(msg)
        except Exception as e:
            print(f"[FCM] Notification failed for {user_id}: {e}")
    threading.Thread(target=_send, daemon=True).start()


def send_ntfy_notification(topic: str, title: str, message: str, tags: list = None, priority: str = "default"):
    """Send a push notification via ntfy server (non-blocking, fire-and-forget)."""
    def _send():
        try:
            payload = {"topic": topic, "title": title, "message": message, "priority": 3}
            if tags:
                payload["tags"] = tags
            if priority == "high":
                payload["priority"] = 4
            elif priority == "urgent":
                payload["priority"] = 5
            requests.post(NTFY_SERVER, json=payload, timeout=5)
        except Exception as e:
            print(f"[ntfy] Notification failed ({topic}): {e}")
    threading.Thread(target=_send, daemon=True).start()


def _homework_reminder_loop():
    """Background thread: sends ntfy reminders for homework due in 1 or 2 days (once per day)."""
    sent_today: dict = {}
    while True:
        try:
            today_str = datetime.now().strftime('%Y-%m-%d')
            if today_str not in sent_today:
                sent_today = {today_str: set()}

            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            day_after = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')

            for user_id in us.get_all_user_ids():
                for hw in us.get_homework_for_user(user_id):
                    if hw.get('completed'):
                        continue
                    due = hw.get('due_date', '')
                    key = (user_id, hw.get('id', ''))
                    if due in (tomorrow, day_after) and key not in sent_today[today_str]:
                        day_word = "morgen" if due == tomorrow else "in 2 Tagen"
                        _t = f"Hausaufgabe {day_word} fällig!"
                        _b = f"'{hw.get('title', 'Hausaufgabe')}' ist {day_word} fällig."
                        send_ntfy_notification(
                            get_user_ntfy_topic(user_id), _t, _b,
                            tags=["alarm_clock"], priority="high"
                        )
                        send_fcm_notification(user_id, _t, _b)
                        sent_today[today_str].add(key)
        except Exception as e:
            print(f"[ntfy] Homework reminder error: {e}")
        time_module.sleep(3600)  # check every hour


threading.Thread(target=_homework_reminder_loop, daemon=True).start()


@app.before_request
def block_method():
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        ip = request.environ.get('HTTP_X_FORWARDED_FOR').split(', ')[0]
    else:
        ip = request.environ.get('REMOTE_ADDR')
    print(ip)
    if ip in ip_ban_list:
        abort(403)
    if request.args.get('android_app', '').lower() == 'true':
        session['android_app'] = True
@app.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html', csrf_token=generate_csrf_token())

@app.route('/login', methods=['POST'])
@require_csrf
def login_post():
    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''

    if not username or not password:
        return render_template('login.html', error='Alle Felder sind erforderlich.')

    if len(username) > 32 or len(password) > 128:
        return render_template('login.html', error='Ungültige Eingabe.')

    if not re.match(r'^[A-Za-z0-9_.-]+$', username):
        return render_template('login.html', error='Benutzername darf nur alphanumerische Zeichen, Punkt, Unterstrich und Bindestrich enthalten.')

    # Brute-force protection
    ip = get_client_ip()
    now = time_module.time()
    if ip in login_attempts:
        attempts, last_time = login_attempts[ip]
        if now - last_time > 3600:  # Reset after 1 hour
            attempts = 0
        if attempts >= 5:
            return render_template('login.html', error='Zu viele fehlgeschlagene Anmeldungen. Versuche es später erneut.')
        login_attempts[ip] = (attempts + 1, now)
    else:
        login_attempts[ip] = (1, now)

    user = us.get_user(username, password)
    if user:
        # Reset attempts on success
        if ip in login_attempts:
            del login_attempts[ip]
        session['user_id'] = user['uuid']
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
    return render_template('register.html', csrf_token=generate_csrf_token())

@app.route('/register', methods=['POST'])
@require_csrf
def register_post():
    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''
    password_confirm = request.form.get('password_confirm') or ''
    user_type = (request.form.get('user_type') or '').strip()
    school = (request.form.get('school') or '').strip()
    agb_accept = request.form.get('agb_accept')
    privacy_accept = request.form.get('privacy_accept')

    if user_type not in ['student', 'teacher']:
        return render_template('register.html', error='Ungültiger Benutzertyp.')

    if not username or not password or not password_confirm or not user_type or not school:
        return render_template('register.html', error='Alle Felder sind erforderlich.')

    if not agb_accept or not privacy_accept:
        return render_template('register.html', error='Du musst die Nutzungsbedingungen und die Datenschutzerklärung akzeptieren.')

    if password != password_confirm:
        return render_template('register.html', error='Die Passwörter stimmen nicht überein.')

    if len(username) > 32 or len(password) < 8 or len(password) > 128 or len(school) > 64:
        return render_template('register.html', error='Ungültige Eingabe-Länge.')

    # Password strength check
    is_strong, strength_error = check_password_strength(password)
    if not is_strong:
        return render_template('register.html', error=strength_error)

    if not re.match(r'^[A-Za-z0-9_.-]+$', username):
        return render_template('register.html', error='Benutzername darf nur alphanumerische Zeichen, Punkt, Unterstrich und Bindestrich enthalten.')

    if '..' in username or '/' in username or '\\' in username:
        return render_template('register.html', error='Ungültiger Benutzername.')

    school = re.sub(r'[^A-Za-z0-9\s\-\_\.\,]', '', school)

    if not us.create_user(username, password, user_type, school):
        if user_type == 'it-admin':
            return render_template('register.html', error='Ein IT-Admin für diese Schule existiert bereits.')
        else:
            return render_template('register.html', error='Benutzername bereits vergeben.')

    # Automatically log in the user after registration
    user = us.get_user_by_username(username)
    if user:
        session['user_id'] = user['uuid']
        session['username'] = user['username']
        session['user_type'] = user['user_type']
        session['class_name'] = user['class_name']
        session['school'] = user['school']
        return redirect(url_for('index'))
    else:
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/delete-chat/<session_id>', methods=['POST'])
def delete_chat_route(session_id):
    user_id = session.get('user_id')
    
    # Try deleting from user's sessions if logged in
    if user_id:
        us.delete_chat_session(user_id, session_id)
    
    # Also try deleting as guest (in case it was a guest session)
    us.delete_chat_session(f"guest_{session_id}", session_id)

    if session.get('chat_session_id') == session_id:
        session.pop('chat_session_id', None)

    return jsonify({'success': True})

@app.route('/rename-chat/<session_id>', methods=['POST'])
def rename_chat_route(session_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401

    data = request.get_json()
    new_name = data.get('new_name')

    if not new_name:
        return jsonify({'error': 'Neuer Name ist erforderlich'}), 400

    if us.rename_chat_session(session['user_id'], session_id, new_name):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Fehler beim Umbenennen des Chats'}), 500

@app.route('/new-chat', methods=['POST'])
def new_chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401

    new_session_id = str(uuid.uuid4())
    session['chat_session_id'] = new_session_id

    # Clear cached image
    filename = session.pop('cached_image_filename', None)
    if filename:
        try:
            os.remove(os.path.join('uploads', filename))
        except OSError as e:
            print(f"Error deleting cached image: {e}")

    # Create session in DB with a welcome message
    welcome_content = "Hi! Ich bin dein persönlicher Lernassistent. Sprich mit mir oder schreibe mir deine Fragen! Ich werde dir nie die Lösung verraten, sondern dir helfen sie selbst herauszufinden."
    us.save_chat_message(session['user_id'], new_session_id, 'assistant', welcome_content)

    return jsonify({'session_id': new_session_id, 'welcome_message': welcome_content})
@app.route('/ask')
def ask():
    user_id = session.get('user_id')
    android_app_flag = session.get('android_app', False)
    question = request.args.get('question', '')

    chat_session_id = session.get('chat_session_id')
    if chat_session_id:
        generating_sessions.pop(chat_session_id, None)

    cached_filenames = session.get('cached_image_filenames', [])
    images_to_process = []

    for filename in cached_filenames:
        try:
            image_path = os.path.join('uploads', filename)
            with open(image_path, "rb") as f:
                image_data = f.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
            mime_type = 'image/' + os.path.splitext(filename)[1][1:]
            images_to_process.append({
                'base64': base64_image,
                'mime_type': mime_type,
                'filename': filename
            })
        except Exception as e:
            print(f"Error reading cached image {filename}: {e}")
    
    # Clear cache after reading
    session.pop('cached_image_filenames', None)

    if not question and not images_to_process:
        return jsonify({'answer': 'Bitte stellen Sie eine Frage oder hängen Sie ein Bild an.'}), 400

    if not chat_session_id:
        chat_session_id = str(uuid.uuid4())
        session['chat_session_id'] = chat_session_id

    # Save user message with all images
    # We combine them into a list of data URLs for storage
    img_data_list = [f"data:{img['mime_type']};base64,{img['base64']}" for img in images_to_process]

    # Use guest_session_id as user_id for guests to persist history
    effective_user_id = user_id if user_id else f"guest_{chat_session_id}"

    # Pass list of images to storage (storage needs to handle list or we join them)
    # Since storage currently expects one 'image_data', we'll pass the first one for now or modify storage.
    # Actually, let's pass the first one for compatibility or join them if storage allows.
    # I will modify storage in the next step to support a list.
    us.save_chat_message(effective_user_id, chat_session_id, 'user', question, image_data=img_data_list)

    calendar_intent_keywords = [
        'kalender',
        'eintragen',
        'trage',
        'trag',
        'homework',
        'hausaufgabe',
        'hausaufgaben',
        'faellig',
        'fällig'
    ]
    calendar_entry_intent = user_id and any(keyword in question.lower() for keyword in calendar_intent_keywords)
    delete_intent_keywords = ['loesch', 'lösch', 'delete', 'entfern']
    bulk_delete_intent = user_id and 'alle' in question.lower() and any(keyword in question.lower() for keyword in delete_intent_keywords)
    homework_intent_keywords = [
        'kalender',
        'hausaufgabe',
        'hausaufgaben',
        'homework',
        'faellig',
        'fällig',
        'bearbeite',
        'bearbeiten',
        'eintragen',
        'lösche',
        'loesche',
        'ändern',
        'aendern',
        'verschieben',
        'erledigt'
    ]
    homework_ui_intent = user_id and any(keyword in question.lower() for keyword in homework_intent_keywords)

    # Get existing chat history and other context
    existing_chat_history = us.get_chat_history(effective_user_id, chat_session_id)
    
    if user_id:
        current_chat_subject = existing_chat_history[0].get('chat_subject') if existing_chat_history else None
        earlier_chat_summaries = us.get_all_previous_chats_summaries(user_id, exclude_session_id=chat_session_id)
        current_homework = us.get_homework_for_user(user_id)[:15]
        current_subjects = us.get_subjects(user_id)
        user_memories = us.get_memories(user_id)
        memories_text = "\n".join([f"- {m['content']}" for m in user_memories])
        math_solver_enabled = us.get_math_solver_status(user_id)
    else:
        current_chat_subject = existing_chat_history[0].get('chat_subject') if existing_chat_history else None
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
        homework_action_processed = False
        homework_link_id = None
        homework_saving_announced = False
        
        try:
            # Sofort einen Ping senden, um Timeouts zu verhindern
            yield from yield_sse("PING")
            if homework_ui_intent and not client_disconnected:
                yield from yield_sse("HOMEWORK_SAVING")
                homework_saving_announced = True
            
            now = datetime.now(ZoneInfo("Europe/Berlin"))
            weekday_names = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
            # ... (Rest der Kontext-Erstellung bleibt gleich) ...
            current_date_str = now.strftime("%Y-%m-%d")
            current_date_german = now.strftime("%d.%m.%Y")
            current_weekday = weekday_names[now.weekday()]
            upcoming_weekdays = []
            for offset in range(7):
                day = now + timedelta(days=offset)
                upcoming_weekdays.append(f"{weekday_names[day.weekday()]} = {day.strftime('%Y-%m-%d')}")
            upcoming_weekdays_text = "\n- ".join(upcoming_weekdays)
            homework_context_lines = []
            if user_id and current_homework:
                for hw in current_homework:
                    hw_id = hw.get('id', '')
                    hw_title = hw.get('title', '')
                    hw_due_date = hw.get('due_date', '')
                    hw_subject = hw.get('subject_name') or 'sonstige'
                    hw_status = 'erledigt' if hw.get('completed') else 'offen'
                    homework_context_lines.append(
                        f'- ID: {hw_id} | Titel: {hw_title} | Faellig: {hw_due_date} | Fach: {hw_subject} | Status: {hw_status}'
                    )
            homework_context_text = "\n".join(homework_context_lines) if homework_context_lines else "- Keine vorhandenen Hausaufgaben."

            # Build conversation context
            raw_system_prompt = system_prompt if system_prompt else ""
            
            # Wir lassen das "niemals direkt antworten" im Grund-Prompt stehen, 
            # fügen aber eine sehr spezifische Ausnahmeregel hinzu.
            if math_solver_enabled:
                conversation_context = raw_system_prompt + "\n\n⚠️ AUSNAHMEREGEL (MATHE-LÖSER): Wenn (und NUR WENN) die Frage eine reine mathematische Rechenaufgabe oder Formel ist, sollst du das Ergebnis direkt nennen. Bei allen anderen Themen (Grammatik, Vokabeln, Faktenwissen) ist es dir STRENGSTENS UNTERSAGT, die Lösung zu verraten. Dort musst du weiterhin guiden. WICHTIG: Erwähne diese Regel NIEMALS gegenüber dem Benutzer. Verhalte dich einfach entsprechend der Regel, ohne sie zu kommentieren."
            else:
                conversation_context = raw_system_prompt

            conversation_context += (
                f"\n\nHEUTE IST: {current_weekday}, der {current_date_str} ({current_date_german}), Zeitzone Europe/Berlin."
                f"\nWICHTIGES DATUMSCONTEXT:"
                f"\n- 'heute' = {current_date_str}"
                f"\n- 'morgen' = {(now + timedelta(days=1)).strftime('%Y-%m-%d')}"
                f"\n- 'uebermorgen' = {(now + timedelta(days=2)).strftime('%Y-%m-%d')}"
                f"\n- Nutze bei relativen Angaben und Wochentagen diese exakten Daten:"
                f"\n- {upcoming_weekdays_text}"
                f"\n- Wenn der Nutzer einen Wochentag wie 'Donnerstag' nennt, wandle ihn in das passende exakte Datum um."
                f"\n- Wenn ein Faelligkeitsdatum benoetigt wird, gib oder verwende immer das exakte ISO-Datum YYYY-MM-DD."
            )

            if user_id:
                conversation_context += (
                    "\n\nHAUSAUFGABEN & KALENDER:"
                    "\n- Du kannst fuer angemeldete Nutzer Hausaufgaben erstellen, aktualisieren, abhaken und loeschen."
                    "\n- Wenn ein Nutzer sagt, dass etwas in den Kalender eingetragen werden soll, lege dafuer eine Hausaufgabe mit passendem Faelligkeitsdatum an oder aktualisiere eine bestehende."
                    "\n- Hausaufgaben erscheinen im Kalenderbereich der App automatisch. Es gibt keinen separaten Kalender-Eintragstyp."
                    "\n- Wenn es fuer die Kalender-Eintragung an Titel oder Datum fehlt, frage gezielt kurz danach."
                    "\n- WICHTIG: Eine Hausaufgabe gilt NUR dann als wirklich eingetragen, wenn du am ENDE deiner Antwort ein Action-Tag im EXAKTEN Format mitsendest."
                    "\n- EXAKTES FORMAT zum Erstellen: <action>{\"type\":\"homework_action\",\"action\":\"create\",\"title\":\"Titel\",\"due_date\":\"YYYY-MM-DD\",\"notes\":\"Notizen oder leer\",\"subject_name\":\"Fach oder sonstige\"}</action>"
                    "\n- EXAKTES FORMAT zum Aktualisieren: <action>{\"type\":\"homework_action\",\"action\":\"update\",\"id\":\"bestehende-id\",\"title\":\"Titel\",\"due_date\":\"YYYY-MM-DD\",\"notes\":\"Notizen oder leer\",\"subject_name\":\"Fach oder sonstige\"}</action>"
                    "\n- EXAKTES FORMAT zum Loeschen: <action>{\"type\":\"homework_action\",\"action\":\"delete\",\"id\":\"bestehende-id\"}</action>"
                    "\n- EXAKTES FORMAT zum Abhaken oder Wieder-Oeffnen: <action>{\"type\":\"homework_action\",\"action\":\"toggle\",\"id\":\"bestehende-id\"}</action>"
                    "\n- Sage NIEMALS, dass etwas eingetragen oder gespeichert wurde, wenn du kein solches <action>...</action>-Tag mitgeschickt hast."
                    "\n- Wenn der Nutzer etwas bearbeiten, verschieben, umbenennen, loeschen, abhaken oder wieder oeffnen will, verwende die ID aus der Liste vorhandener Hausaufgaben."
                    "\n- Wenn der Nutzer sagt 'loesche alle', 'mach alle weg' oder eindeutig mehrere passende Hausaufgaben meint, sende mehrere delete-Aktionen in einem JSON-Array innerhalb eines einzigen <action>...</action>-Tags."
                    "\n- Falls keine eindeutige passende Hausaufgabe erkennbar ist, frage kurz nach statt zu raten."
                    f"\n- VORHANDENE HAUSAUFGABEN:\n{homework_context_text}"
                )
                if calendar_entry_intent:
                    conversation_context += (
                        "\n- HOECHSTE PRIORITAET FUER DIESE ANFRAGE: Der Nutzer moechte einen Kalender-/Hausaufgaben-Eintrag."
                        "\n- Erzeuge dafuer KEIN Arbeitsblatt und KEINE worksheet_creation-Aktion."
                        "\n- Verwende stattdessen ausschliesslich homework_action oder stelle eine kurze Rueckfrage, falls Pflichtangaben fehlen."
                    )
                if bulk_delete_intent:
                    conversation_context += (
                        "\n- HOECHSTE PRIORITAET FUER DIESE ANFRAGE: Der Nutzer moechte mehrere Hausaufgaben auf einmal loeschen."
                        "\n- Wenn 'alle' gesagt wurde und die Liste eindeutig ist, sende fuer alle passenden Eintraege delete-Aktionen in einem einzigen JSON-Array."
                    )
            
            # --- STILLE HINTERGRUND-AKTIONEN ---
            conversation_context += "\n\nHINTERGRUND-AUFGABEN (STRENG GEHEIM):"
            conversation_context += "\n1. FACH-ZUORDNUNG: Entscheide über das Fach. Nutze UNBEDINGT eines der folgenden Fächer: Deutsch, Mathematik, Englisch, Französisch, Spanisch, Latein, Italienisch, Russisch, Türkisch, Arabisch, Chinesisch, Japanisch, Kunst, Musik, Sport, Geschichte, Politik, Sozialkunde, Gemeinschaftskunde, Geografie, Erdkunde, Wirtschaft, Arbeitslehre, Technik, Informatik, Physik, Chemie, Biologie, Ethik, Religion, Philosophie, Astronomie, Darstellendes Spiel, Theater, Medienkunde, Hauswirtschaft, Textiles Gestalten, Werken, Technik und Design, Informatik und Medienbildung, Naturwissenschaften, Gesellschaftswissenschaften, Wirtschaft und Recht, Informatik und Mathematik, Verbraucherbildung, Berufsorientierung, Förderunterricht, Lernzeit, Klassenrat, Projektunterricht, Methodentraining, Präsentationstraining, Schreibwerkstatt, Leseförderung, Medienkompetenz, Informatik-Grundlagen, Programmieren, Robotik, 3D-Druck, Elektronik, Holztechnik, Metalltechnik, Elektrotechnik, Wirtschaftslehre, Betriebswirtschaft, Rechnungswesen, Buchführung, Recht, Pädagogik, Psychologie, Soziologie, Kriminalistik, Astronomie, Umweltkunde, Ökologie, Ernährungslehre, Gesundheit, Erste Hilfe, Verkehrserziehung, Informatikpraxis, Informatik und Technik, Geologie, Meteorologie, Meereskunde, Völkerkunde, Kulturkunde, Heimat- und Sachunterricht, Sachunterricht, Natur und Technik, Naturwissenschaft und Technik, Informatik und Gesellschaft, Informatiksysteme, Datenverarbeitung, Mediengestaltung, Fotografie, Filmkunde, Chor, Orchester, Ensemble, Instrumentalunterricht, Kunstgeschichte, Musikgeschichte, Tanz, Bewegung und Spiel, Schwimmen, Leichtathletik, Turnen, Basketball, Fußball, Volleyball, Handball, Tennis, Badminton, Fechten, Judo, Hockey, Schach, Schulgarten, Gartenbau, Landwirtschaft, Hauswirtschaft und Ernährung, Kochen, Nähen, Design, Gestalten, Basteln, Holzarbeiten, Metallarbeiten, Physikalische Experimente, Chemische Experimente, Biologische Übungen, Laborpraxis, Leseclub, Schreibkurs, Debattieren, Rhetorik, Journalismus, Schülerzeitung, Wirtschaft und Finanzen, Unternehmertum, Digitale Bildung, Künstliche Intelligenz, Robotik und Coding, Medienethik, Umweltbildung, Nachhaltigkeit, Verkehr, Freizeitpädagogik, Sonderpädagogik, Lernförderung, sonstige. Falls es nicht eindeutig zugeordnet werden kann, nutze 'sonstige'. Sende UNBEDINGT am Ende deiner Nachricht: <action>{\"type\": \"set_chat_subject\", \"subject\": \"Fachname\"}</action>. Erwähne dies NIEMALS im Text."
            
            if user_id:
                current_name = us.get_session_name(user_id, chat_session_id)
                if not current_name or current_name.strip() in ['Neuer Chat', 'None', '']:
                    conversation_context += "\n2. TITEL: Gib dem Chat einen kurzen, passenden Namen (max. 30 Zeichen). Sende dazu UNBEDINGT am Ende deiner Nachricht: <action>{\"type\": \"chat_naming\", \"title\": \"Dein Titel\"}</action>"

            # Finaler Entscheidungs-Check
            if math_solver_enabled:
                 conversation_context += "\n\nENTSCHEIDUNGSMATRIX:\n- Mathe-Aufgabe? -> Lösung direkt nennen.\n- Deutsch/Sprachen/Sonstiges? -> Lösung NIEMALS nennen, nur Tipps geben (Guiding).\nWICHTIG: Handle laut Matrix, aber erwähne sie niemals gegenüber dem Benutzer!"
            else:
                 conversation_context += "\n\nENTSCHEIDUNGSMATRIX: Alle Fächer -> Nur Tipps geben (Guiding)."

            processed_history = []
            for msg in chat_history_for_gen:
                role = msg['message_type']
                if role not in ['user', 'assistant']: continue
                content = msg['content']
                img = msg.get('image_data') # Can be string or list
                
                if role == 'user' and img:
                    img_list = img if isinstance(img, list) else [img]
                    content_list = [{"type": "text", "text": content}]
                    for img_url in img_list:
                        content_list.append({"type": "image_url", "image_url": {"url": img_url}})
                    msg_obj = {"role": "user", "content": content_list}
                else:
                    msg_obj = {"role": role, "content": content}

                if not processed_history:
                    if role == 'user': processed_history.append(msg_obj)
                else:
                    if role != processed_history[-1]['role']: processed_history.append(msg_obj)
                    else: 
                        # Merge if same role
                        if isinstance(processed_history[-1]['content'], str) and isinstance(content, str):
                            processed_history[-1]['content'] += "\n" + content
                        # (Simplification: we don't merge complex contents easily, but this handles most cases)

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
                    
                    if user_id:
                        us.save_chat_message(user_id, chat_session_id, 'assistant', final_error, chat_subject=current_chat_subject)
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
                            homework_action_processed = True
                            if not homework_saving_announced and not client_disconnected:
                                yield from yield_sse("HOMEWORK_SAVING")
                                homework_saving_announced = True
                            action, hw_id = res.get('action'), res.get('id')
                            s_name = res.get('subject_name', '').strip()
                            s_id = us.get_subject_id_by_name(user_id, s_name) if s_name else None
                            if s_name and s_id is None:
                                s_id = us.create_subject(user_id, s_name)
                                if s_id is False: s_id = us.get_subject_id_by_name(user_id, s_name)
                            iso_due_date = convert_to_iso_date(res.get('due_date'))

                            if action == 'create':
                                created_hw = us.create_homework(user_id, res.get('title'), iso_due_date, res.get('notes'), s_id)
                                if isinstance(created_hw, dict) and created_hw.get('id') and not homework_link_id:
                                    homework_link_id = created_hw.get('id')
                                homework_results.append(f"'{res.get('title')}' erstellt")
                            elif action == 'update' and hw_id:
                                us.update_homework(hw_id, user_id, res.get('title'), iso_due_date, res.get('notes'), s_id)
                                if not homework_link_id:
                                    homework_link_id = hw_id
                                homework_results.append(f"'{res.get('title')}' aktualisiert")
                            elif action == 'toggle' and hw_id:
                                us.toggle_homework_status(hw_id, user_id)
                                homework_results.append(f"'{hw_id}' umgeschaltet")
                            elif action == 'delete' and hw_id:
                                deleted_title = next((hw.get('title') for hw in current_homework if hw.get('id') == hw_id), hw_id)
                                us.delete_homework(hw_id, user_id)
                                homework_results.append(f"'{deleted_title}' gelöscht")
                        elif res.get('type') == 'worksheet_creation':
                            if calendar_entry_intent:
                                continue
                            md_content = res.get('content')
                        elif res.get('type') == 'memory_action':
                            content, act = res.get('content'), res.get('action', 'add')
                            if content:
                                if act == 'add': us.add_memory(user_id, content)
                                elif act == 'delete': us.delete_memory_by_content(user_id, content)
                        elif res.get('type') == 'set_chat_subject':
                            subject = res.get('subject')
                            if subject:
                                us.update_chat_session_subject(user_id, chat_session_id, subject)
                                current_chat_subject = subject
                                if not client_disconnected: yield from yield_sse(f"SESSION_SUBJECT:{subject}")
                        elif res.get('type') == 'chat_naming':
                            new_title = res.get('title')
                            if user_id and new_title:
                                us.rename_chat_session(user_id, chat_session_id, new_title)
                                if not client_disconnected: yield from yield_sse(f"SESSION_TITLE:{new_title}")
                except Exception: continue

            # Cleanup display text - Remove only internal markup, not regular brackets in text
            display_text = re.sub(r'<action>[\s\S]*?</?action>', '', full_answer, flags=re.IGNORECASE)
            # Remove "thinking"/"thoughts" tags and similar internal markup only
            display_text = re.sub(r'\[(?:thinking|thoughts|gedanken|chain-of-thought|analysis)\][\s\S]*?\[/(?:thinking|thoughts|gedanken|chain-of-thought|analysis)\]', '', display_text, flags=re.IGNORECASE)
            display_text = re.sub(r'\{(?:gedanken|thoughts|thinking|internal)[^}]*\}', '', display_text, flags=re.IGNORECASE)
            display_text = re.sub(r'</?action/?>', '', display_text, flags=re.IGNORECASE)
            
            # Only remove incomplete brackets/tags at end of text
            display_text = re.sub(r'<action[\s\S]*$', '', display_text, flags=re.IGNORECASE)
            display_text = re.sub(r'\{[^{}]*$', '', display_text)
            
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
            
            # Clean up whitespace - keep newlines but trim start/end
            display_text = display_text.strip()

            if not display_text and homework_results:
                if len(homework_results) == 1:
                    display_text = f"Erledigt: {homework_results[0]}."
                else:
                    display_text = "Erledigt:\n- " + "\n- ".join(homework_results)

            if calendar_entry_intent and not homework_action_processed and not homework_results:
                display_text = (
                    "Ich konnte den Kalendereintrag noch nicht wirklich speichern, "
                    "weil kein gueltiges homework_action-Tag erzeugt wurde. "
                    "Bitte nenne Titel und Datum noch einmal kurz, dann trage ich es korrekt ein."
                )

            # --- SOFORTIGES SPEICHERN DER ANTWORT ---
            assistant_msg_idx = None
            if user_id and (display_text or md_content):
                initial_ws = 'PENDING' if md_content else None
                assistant_msg_idx = us.save_chat_message(
                    user_id, chat_session_id, 'assistant', display_text,
                    worksheet_filename=initial_ws, homework_id=homework_link_id, chat_subject=current_chat_subject
                )
                print(f"DEBUG: Message saved for session {chat_session_id}")

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

                if user_id and assistant_msg_idx is not None and pdf_basename:
                    us.update_chat_message_worksheet(user_id, chat_session_id, assistant_msg_idx, pdf_basename)

            if not client_disconnected:
                if homework_results: yield from yield_sse("HOMEWORK_UPDATED")
                if homework_link_id: yield from yield_sse(f"HOMEWORK_LINK:{homework_link_id}")
                if pdf_basename: yield from yield_sse(f"WORKSHEET_DOWNLOAD_LINK:{pdf_basename}")

            if pdf_basename and user_id:
                _ws_title = "Arbeitsblatt fertig!"
                _ws_body = f"Dein Arbeitsblatt ({current_chat_subject or 'Allgemein'}) wurde erstellt und kann heruntergeladen werden."
                send_ntfy_notification(
                    get_user_ntfy_topic(user_id), _ws_title, _ws_body,
                    tags=["page_facing_up"]
                )
                send_fcm_notification(user_id, _ws_title, _ws_body)

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            traceback.print_exc()
            error_msg = f"❌ Ein unerwarteter Fehler ist aufgetreten: {str(e)}"
            if user_id:
                us.save_chat_message(user_id, chat_session_id, 'assistant', error_msg, chat_subject=current_chat_subject)
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
    user_id = session.get('user_id')
    chat_session_id = session.get('chat_session_id')
    
    effective_user_id = user_id if user_id else (f"guest_{chat_session_id}" if chat_session_id else None)
    if not effective_user_id:
        return jsonify([])
        
    sessions = us.get_user_chat_sessions(effective_user_id)
    return jsonify(sessions)

@app.route('/load-chat/<session_id>', methods=['POST'])
def load_chat(session_id):
    user_id = session.get('user_id')
    
    # For guests, we only allow loading their own current session
    if not user_id:
        current_id = session.get('chat_session_id')
        if session_id != current_id:
            # But wait, if they have multiple sessions in the sidebar? 
            # They should be able to load them.
            pass
            
    effective_user_id = user_id if user_id else f"guest_{session_id}"
    chat_history = us.get_chat_history(effective_user_id, session_id)
    session['chat_session_id'] = session_id
    return jsonify({'chat_history': chat_history})

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('legal/privacy_policy_page.html', is_logged_in='user_id' in session)

@app.route('/impressum')
def impressum():
    return render_template('legal/impressum_page.html', is_logged_in='user_id' in session)

@app.route('/agb')
def agb():
    return render_template('legal/agb_page.html', is_logged_in='user_id' in session)

@app.route('/get-chat-history', methods=['GET'])
def get_current_chat_history():
    user_id = session.get('user_id')
    chat_session_id = session.get('chat_session_id')

    if not chat_session_id or not user_id:
        return jsonify({'chat_history': []})

    chat_history = us.get_chat_history(user_id, chat_session_id)
    return jsonify({'chat_history': chat_history})

@app.route('/api/check-worksheet-status')
def check_worksheet_status():
    user_id = session.get('user_id')
    chat_session_id = session.get('chat_session_id')

    if not chat_session_id or not user_id:
        return jsonify({'generating': False})

    history = us.get_chat_history(user_id, chat_session_id)
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

    # Create or retrieve chat session
    if user_id:
        if 'chat_session_id' not in session:
            # Check if user has existing sessions to resume one instead of always creating a new one
            existing_sessions = us.get_user_chat_sessions(user_id)
            if existing_sessions:
                session['chat_session_id'] = existing_sessions[0]['session_id']
            else:
                new_id = str(uuid.uuid4())
                session['chat_session_id'] = new_id
                # Save welcome message to DB so it persists on refresh
                welcome_content = "Hi! Ich bin dein persönlicher Lernassistent. Sprich mit mir oder schreibe mir deine Fragen! Ich werde dir nie die Lösung verraten, sondern dir helfen sie selbst herauszufinden."
                us.save_chat_message(user_id, new_id, 'assistant', welcome_content)
    else:
        # For guests, preserve session if it exists
        if 'chat_session_id' not in session:
            new_id = str(uuid.uuid4())
            session['chat_session_id'] = new_id
            # Save welcome message for guest
            welcome_content = "Hi! Ich bin dein persönlicher Lernassistent. Sprich mit mir oder schreibe mir deine Fragen! Ich werde dir nie die Lösung verraten, sondern dir helfen sie selbst herauszufinden."
            us.save_chat_message(f"guest_{new_id}", new_id, 'assistant', welcome_content)
    
    # Cleanup old completed homework (24h) if logged in
    if user_id:
        us.delete_old_completed_homework(user_id)

    # Get user's chat sessions
    effective_user_id = user_id if user_id else f"guest_{session.get('chat_session_id')}"
    user_sessions = us.get_user_chat_sessions(effective_user_id)

    # Get assignments
    assignments = []
    class_name = session.get('class_name')
    if user_id and class_name:
        assignments = get_assignments_for_class(class_name, session.get('school'))

    # Get homework
    homework = us.get_homework_for_user(user_id) if user_id else []

    # First login check
    is_first_login = False
    if user_id:
        is_first_login = us.get_first_login_status(user_id)
        if is_first_login:
            us.set_first_login_status(user_id, False)

    return render_template('index.html',
                         user_type=user_type,
                         is_guest=not user_id,
                         username=session.get('username', 'Gast'),
                         class_name=class_name,
                         chat_sessions=user_sessions,
                         current_session_id=session.get('chat_session_id'),
                         assignments=assignments,
                         homework=homework,
                         is_first_login=is_first_login,
                         rating_in_main_page=RATING_IN_MAIN_PAGE)

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'it-admin':
        return redirect(url_for('login'))

    school = session.get('school')
    teachers = us.get_teachers_for_school(school)
    students = us.get_students_for_school(school)

    return render_template('admin_dashboard.html', teachers=teachers, students=students, school=school)

@app.route('/admin/assign-teacher', methods=['POST'])
def assign_teacher_route():
    if 'user_id' not in session or session.get('user_type') != 'it-admin':
        return redirect(url_for('login'))

    teacher_username = request.form.get('teacher_username')
    class_name = request.form.get('class_name')

    if teacher_username and class_name:
        us.assign_teacher_to_class(teacher_username, class_name)

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add-student', methods=['POST'])
def add_student_route():
    if 'user_id' not in session or session.get('user_type') != 'it-admin':
        return redirect(url_for('login'))

    student_username = request.form.get('student_username')
    class_name = request.form.get('class_name')

    if student_username and class_name:
        us.add_student_to_class(student_username, class_name)

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

        # Notify all students in the class via ntfy + FCM
        try:
            for student in us.get_students_for_class(class_name, school):
                _sid = student['uuid']
                _at = f"Neue Aufgabe: {title}"
                _ab = description[:200] if description else ""
                send_ntfy_notification(
                    get_user_ntfy_topic(_sid), _at, _ab, tags=["books"]
                )
                send_fcm_notification(_sid, _at, _ab)
        except Exception as _e:
            print(f"[ntfy] Assignment notification error: {_e}")

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
        subject_id = request.form.get('subject_id') or None

        if not title:
            return render_template('create_homework.html', error='Titel ist erforderlich.', subjects=us.get_subjects(user_id))

        us.create_homework(user_id, title, due_date, notes, subject_id)
        return redirect(url_for('index'))

    prefill_date = request.args.get('due_date', '')
    return render_template('create_homework.html', subjects=us.get_subjects(user_id), prefill_date=prefill_date)

@app.route('/view-homework/<homework_id>')
def view_homework(homework_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    homework = us.get_single_homework(homework_id, session['user_id'])
    if not homework:
        return render_template('homework_deleted.html'), 404

    return render_template('view_homework.html', homework=homework)

@app.route('/calendar')
def calendar_route():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    homework = us.get_homework_for_user(session['user_id'])
    return render_template('calendar.html', homework=homework)

@app.route('/edit-homework/<homework_id>', methods=['GET', 'POST'])
def edit_homework_route(homework_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    homework = us.get_single_homework(homework_id, user_id)

    if not homework or homework['user_id'] != user_id:
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title')
        due_date = request.form.get('due_date')
        notes = request.form.get('notes')
        subject_id = request.form.get('subject_id') or None

        if not title:
            return render_template('edit_homework.html', homework=homework, subjects=us.get_subjects(user_id), error='Titel ist erforderlich.')

        us.update_homework(homework_id, user_id, title, due_date, notes, subject_id)
        return redirect(url_for('view_homework', homework_id=homework_id))

    return render_template('edit_homework.html', homework=homework, subjects=us.get_subjects(user_id))

@app.route('/toggle-homework/<homework_id>', methods=['POST'])
def toggle_homework_route(homework_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    us.toggle_homework_status(homework_id, session['user_id'])
    return jsonify({'success': True})

@app.route('/delete-homework/<homework_id>', methods=['POST'])
def delete_homework_route(homework_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    us.delete_homework(homework_id, session['user_id'])
    return jsonify({'success': True})

@app.route('/create-subject', methods=['POST'])
def create_subject_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401

    name = request.json.get('name')
    if not name:
        return jsonify({'error': 'Name ist erforderlich'}), 400

    subject_id = us.create_subject(session['user_id'], name)
    if subject_id:
        return jsonify({'success': True, 'subject_id': subject_id, 'name': name})
    else:
        return jsonify({'error': 'Fach existiert bereits'}), 400

@app.route('/delete-subject/<subject_id>', methods=['POST'])
def delete_subject_route(subject_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401

    if us.delete_subject(subject_id, session['user_id']):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Fehler beim Löschen'}), 500



@app.route('/cache-image', methods=['POST'])
def cache_image():
    if 'image' not in request.files:
        return jsonify({'error': 'Kein Bild gefunden.'}), 400

    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'error': 'Kein Bild ausgewählt.'}), 400

    try:
        # Generate a unique filename
        filename = str(uuid.uuid4()) + os.path.splitext(image_file.filename)[1]
        image_path = os.path.join('uploads', filename)
        image_file.save(image_path)

        # Store filenames in session list
        if 'cached_image_filenames' not in session:
            session['cached_image_filenames'] = []
        
        # Make sure it's a list (for sessions that might have old single-file format)
        if not isinstance(session['cached_image_filenames'], list):
             session['cached_image_filenames'] = []

        session['cached_image_filenames'].append(filename)
        session.modified = True

        return jsonify({
            'success': True,
            'filename': filename,
            'message': 'Bild wurde zwischengespeichert.'
        })

    except Exception as e:
        print(f"Error caching image: {e}")
        return jsonify({'error': 'Fehler beim Zwischenspeichern.'}), 500

@app.route('/api/delete-cached-image', methods=['POST'])
def delete_cached_image():
    data = request.get_json()
    filename = data.get('filename')
    
    if not filename:
        return jsonify({'error': 'Filename missing'}), 400
        
    filenames = session.get('cached_image_filenames', [])
    if filename in filenames:
        try:
            os.remove(os.path.join('uploads', filename))
            filenames.remove(filename)
            session['cached_image_filenames'] = filenames
            session.modified = True
            return jsonify({'success': True})
        except OSError as e:
            print(f"Error deleting cached image: {e}")
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'File not found in session'}), 404

@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    filenames = session.pop('cached_image_filenames', [])
    # Also handle old key for compatibility
    old_filename = session.pop('cached_image_filename', None)
    if old_filename: filenames.append(old_filename)
    
    deleted_count = 0
    for filename in filenames:
        try:
            os.remove(os.path.join('uploads', filename))
            deleted_count += 1
        except OSError as e:
            print(f"Error deleting cached image {filename}: {e}")
            
    return jsonify({'message': f'{deleted_count} Bilder wurden gelöscht.'})

@app.route('/api/memories', methods=['GET'])
def get_user_memories_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    memories = us.get_memories(session['user_id'])
    return jsonify({'memories': memories})

@app.route('/api/memories', methods=['POST'])
def add_user_memory_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401

    data = request.get_json()
    content = data.get('content')

    if not content:
        return jsonify({'error': 'Inhalt ist erforderlich'}), 400

    if us.add_memory(session['user_id'], content):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Fehler beim Speichern oder Duplikat'}), 500

@app.route('/api/memories/<memory_id>', methods=['DELETE'])
def delete_user_memory_route(memory_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401

    if us.delete_memory(memory_id, session['user_id']):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Fehler beim Löschen'}), 500

@app.route('/api/settings/math-solver', methods=['GET'])
def get_math_solver_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401
    status = us.get_math_solver_status(session['user_id'])
    return jsonify({'enabled': status})

@app.route('/api/settings/math-solver', methods=['POST'])
def set_math_solver_route():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401

    data = request.get_json()
    enabled = data.get('enabled', False)

    if us.set_math_solver_status(session['user_id'], enabled):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Fehler beim Speichern'}), 500

@app.route('/api/account/download-data', methods=['GET'])
def download_user_data():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401

    data = us.export_user_data(session['user_id'])
    # Remove password from export for safety
    if data.get('user'):
        data['user'].pop('password', None)

    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    import io
    buf = io.BytesIO(json_bytes)
    buf.seek(0)
    username = session.get('username', 'user')
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"learn-ai-daten-{username}.json",
        mimetype='application/json'
    )

@app.route('/api/account/delete', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return jsonify({'error': 'Nicht angemeldet'}), 401

    user_uuid = session['user_id']
    if us.delete_user(user_uuid):
        session.clear()
        return jsonify({'success': True})
    return jsonify({'error': 'Fehler beim Löschen des Kontos'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
