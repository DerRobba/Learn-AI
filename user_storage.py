"""
File-based user data storage module.
Replaces SQLite for user profiles, conversations, homework, subjects and memories.
Each user gets a UUID4 folder under users/.
"""

import os
import json
import uuid
import shutil
import threading
from datetime import datetime, timedelta

USERS_DIR = 'users'
INDEX_FILE = os.path.join(USERS_DIR, 'index.json')

_lock = threading.Lock()


def _ensure_users_dir():
    os.makedirs(USERS_DIR, exist_ok=True)
    os.makedirs(os.path.join(USERS_DIR, 'guests'), exist_ok=True)


def get_user_dir(user_uuid):
    if user_uuid and user_uuid.startswith('guest_'):
        return os.path.join(USERS_DIR, 'guests', user_uuid)
    return os.path.join(USERS_DIR, user_uuid)


def _load_json(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return default
    return default


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_index():
    _ensure_users_dir()
    return _load_json(INDEX_FILE, {})


def _save_index(index):
    _ensure_users_dir()
    _save_json(INDEX_FILE, index)


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def create_user(username, password, user_type, school=None):
    """Create a new user. Returns True on success, False if username taken or IT-admin conflict."""
    with _lock:
        index = _load_index()
        if username in index:
            return False

        if user_type == 'it-admin' and school:
            # Only one IT-admin per school
            for uid in index.values():
                u = _load_user(uid)
                if u and u.get('user_type') == 'it-admin' and u.get('school') == school:
                    return False

        user_uuid = str(uuid.uuid4())
        user_dir = get_user_dir(user_uuid)
        os.makedirs(user_dir, exist_ok=True)

        now = datetime.now().isoformat()
        user_data = {
            'uuid': user_uuid,
            'username': username,
            'password': password,
            'user_type': user_type,
            'school': school,
            'class_name': None,
            'math_solver': False,
            'is_first_login': True,
            'created_at': now,
        }
        _save_json(os.path.join(user_dir, 'user.json'), user_data)
        _save_json(os.path.join(user_dir, 'conversations.json'), [])
        _save_json(os.path.join(user_dir, 'homework.json'), [])
        _save_json(os.path.join(user_dir, 'subjects.json'), [])
        _save_json(os.path.join(user_dir, 'memories.json'), [])

        index[username] = user_uuid
        _save_index(index)
        return True


def _load_user(user_uuid):
    path = os.path.join(get_user_dir(user_uuid), 'user.json')
    return _load_json(path, None)


def _save_user(user_uuid, data):
    path = os.path.join(get_user_dir(user_uuid), 'user.json')
    _save_json(path, data)


def get_user(username, password):
    """Authenticate user. Returns user dict or None."""
    index = _load_index()
    uid = index.get(username)
    if not uid:
        return None
    user = _load_user(uid)
    if user and user.get('password') == password:
        return user
    return None


def get_user_by_id(user_uuid):
    return _load_user(user_uuid)


def get_user_by_username(username):
    index = _load_index()
    uid = index.get(username)
    if not uid:
        return None
    return _load_user(uid)


def _update_user_field(user_uuid, **kwargs):
    with _lock:
        user = _load_user(user_uuid)
        if user is None:
            return False
        user.update(kwargs)
        _save_user(user_uuid, user)
        return True


def assign_teacher_to_class(teacher_username, class_name):
    index = _load_index()
    uid = index.get(teacher_username)
    return _update_user_field(uid, class_name=class_name) if uid else False


def add_student_to_class(student_username, class_name):
    index = _load_index()
    uid = index.get(student_username)
    return _update_user_field(uid, class_name=class_name) if uid else False


def get_all_users():
    index = _load_index()
    users = []
    for uid in index.values():
        u = _load_user(uid)
        if u:
            users.append(u)
    return users


def get_teachers_for_school(school):
    return [u for u in get_all_users() if u.get('user_type') == 'teacher' and u.get('school') == school]


def get_students_for_school(school):
    return [u for u in get_all_users() if u.get('user_type') == 'student' and u.get('school') == school]


def get_unique_school_names():
    schools = {u.get('school') for u in get_all_users() if u.get('school')}
    return sorted(schools)


def get_student_usernames_for_school(school):
    return [u['username'] for u in get_students_for_school(school)]


def get_unique_class_names_for_school(school):
    classes = {u.get('class_name') for u in get_all_users() if u.get('school') == school and u.get('class_name')}
    return sorted(classes)


def get_teacher_usernames_for_school(school):
    return [u['username'] for u in get_teachers_for_school(school)]


def delete_user(user_uuid):
    """Delete user folder and remove from index."""
    with _lock:
        user = _load_user(user_uuid)
        if not user:
            return False
        username = user.get('username')
        user_dir = get_user_dir(user_uuid)
        if os.path.exists(user_dir):
            shutil.rmtree(user_dir)
        index = _load_index()
        index.pop(username, None)
        _save_index(index)
        return True


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------

def get_math_solver_status(user_uuid):
    user = _load_user(user_uuid)
    return bool(user.get('math_solver', False)) if user else False


def set_math_solver_status(user_uuid, status):
    return _update_user_field(user_uuid, math_solver=bool(status))


def get_first_login_status(user_uuid):
    user = _load_user(user_uuid)
    return bool(user.get('is_first_login', False)) if user else False


def set_first_login_status(user_uuid, status):
    return _update_user_field(user_uuid, is_first_login=bool(status))


# ---------------------------------------------------------------------------
# Conversations (OpenAI-like format)
# ---------------------------------------------------------------------------

def _load_conversations(user_uuid):
    if not user_uuid:
        return []
    path = os.path.join(get_user_dir(user_uuid), 'conversations.json')
    return _load_json(path, [])


def _save_conversations(user_uuid, conversations):
    if not user_uuid:
        return
    path = os.path.join(get_user_dir(user_uuid), 'conversations.json')
    _save_json(path, conversations)


def _find_session(conversations, session_id):
    for s in conversations:
        if s.get('id') == session_id:
            return s
    return None


def get_user_chat_sessions(user_uuid):
    if not user_uuid:
        return []
    conversations = _load_conversations(user_uuid)
    sessions = []
    for s in conversations:
        msgs = s.get('messages', [])
        sessions.append({
            'session_id': s['id'],
            'session_name': s.get('name', 'Neuer Chat'),
            'first_message': msgs[0]['created_at'] if msgs else s.get('created_at', ''),
            'last_message': msgs[-1]['created_at'] if msgs else s.get('created_at', ''),
            'chat_subject': s.get('subject'),
        })
    sessions.sort(key=lambda x: x['last_message'] or '', reverse=True)
    return sessions


def get_chat_history(user_uuid, session_id):
    if not user_uuid:
        return []
    conversations = _load_conversations(user_uuid)
    session = _find_session(conversations, session_id)
    if not session:
        return []
    return [
        {
            'message_type': m['role'],
            'content': m['content'],
            'image_data': m.get('image_data'),
            'worksheet_filename': m.get('worksheet_filename'),
            'created_at': m.get('created_at'),
            'chat_subject': session.get('subject'),
        }
        for m in session.get('messages', [])
    ]


def save_chat_message(user_uuid, session_id, message_type, content,
                      image_data=None, worksheet_filename=None,
                      chat_subject=None, session_name=None):
    """Save a chat message. Returns message index within session (for worksheet updates)."""
    # image_data can be a string (data URL) or a list of strings
    if not user_uuid:
        return None
    with _lock:
        conversations = _load_conversations(user_uuid)
        session = _find_session(conversations, session_id)
        now = datetime.now().isoformat()

        if session is None:
            session = {
                'id': session_id,
                'name': session_name or 'Neuer Chat',
                'subject': chat_subject,
                'created_at': now,
                'updated_at': now,
                'messages': [],
            }
            conversations.insert(0, session)
        else:
            if session_name and session.get('name') in (None, 'Neuer Chat', ''):
                session['name'] = session_name
            if chat_subject:
                session['subject'] = chat_subject
            session['updated_at'] = now

        msg = {
            'role': message_type,
            'content': content,
            'created_at': now,
        }
        if image_data:
            msg['image_data'] = image_data
        if worksheet_filename:
            msg['worksheet_filename'] = worksheet_filename

        session['messages'].append(msg)
        msg_idx = len(session['messages']) - 1
        _save_conversations(user_uuid, conversations)
        return msg_idx


def update_chat_message_worksheet(user_uuid, session_id, msg_idx, worksheet_filename):
    if not user_uuid:
        return False
    with _lock:
        conversations = _load_conversations(user_uuid)
        session = _find_session(conversations, session_id)
        if session and 0 <= msg_idx < len(session['messages']):
            session['messages'][msg_idx]['worksheet_filename'] = worksheet_filename
            _save_conversations(user_uuid, conversations)
            return True
    return False


def delete_chat_session(user_uuid, session_id):
    if not user_uuid:
        return False
    with _lock:
        conversations = _load_conversations(user_uuid)
        conversations = [s for s in conversations if s.get('id') != session_id]
        _save_conversations(user_uuid, conversations)
    return True


def rename_chat_session(user_uuid, session_id, new_name):
    if not user_uuid:
        return False
    with _lock:
        conversations = _load_conversations(user_uuid)
        session = _find_session(conversations, session_id)
        if session:
            session['name'] = new_name
            _save_conversations(user_uuid, conversations)
            return True
    return False


def get_session_name(user_uuid, session_id):
    if not user_uuid:
        return None
    conversations = _load_conversations(user_uuid)
    session = _find_session(conversations, session_id)
    return session.get('name') if session else None


def update_chat_session_subject(user_uuid, session_id, subject):
    if not user_uuid:
        return False
    with _lock:
        conversations = _load_conversations(user_uuid)
        session = _find_session(conversations, session_id)
        if session:
            session['subject'] = subject
            _save_conversations(user_uuid, conversations)
            return True
    return False


def get_unique_chat_subjects(user_uuid):
    if not user_uuid:
        return []
    conversations = _load_conversations(user_uuid)
    subjects = sorted({s.get('subject') for s in conversations if s.get('subject')})
    return subjects


def get_chat_sessions_by_subject(user_uuid, subject):
    if not user_uuid:
        return []
    conversations = _load_conversations(user_uuid)
    sessions = []
    for s in conversations:
        if s.get('subject') == subject:
            msgs = s.get('messages', [])
            sessions.append({
                'session_id': s['id'],
                'session_name': s.get('name', 'Neuer Chat'),
                'first_message': msgs[0]['created_at'] if msgs else s.get('created_at', ''),
                'last_message': msgs[-1]['created_at'] if msgs else s.get('created_at', ''),
                'chat_subject': s.get('subject'),
            })
    sessions.sort(key=lambda x: x['last_message'] or '', reverse=True)
    return sessions


def get_all_previous_chats_summaries(user_uuid, exclude_session_id=None):
    if not user_uuid:
        return []
    conversations = _load_conversations(user_uuid)
    summaries = []
    for s in conversations:
        if len(summaries) >= 20:
            break
        if exclude_session_id and s.get('id') == exclude_session_id:
            continue
        name = s.get('name', 'Neuer Chat')
        subject = s.get('subject')
        preview_msgs = [m for m in s.get('messages', []) if m['role'] in ('user', 'assistant')][:5]

        summary = f"- {name}"
        if subject:
            summary += f" (Thema: {subject})"
        if preview_msgs:
            parts = [f"[{m['role']}]: {m['content'][:100]}" for m in preview_msgs]
            summary += ": " + " | ".join(parts)
        summaries.append(summary)
    return summaries


# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------

def _load_subjects(user_uuid):
    path = os.path.join(get_user_dir(user_uuid), 'subjects.json')
    return _load_json(path, [])


def _save_subjects(user_uuid, subjects):
    path = os.path.join(get_user_dir(user_uuid), 'subjects.json')
    _save_json(path, subjects)


def get_subjects(user_uuid):
    return _load_subjects(user_uuid)


def get_subject_id_by_name(user_uuid, name):
    for s in _load_subjects(user_uuid):
        if s['name'].lower() == name.lower():
            return s['id']
    return None


def create_subject(user_uuid, name):
    with _lock:
        subjects = _load_subjects(user_uuid)
        for s in subjects:
            if s['name'].lower() == name.lower():
                return False
        new_id = str(uuid.uuid4())
        subjects.append({'id': new_id, 'name': name, 'created_at': datetime.now().isoformat()})
        _save_subjects(user_uuid, subjects)
        return new_id


def delete_subject(subject_id, user_uuid):
    with _lock:
        subjects = _load_subjects(user_uuid)
        subjects = [s for s in subjects if s['id'] != subject_id]
        _save_subjects(user_uuid, subjects)
        # Unlink from homework
        homework = _load_homework(user_uuid)
        for hw in homework:
            if hw.get('subject_id') == subject_id:
                hw['subject_id'] = None
        _save_homework(user_uuid, homework)
    return True


# ---------------------------------------------------------------------------
# Homework
# ---------------------------------------------------------------------------

def _load_homework(user_uuid):
    path = os.path.join(get_user_dir(user_uuid), 'homework.json')
    return _load_json(path, [])


def _save_homework(user_uuid, homework):
    path = os.path.join(get_user_dir(user_uuid), 'homework.json')
    _save_json(path, homework)


def _enrich_hw(hw, subject_map):
    hw = dict(hw)
    hw['subject_name'] = subject_map.get(hw.get('subject_id'))
    hw['completed'] = bool(hw.get('completed', False))
    hw['user_id'] = hw.get('user_uuid', '')
    return hw


def create_homework(user_uuid, title, due_date, notes, subject_id=None):
    with _lock:
        homework = _load_homework(user_uuid)
        homework.append({
            'id': str(uuid.uuid4()),
            'user_uuid': user_uuid,
            'title': title,
            'due_date': due_date,
            'notes': notes,
            'subject_id': subject_id,
            'completed': False,
            'completed_at': None,
            'created_at': datetime.now().isoformat(),
        })
        _save_homework(user_uuid, homework)
    return True


def get_homework_for_user(user_uuid):
    homework = _load_homework(user_uuid)
    subject_map = {s['id']: s['name'] for s in _load_subjects(user_uuid)}
    enriched = [_enrich_hw(hw, subject_map) for hw in homework]
    enriched.sort(key=lambda x: (x['completed'], x.get('due_date') or ''))
    return enriched


def get_single_homework(homework_id, user_uuid=None):
    if not user_uuid:
        return None
    homework = _load_homework(user_uuid)
    subject_map = {s['id']: s['name'] for s in _load_subjects(user_uuid)}
    for hw in homework:
        if hw['id'] == homework_id:
            result = _enrich_hw(hw, subject_map)
            result['user_id'] = user_uuid  # used for ownership check in app.py
            return result
    return None


def update_homework(homework_id, user_uuid, title, due_date, notes, subject_id=None):
    with _lock:
        homework = _load_homework(user_uuid)
        for hw in homework:
            if hw['id'] == homework_id:
                hw.update({'title': title, 'due_date': due_date, 'notes': notes, 'subject_id': subject_id})
                _save_homework(user_uuid, homework)
                return True
    return False


def delete_homework(homework_id, user_uuid=None):
    if not user_uuid:
        return False
    with _lock:
        homework = _load_homework(user_uuid)
        homework = [hw for hw in homework if hw['id'] != homework_id]
        _save_homework(user_uuid, homework)
    return True


def delete_all_homework(user_uuid):
    _save_homework(user_uuid, [])
    return True


def toggle_homework_status(homework_id, user_uuid):
    with _lock:
        homework = _load_homework(user_uuid)
        for hw in homework:
            if hw['id'] == homework_id:
                hw['completed'] = not bool(hw.get('completed', False))
                hw['completed_at'] = datetime.now().isoformat() if hw['completed'] else None
                _save_homework(user_uuid, homework)
                return True
    return False


def delete_old_completed_homework(user_uuid):
    cutoff = (datetime.now() - timedelta(days=1)).isoformat()
    with _lock:
        homework = _load_homework(user_uuid)
        homework = [
            hw for hw in homework
            if not (hw.get('completed') and hw.get('completed_at') and hw['completed_at'] < cutoff)
        ]
        _save_homework(user_uuid, homework)


# ---------------------------------------------------------------------------
# Memories
# ---------------------------------------------------------------------------

def _load_memories(user_uuid):
    path = os.path.join(get_user_dir(user_uuid), 'memories.json')
    return _load_json(path, [])


def _save_memories(user_uuid, memories):
    path = os.path.join(get_user_dir(user_uuid), 'memories.json')
    _save_json(path, memories)


def add_memory(user_uuid, content):
    with _lock:
        memories = _load_memories(user_uuid)
        if any(m['content'] == content for m in memories):
            return False
        memories.insert(0, {'id': str(uuid.uuid4()), 'content': content, 'created_at': datetime.now().isoformat()})
        _save_memories(user_uuid, memories)
    return True


def get_memories(user_uuid):
    return _load_memories(user_uuid)


def delete_memory(memory_id, user_uuid):
    with _lock:
        memories = _load_memories(user_uuid)
        memories = [m for m in memories if m['id'] != memory_id]
        _save_memories(user_uuid, memories)
    return True


def delete_memory_by_content(user_uuid, content):
    with _lock:
        memories = _load_memories(user_uuid)
        orig = len(memories)
        memories = [m for m in memories if m['content'] != content]
        if len(memories) < orig:
            _save_memories(user_uuid, memories)
            return True
    return False


# ---------------------------------------------------------------------------
# Data export / import for download
# ---------------------------------------------------------------------------

def export_user_data(user_uuid):
    """Return all user data as a dict suitable for JSON export."""
    return {
        'user': _load_user(user_uuid),
        'conversations': _load_conversations(user_uuid),
        'homework': _load_homework(user_uuid),
        'subjects': _load_subjects(user_uuid),
        'memories': _load_memories(user_uuid),
    }


# ---------------------------------------------------------------------------
# Migration from SQLite
# ---------------------------------------------------------------------------

def migrate_from_sqlite():
    """Migrate existing users.db data to file-based storage. Runs once on startup."""
    db_path = 'users.db'
    if not os.path.exists(db_path):
        return

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            conn.close()
            return

        # Check if already migrated (index has entries)
        index = _load_index()

        cursor.execute('SELECT id, username, password, user_type, school, class_name, math_solver, is_first_login, created_at FROM users')
        db_users = cursor.fetchall()
        if not db_users:
            conn.close()
            return

        migrated = 0
        for row in db_users:
            db_id, username, password, user_type, school, class_name, math_solver, is_first_login, created_at = row
            if username in index:
                continue  # Already migrated

            user_uuid = str(uuid.uuid4())
            user_dir = get_user_dir(user_uuid)
            os.makedirs(user_dir, exist_ok=True)

            user_data = {
                'uuid': user_uuid,
                'username': username,
                'password': password,
                'user_type': user_type,
                'school': school,
                'class_name': class_name,
                'math_solver': bool(math_solver),
                'is_first_login': bool(is_first_login),
                'created_at': created_at or datetime.now().isoformat(),
            }
            _save_json(os.path.join(user_dir, 'user.json'), user_data)

            # Migrate chat history
            conversations = []
            try:
                cursor.execute('''
                    SELECT session_id, session_name, chat_subject,
                           message_type, content, image_data, worksheet_filename, created_at
                    FROM chat_history WHERE user_id = ?
                    ORDER BY created_at ASC
                ''', (db_id,))
                rows = cursor.fetchall()
                sessions_map = {}
                for r in rows:
                    sid, sname, subj, mtype, content, img, ws, ts = r
                    if sid not in sessions_map:
                        sessions_map[sid] = {
                            'id': sid,
                            'name': sname or 'Neuer Chat',
                            'subject': subj,
                            'created_at': ts,
                            'updated_at': ts,
                            'messages': [],
                        }
                    msg = {'role': mtype, 'content': content, 'created_at': ts}
                    if img:
                        msg['image_data'] = img
                    if ws:
                        msg['worksheet_filename'] = ws
                    sessions_map[sid]['messages'].append(msg)
                conversations = list(sessions_map.values())
                conversations.sort(key=lambda s: s.get('updated_at') or '', reverse=True)
            except Exception:
                pass
            _save_json(os.path.join(user_dir, 'conversations.json'), conversations)

            # Migrate homework
            homework = []
            try:
                cursor.execute('''
                    SELECT h.id, h.title, h.due_date, h.notes, h.subject_id,
                           h.completed, h.completed_at, h.created_at
                    FROM homework h WHERE h.user_id = ?
                ''', (db_id,))
                for r in cursor.fetchall():
                    hid, title, due, notes, subj_id, completed, comp_at, ts = r
                    homework.append({
                        'id': str(hid),
                        'user_uuid': user_uuid,
                        'title': title,
                        'due_date': due,
                        'notes': notes,
                        'subject_id': str(subj_id) if subj_id else None,
                        'completed': bool(completed),
                        'completed_at': comp_at,
                        'created_at': ts,
                    })
            except Exception:
                pass
            _save_json(os.path.join(user_dir, 'homework.json'), homework)

            # Migrate subjects
            subjects = []
            try:
                cursor.execute('SELECT id, name, created_at FROM subjects WHERE user_id = ?', (db_id,))
                for r in cursor.fetchall():
                    subjects.append({'id': str(r[0]), 'name': r[1], 'created_at': r[2]})
            except Exception:
                pass
            _save_json(os.path.join(user_dir, 'subjects.json'), subjects)

            # Migrate memories
            memories = []
            try:
                cursor.execute('SELECT id, content, created_at FROM memories WHERE user_id = ?', (db_id,))
                for r in cursor.fetchall():
                    memories.append({'id': str(r[0]), 'content': r[1], 'created_at': r[2]})
            except Exception:
                pass
            _save_json(os.path.join(user_dir, 'memories.json'), memories)

            index[username] = user_uuid
            migrated += 1

        if migrated:
            _save_index(index)
            print(f"[user_storage] Migrated {migrated} user(s) from SQLite to file storage.")

        conn.close()

        # Rename DB so migration doesn't run again
        if migrated and os.path.exists(db_path):
            os.rename(db_path, db_path + '.migrated')

    except Exception as e:
        print(f"[user_storage] Migration error: {e}")
