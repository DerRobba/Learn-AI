import subprocess
import os
import base64
import uuid
import json
import re
import traceback
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, Response, abort, current_app
import requests
from dotenv import load_dotenv
from openai import OpenAI
from database import init_database, create_user, get_user, save_chat_message, get_chat_history, get_user_chat_sessions, delete_chat_session, rename_chat_session, create_assignment, get_assignments_for_class, get_assignment, delete_assignment, create_submission, get_submissions_for_assignment, get_submission_for_user, get_user_by_username, assign_teacher_to_class, add_student_to_class, get_teachers_for_school, get_students_for_school, get_unique_school_names, get_student_usernames_for_school, get_unique_class_names_for_school, get_teacher_usernames_for_school, create_homework, get_homework_for_user, delete_homework, toggle_homework_status, create_subject, get_subjects, delete_subject, get_single_homework, delete_old_completed_homework, update_homework, get_subject_id_by_name, delete_all_homework, add_memory, get_memories, delete_memory, delete_memory_by_content, set_math_solver_status, get_math_solver_status

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

# Ensure uploads directory exists
if not os.path.exists('uploads'):
    os.makedirs('uploads')

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
    agb_accept = request.form.get('agb_accept')

    if not username or not password or not password_confirm or not user_type or not school:
        return render_template('register.html', error='Alle Felder sind erforderlich.')

    if not agb_accept:
        return render_template('register.html', error='Du musst die AGB akzeptieren.')

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
    save_chat_message(session['user_id'], new_session_id, 'assistant', 'Hi! Ich bin dein persönlicher Lernassistent. Sprich mit mir oder schreibe mir deine Fragen!')

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
            # Clear from session so it's only used once
            session.pop('cached_image_filename', None)
            print(f"DEBUG: Cached image loaded and cleared from session: {cached_image_filename}")
        except Exception as e:
            print(f"Error reading cached image: {e}")


    if not chat_session_id:
        chat_session_id = str(uuid.uuid4())
        session['chat_session_id'] = chat_session_id

    def generate():
        try:
            from datetime import datetime
            # Get current date info
            now = datetime.now()
            current_date_str = now.strftime("%Y-%m-%d")
            current_weekday = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][now.weekday()]

            # Get existing chat history for context
            chat_history = get_chat_history(user_id, chat_session_id)
            
            # Get current homework and subjects for context (limit to recent 15)
            current_homework = get_homework_for_user(user_id)[:15]
            current_subjects = get_subjects(user_id)
            
            # Get user memories
            user_memories = get_memories(user_id)
            memories_text = "\n".join([f"- {m['content']}" for m in user_memories])

            # Get math solver status
            math_solver_enabled = get_math_solver_status(user_id)

            # Build conversation context from database
            conversation_context = system_prompt if system_prompt else ""
            
            if math_solver_enabled:
                 conversation_context += "\n\nZUSATZREGEL: Du darfst Matheaufgaben vollständig lösen und den Rechenweg zeigen. Die Regel 'keine Lösungen sagen' ist für diesen Benutzer AUFGEHOBEN."
            else:
                 conversation_context += "\n\nZUSATZREGEL: Bei Matheaufgaben darfst du KEINE Lösungen direkt verraten. Gib nur Tipps und Hilfestellungen zum Lösungsweg."

            conversation_context += f"\n\nHEUTE IST: {current_weekday}, der {current_date_str}"
            if memories_text:
                conversation_context += f"\n\nDAS WEIßT DU ÜBER DEN BENUTZER (Erinnerungen):\n{memories_text}"
            
            conversation_context += f"\n\nDeine aktuelle Hausaufgaben-Liste: {json.dumps(current_homework)}"
            conversation_context += f"\nDeine verfügbaren Fächer: {json.dumps(current_subjects)}"
            conversation_context += "\n\nANWEISUNG: Du bist ein Hausaufgaben-Assistent. Du kannst Hausaufgaben eintragen, bearbeiten oder löschen."
            conversation_context += "\nWenn du eine Aktion durchführst, schreibe ZUERST deine Antwort an den Benutzer und füge AM ENDE deiner Nachricht die Aktion im JSON-Format zwischen <action> und </action> Tags ein."
            conversation_context += "\nBeispiel: Ich habe Mathe eingetragen. <action>{\"type\": \"homework_action\", \"action\": \"create\", \"title\": \"Mathe S.12\", \"due_date\": \"YYYY-MM-DD\", \"subject_name\": \"Mathe\"}</action>"
            conversation_context += "\n\nSPEICHERUNG VON FAKTEN: Sei extrem aufmerksam auf kleine Details! Wenn der Benutzer dir persönliche Informationen gibt oder diese aus hochgeladenen Dokumenten/Bildern hervorgehen (z.B. Name auf einem Arbeitsblatt, spezifische Lernschwächen, Themen die er gut/schlecht kann), speichere diese SOFORT als Erinnerung."
            conversation_context += "\nNutze dafür: <action>{\"type\": \"memory_action\", \"action\": \"add\", \"content\": \"Der Benutzer heißt Max (aus Arbeitsblatt erkannt).\"}</action>"
            conversation_context += "\nOder: <action>{\"type\": \"memory_action\", \"action\": \"add\", \"content\": \"Benutzer tut sich schwer mit Bruchrechnung.\"}</action>"
            conversation_context += "\nINFO: Wenn du eine Erinnerung speicherst, erwähne beiläufig, dass der Benutzer diese jederzeit in den Einstellungen (Zahnrad-Symbol) verwalten oder löschen kann."
            conversation_context += "\n\nKONFLIKTE LÖSEN: Wenn eine neue Information einer alten widerspricht (z.B. Benutzer heißt jetzt Peter statt Bo), LÖSCHE die alte Erinnerung!"
            conversation_context += "\nZum Löschen nutze: <action>{\"type\": \"memory_action\", \"action\": \"delete\", \"content\": \"EXAKTER INHALT DERALTEN ERINNERUNG\"}</action>"
            conversation_context += "\n\nWICHTIG: Nutze für 'due_date' IMMER das Format YYYY-MM-DD. Wenn der Benutzer 'morgen' sagt, berechne das Datum basierend auf HEUTE."
            conversation_context += "\n\nWICHTIG: Benutze NIEMALS JSON-Code außerhalb von <action> Tags. Erstelle neue Fächer automatisch, indem du den 'subject_name' angibst."
            conversation_context += "\n\nWICHTIG: Wenn der Benutzer ein Arbeitsblatt möchte, füge zusätzlich ein JSON-Objekt hinzu: <action>{\"type\": \"worksheet_creation\", \"content\": \"# Titel\\n\\n## Aufgabe 1\\nFrage...\"}</action>."
            conversation_context += "\nACHTUNG: Der Inhalt muss valides Markdown sein. Nutze '\\n' für Zeilenumbrüche. Mache IMMER ein Leerzeichen nach '#' (z.B. '# Titel', nicht '#Titel')."
            conversation_context += "\nVERBOTEN: Beginne den Inhalt NIEMALS mit 'createmd:'. Schreibe direkt das Markdown."
            conversation_context += "\nINFO: Wenn du ein Arbeitsblatt erstellst, bestätige dies kurz und bitte um einen Moment Geduld. Gib KEINE Überbrückungsaufgaben oder Rätsel für die Wartezeit, da es nur wenige Sekunden dauert."
            conversation_context += "\n\nDRINGEND: Achte penibel auf korrekte Leerzeichen! Setze NACH jedem Satzzeichen (.,!?) ein Leerzeichen, BEVOR du weiterschreibst oder einen <action> Tag öffnest."

            # Prepare messages with chat history
            messages = [
                {"role": "system", "content": conversation_context}
            ]

            # Reconstruct history strictly alternating
            processed_history = []
            for msg in chat_history:
                role = msg['message_type']
                if role not in ['user', 'assistant']:
                    continue
                
                content = msg['content']
                img = msg.get('image_data')
                
                if role == 'user' and img:
                    msg_obj = {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": content},
                            {"type": "image_url", "image_url": {"url": img}}
                        ]
                    }
                else:
                    msg_obj = {"role": role, "content": content}

                if not processed_history:
                    # The first message after system should ideally be 'user'
                    # If history starts with 'assistant' (e.g. the welcome message), we skip it for the AI context
                    if role == 'user':
                        processed_history.append(msg_obj)
                else:
                    # Ensure alternating roles
                    if role != processed_history[-1]['role']:
                        processed_history.append(msg_obj)
                    else:
                        # Same role twice: merge content
                        processed_history[-1]['content'] = str(processed_history[-1]['content']) + "\n" + content
            
            messages.extend(processed_history)

            # Save user question to database
            image_data = None
            if cached_image:
                image_data = f"data:{cached_image['mime_type']};base64,{cached_image['base64']}"

            save_chat_message(user_id, chat_session_id, 'user', question, image_data)

            # Check if we need to append current question (must follow an assistant message or be the first)
            # If the history ended with 'user', we add a dummy assistant response to allow the new user question
            if messages and messages[-1]['role'] == 'user':
                messages.append({"role": "assistant", "content": "..."})
            
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

            # Final check: Ensure the first message after system is 'user'
            # If all history was skipped/empty, the current question will be the first and it's 'user'. Correct.
            if len(messages) > 1 and messages[1]['role'] == 'assistant':
                # This could happen if history was [assistant] and we added a dummy assistant
                # We remove the first assistant message to start with user
                messages.pop(1)

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

            # Inside generate() loop, after full_answer is collected:
            homework_results = []
            memory_results = []
            md_content = None

            # Find all <action> blocks
            action_blocks = re.findall(r'<action>(.*?)</action>', full_answer, re.DOTALL)
            
            # Fallback to general JSON find if no tags were used (for robustness)
            if not action_blocks:
                action_blocks = re.findall(r'(\{.*?\}|\[.*?\])', full_answer, re.DOTALL)
            
            for block in action_blocks:
                try:
                    res_data = json.loads(block)
                    if not isinstance(res_data, list):
                        res_list = [res_data]
                    else:
                        res_list = res_data
                        
                    for res in res_list:
                        if not isinstance(res, dict): continue
                        
                        if res.get('type') == 'homework_action':
                            action = res.get('action')
                            hw_id = res.get('id')
                            
                            if action == 'create':
                                s_name = res.get('subject_name', '').strip()
                                s_id = get_subject_id_by_name(user_id, s_name) if s_name else None
                                if s_name and s_id is None:
                                    s_id = create_subject(user_id, s_name)
                                    if s_id is False: s_id = get_subject_id_by_name(user_id, s_name)
                                
                                create_homework(user_id, res.get('title'), res.get('due_date'), res.get('notes'), s_id)
                                homework_results.append(f"'{res.get('title')}' erstellt")
                            elif action == 'update' and hw_id:
                                s_name = res.get('subject_name', '').strip()
                                s_id = get_subject_id_by_name(user_id, s_name) if s_name else None
                                if s_name and s_id is None:
                                    s_id = create_subject(user_id, s_name)
                                    if s_id is False: s_id = get_subject_id_by_name(user_id, s_name)
                                
                                update_homework(hw_id, user_id, res.get('title'), res.get('due_date'), res.get('notes'), s_id)
                                homework_results.append(f"'{res.get('title')}' aktualisiert")
                            elif action == 'toggle' and hw_id:
                                toggle_homework_status(hw_id, user_id)
                                homework_results.append("Status geändert")
                            elif action == 'delete' and hw_id:
                                delete_homework(hw_id)
                                homework_results.append("gelöscht")
                            elif action == 'deleteAll':
                                delete_all_homework(user_id)
                                homework_results.append("alle Hausaufgaben gelöscht")
                        elif res.get('type') == 'worksheet_creation':
                             md_content = res.get('content')
                        elif res.get('type') == 'memory_action':
                            content = res.get('content')
                            action_type = res.get('action', 'add') # Default to add for backward compatibility
                            
                            if content:
                                if action_type == 'add':
                                    if add_memory(user_id, content):
                                        memory_results.append("Erinnerung gespeichert")
                                    else:
                                        memory_results.append("Erinnerung existiert bereits")
                                elif action_type == 'delete':
                                    if delete_memory_by_content(user_id, content):
                                        memory_results.append("Erinnerung aktualisiert")
                except Exception:
                    continue

            pdf_basename = None
            if md_content:
                worksheet_uuid = str(uuid.uuid4())
                md_filename = f"sheets/{worksheet_uuid}.md"
                pdf_filename = f"sheets/{worksheet_uuid}.pdf"

                with open(md_filename, "w", encoding='utf-8') as f:
                    f.write(md_content.strip())
                
                # Convert MD to PDF using the external service
                try:
                    response = requests.post(
                        'https://api.md-to-pdf.l-ai.pro',
                        data={'markdown': md_content.strip()},
                        timeout=30
                    )
                    response.raise_for_status()
                    with open(pdf_filename, 'wb') as f:
                        f.write(response.content)
                    pdf_basename = os.path.basename(pdf_filename)
                except Exception as e:
                    print(f"PDF generation failed: {e}")
                    yield "data: Fehler beim Erstellen des Arbeitsblatts.\n\n"

            # Clean up message for storage (remove all JSON and tags)
            # We replace with a space first to prevent sentences sticking together, then clean double spaces
            display_text = re.sub(r'<action>[\s\S]*?</?action>', ' ', full_answer, flags=re.IGNORECASE)
            display_text = re.sub(r'(\{.*?\}|\[.*?\])', ' ', display_text)
            display_text = re.sub(r'</?action/?>', ' ', display_text, flags=re.IGNORECASE)
            display_text = re.sub(r'\s+', ' ', display_text).strip()
            
            if not display_text:
                if homework_results:
                    display_text = "Erledigt: " + ", ".join(homework_results)
                elif memory_results:
                    display_text = "Ich habe mir das gemerkt."
            
            if display_text:
                save_chat_message(user_id, chat_session_id, 'assistant', display_text, worksheet_filename=pdf_basename)
            
            if homework_results:
                yield "data: HOMEWORK_UPDATED\n\n"
            
            if pdf_basename:
                yield f"data: WORKSHEET_DOWNLOAD_LINK:{pdf_basename}\n\n"
            
            # Auto-naming: Only if this is the start of the conversation (e.g., <= 2 messages in history including the one just added)
            # We count messages in chat_history. user msg + current assistant msg = 2 new ones. 
            # If total history is small, we generate a title.
            if len(chat_history) <= 1: # History before this turn was 0 or 1 message
                try:
                    title_prompt = "Fasse das Thema dieser Konversation in 1-4 Schlagworten zusammen. Antworte NUR mit den Schlagworten. KEINE ganzen Sätze. KEIN Satzzeichen am Ende."
                    # We must append the assistant's answer to the history before asking for title, 
                    # otherwise we have user-user sequence (question + title_prompt)
                    title_messages = messages + [
                        {"role": "assistant", "content": display_text if display_text else " "},
                        {"role": "user", "content": title_prompt}
                    ]
                    
                    # Short context call for title
                    title_response = client.chat.completions.create(
                        model=MODEL,
                        messages=title_messages,
                        max_tokens=15
                    )
                    new_title = title_response.choices[0].message.content.strip().strip('"').strip('.')
                    if new_title:
                        rename_chat_session(user_id, chat_session_id, new_title)
                        yield f"data: SESSION_TITLE:{new_title}\n\n"
                except Exception as e:
                    print(f"Auto-naming failed: {e}")

        except requests.exceptions.RequestException as e:
            print(f"Error communicating with API: {e}")
            error_message = "Entschuldigung, es gab ein Problem mit der Verbindung. Bitte stellen Sie sicher, dass der Dienst erreichbar ist."
            save_chat_message(user_id, chat_session_id, 'assistant', error_message)
            yield f"data: {error_message}\n\n"
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            traceback.print_exc()
            error_message = f"Ein unerwarteter Fehler ist aufgetreten: {str(e)}"
            save_chat_message(user_id, chat_session_id, 'assistant', error_message)
            yield f"data: {error_message}\n\n"

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

    # Create new chat session if not exists
    if 'chat_session_id' not in session:
        session['chat_session_id'] = str(uuid.uuid4())

    user_id = session['user_id']
    
    # Cleanup old completed homework (24h)
    delete_old_completed_homework(user_id)

    # Get user's chat sessions
    user_sessions = get_user_chat_sessions(user_id)

    # Get assignments
    assignments = []
    class_name = session.get('class_name')
    if class_name:
        if user_type == 'teacher':
            assignments = get_assignments_for_class(class_name, session.get('school'))
        elif user_type == 'student':
            assignments = get_assignments_for_class(class_name, session.get('school'))

    # Get homework
    homework = get_homework_for_user(session['user_id'])

    return render_template('index.html',
                         user_type=user_type,
                         username=session.get('username'),
                         class_name=class_name,
                         chat_sessions=user_sessions,
                         current_session_id=session.get('chat_session_id'),
                         assignments=assignments,
                         homework=homework)

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
def delete_homework_route(homework_id):
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