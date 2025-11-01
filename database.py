import sqlite3
import os
import json

DATABASE_PATH = 'users.db'

def init_database():
    """Initialize the database with users and chat_history tables"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            user_type TEXT NOT NULL CHECK (user_type IN ('teacher', 'student', 'it-admin')),
            class_name TEXT,
            school TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create assignments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            class_name TEXT NOT NULL,
            school TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')

    # Add school column to assignments table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE assignments ADD COLUMN school TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' not in str(e):
            raise

    # Create submissions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (student_id) REFERENCES users (id)
        )
    ''')

    # Create chat_history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            session_name TEXT,
            message_type TEXT NOT NULL CHECK (message_type IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            image_data TEXT,
            worksheet_filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Add worksheet_filename column to chat_history table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE chat_history ADD COLUMN worksheet_filename TEXT")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' not in str(e):
            pass # Column already exists

    conn.commit()
    conn.close()

def create_user(username, password, user_type, school=None):
    """Create a new user"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        if user_type == 'it-admin':
            cursor.execute('SELECT id FROM users WHERE user_type = ? AND school = ?', ('it-admin', school))
            if cursor.fetchone():
                return False  # IT admin for this school already exists

        cursor.execute('INSERT INTO users (username, password, user_type, school) VALUES (?, ?, ?, ?)',
                      (username, password, user_type, school))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Username already exists
    finally:
        conn.close()

def get_user(username, password):
    """Get user by username and password"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT id, username, user_type, class_name, school FROM users WHERE username = ? AND password = ?',
                  (username, password))
    user = cursor.fetchone()
    conn.close()

    if user:
        return {'id': user[0], 'username': user[1], 'user_type': user[2], 'class_name': user[3], 'school': user[4]}
    return None

def get_user_by_username(username):
    """Get user by username"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT id, username, user_type, class_name, school FROM users WHERE username = ?',
                  (username,))
    user = cursor.fetchone()
    conn.close()

    if user:
        return {'id': user[0], 'username': user[1], 'user_type': user[2], 'class_name': user[3], 'school': user[4]}
    return None

def assign_teacher_to_class(teacher_username, class_name):
    """Assign a teacher to a class"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute('UPDATE users SET class_name = ? WHERE username = ? AND user_type = \'teacher\'', (class_name, teacher_username))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

def add_student_to_class(student_username, class_name):
    """Add a student to a class"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute('UPDATE users SET class_name = ? WHERE username = ? AND user_type = \'student\'', (class_name, student_username))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

def get_teachers_for_school(school):
    """Get all teachers for a school"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT id, username, class_name FROM users WHERE user_type = \'teacher\' AND school = ?', (school,))
    teachers = cursor.fetchall()
    conn.close()

    return [{'id': t[0], 'username': t[1], 'class_name': t[2]} for t in teachers]

def get_students_for_school(school):
    """Get all students for a school"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT id, username, class_name FROM users WHERE user_type = \'student\' AND school = ?', (school,))
    students = cursor.fetchall()
    conn.close()

    return [{'id': s[0], 'username': s[1], 'class_name': s[2]} for s in students]

def get_all_users():
    """Get all users (for admin purposes)"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT id, username, password, user_type, created_at FROM users')
    users = cursor.fetchall()
    conn.close()

    return [{'id': u[0], 'username': u[1], 'password': u[2], 'user_type': u[3], 'created_at': u[4]} for u in users]

def save_chat_message(user_id, session_id, message_type, content, image_data=None, worksheet_filename=None):
    """Save a chat message to the database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO chat_history (user_id, session_id, message_type, content, image_data, worksheet_filename)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, session_id, message_type, content, image_data, worksheet_filename))

    conn.commit()
    conn.close()

