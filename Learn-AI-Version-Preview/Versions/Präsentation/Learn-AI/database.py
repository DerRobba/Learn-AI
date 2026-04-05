"""
Minimal SQLite database module.
Only handles assignments and submissions (cross-user data).
All user-specific data (profiles, conversations, homework, subjects, memories)
is now managed by user_storage.py.
"""

import sqlite3

DATABASE_PATH = 'assignments.db'


def init_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_by TEXT NOT NULL,
            class_name TEXT NOT NULL,
            school TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            content TEXT NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_assignments_class_school ON assignments(class_name, school)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_assignment ON submissions(assignment_id)')

    conn.commit()
    conn.close()


def create_assignment(title, description, created_by, class_name, school):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO assignments (title, description, created_by, class_name, school) VALUES (?, ?, ?, ?, ?)',
            (title, description, str(created_by), class_name, school)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()


def get_assignments_for_class(class_name, school):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, title, description, created_at FROM assignments WHERE class_name = ? AND school = ? ORDER BY created_at DESC',
        (class_name, school)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{'id': r[0], 'title': r[1], 'description': r[2], 'created_at': r[3]} for r in rows]


def get_assignment(assignment_id):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, description, created_at FROM assignments WHERE id = ?', (assignment_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {'id': row[0], 'title': row[1], 'description': row[2], 'created_at': row[3]}
    return None


def delete_assignment(assignment_id):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM submissions WHERE assignment_id = ?', (assignment_id,))
        cursor.execute('DELETE FROM assignments WHERE id = ?', (assignment_id,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()


def create_submission(assignment_id, student_id, content):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO submissions (assignment_id, student_id, content) VALUES (?, ?, ?)',
            (assignment_id, str(student_id), content)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()


def get_submissions_for_assignment(assignment_id):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, content, submitted_at, student_id FROM submissions WHERE assignment_id = ? ORDER BY submitted_at DESC',
        (assignment_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{'id': r[0], 'content': r[1], 'submitted_at': r[2], 'student_username': r[3]} for r in rows]


def get_submission_for_user(assignment_id, student_id):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, content, submitted_at FROM submissions WHERE assignment_id = ? AND student_id = ?',
        (assignment_id, str(student_id))
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {'id': row[0], 'content': row[1], 'submitted_at': row[2]}
    return None