def get_chat_history(user_id, session_id):
    """Get chat history for a specific user and session"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT message_type, content, image_data, worksheet_filename, created_at
        FROM chat_history
        WHERE user_id = ? AND session_id = ?
        ORDER BY created_at ASC
    ''', (user_id, session_id))

    messages = cursor.fetchall()
    conn.close()

    return [{'message_type': m[0], 'content': m[1], 'image_data': m[2], 'worksheet_filename': m[3], 'created_at': m[4]} for m in messages]

def get_user_chat_sessions(user_id):
    """Get all chat sessions for a user"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT 
            session_id, 
            MIN(created_at) as first_message, 
            MAX(created_at) as last_message,
            COALESCE(session_name, content) as session_name
        FROM chat_history
        WHERE user_id = ?
        GROUP BY session_id
        ORDER BY last_message DESC
    ''', (user_id,))

    sessions = cursor.fetchall()
    conn.close()

    return [{'session_id': s[0], 'first_message': s[1], 'last_message': s[2], 'session_name': s[3]} for s in sessions]

def delete_chat_session(user_id, session_id):
    """Delete a chat session for a user"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute('DELETE FROM chat_history WHERE user_id = ? AND session_id = ?', (user_id, session_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

def rename_chat_session(user_id, session_id, new_name):
    """Rename a chat session for a user"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute('UPDATE chat_history SET session_name = ? WHERE user_id = ? AND session_id = ?', (new_name, user_id, session_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

def create_assignment(title, description, created_by, class_name, school):
    """Create a new assignment"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute('INSERT INTO assignments (title, description, created_by, class_name, school) VALUES (?, ?, ?, ?, ?)',
                      (title, description, created_by, class_name, school))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

def get_assignments_for_class(class_name, school):
    """Get all assignments for a given class and school"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT id, title, description, created_at FROM assignments WHERE class_name = ? AND school = ? ORDER BY created_at DESC',
                  (class_name, school))
    assignments = cursor.fetchall()
    conn.close()

    return [{'id': a[0], 'title': a[1], 'description': a[2], 'created_at': a[3]} for a in assignments]

def get_assignment(assignment_id):
    """Get a single assignment by its ID"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT id, title, description, created_at FROM assignments WHERE id = ?',
                  (assignment_id,))
    assignment = cursor.fetchone()
    conn.close()

    if assignment:
        return {'id': assignment[0], 'title': assignment[1], 'description': assignment[2], 'created_at': assignment[3]}
    return None

def delete_assignment(assignment_id):
    """Delete an assignment and all its submissions"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # First, delete all submissions for this assignment
        cursor.execute('DELETE FROM submissions WHERE assignment_id = ?', (assignment_id,))

        # Then, delete the assignment itself
        cursor.execute('DELETE FROM assignments WHERE id = ?', (assignment_id,))

        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

def create_submission(assignment_id, student_id, content):
    """Create a new submission"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute('INSERT INTO submissions (assignment_id, student_id, content) VALUES (?, ?, ?)',
                      (assignment_id, student_id, content))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

def get_submissions_for_assignment(assignment_id):
    """Get all submissions for a given assignment"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT s.id, s.content, s.submitted_at, u.username
        FROM submissions s
        JOIN users u ON s.student_id = u.id
        WHERE s.assignment_id = ?
        ORDER BY s.submitted_at DESC
    ''', (assignment_id,))
    submissions = cursor.fetchall()
    conn.close()

    return [{'id': s[0], 'content': s[1], 'submitted_at': s[2], 'student_username': s[3]} for s in submissions]

def get_submission_for_user(assignment_id, student_id):
    """Get a submission for a specific user and assignment"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT id, content, submitted_at FROM submissions WHERE assignment_id = ? AND student_id = ?',
                  (assignment_id, student_id))
    submission = cursor.fetchone()
    conn.close()

    if submission:
        return {'id': submission[0], 'content': submission[1], 'submitted_at': submission[2]}
    return None

def get_unique_school_names():
    """Get a list of unique school names"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT DISTINCT school FROM users WHERE school IS NOT NULL')
    schools = cursor.fetchall()
    conn.close()

    return [s[0] for s in schools]

def get_student_usernames_for_school(school):
    """Get a list of student usernames for a given school"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT username FROM users WHERE school = ? AND user_type = \'student\'', (school,))
    students = cursor.fetchall()
    conn.close()

    return [s[0] for s in students]

def get_unique_class_names_for_school(school):
    """Get a list of unique class names for a given school"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT DISTINCT class_name FROM users WHERE school = ? AND class_name IS NOT NULL', (school,))
    classes = cursor.fetchall()
    conn.close()

    return [c[0] for c in classes]

def get_teacher_usernames_for_school(school):
    """Get a list of teacher usernames for a given school"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT username FROM users WHERE school = ? AND user_type = \'teacher\'', (school,))
    teachers = cursor.fetchall()
    conn.close()

    return [t[0] for t in teachers]