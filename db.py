"""
Database module for BLG Exam application using SQLite.
Handles users, pools, progress, gamestates, and sessions.
"""

import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime

DB_PATH = "data/blg_exam.db"


def ensure_db_dir():
    """Ensure the data directory exists."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def get_db():
    """Context manager for database connections."""
    ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database tables."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Pools table - stores uploaded problem sets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pools (
                id TEXT PRIMARY KEY,
                username TEXT,
                orig_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
            )
        """)
        
        # Progress table - tracks question progress per user per pool
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                pool_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                box INTEGER DEFAULT 1,
                correct_streak INTEGER DEFAULT 0,
                incorrect_count INTEGER DEFAULT 0,
                last_seen TIMESTAMP,
                due TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(username, pool_id, question_id),
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (pool_id) REFERENCES pools(id) ON DELETE CASCADE
            )
        """)
        
        # Gamestates table - stores points, ranks, streaks per user
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gamestates (
                username TEXT PRIMARY KEY,
                points INTEGER DEFAULT 0,
                rank TEXT DEFAULT 'Unranked',
                answer_streak INTEGER DEFAULT 0,
                daily_streak INTEGER DEFAULT 0,
                last_active TIMESTAMP,
                badges TEXT,  -- JSON array of badges
                history TEXT,  -- JSON array of point history
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
            )
        """)
        
        # Sessions table - tracks active quiz sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                sid TEXT PRIMARY KEY,
                username TEXT,
                pool_id TEXT NOT NULL,
                pool_data TEXT NOT NULL,  -- JSON of pool questions
                exam_set TEXT NOT NULL,  -- JSON of current exam set
                wrong_set TEXT,  -- JSON of wrong answers for review
                current_index INTEGER DEFAULT 0,
                num_questions INTEGER,
                progress_data TEXT,  -- JSON of current session progress
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE,
                FOREIGN KEY (pool_id) REFERENCES pools(id) ON DELETE SET NULL
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pools_username ON pools(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_user_pool ON progress(username, pool_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username)")
        
        conn.commit()


# ==================== User Functions ====================

def create_user(username, password_hash):
    """Create a new user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        # Create initial gamestate for user
        cursor.execute(
            "INSERT INTO gamestates (username, points, rank) VALUES (?, 0, 'Unranked')",
            (username,)
        )
    return True


def get_user(username):
    """Get user by username."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_users():
    """Get all users (username -> password_hash mapping)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, password_hash FROM users")
        rows = cursor.fetchall()
        return {row['username']: row['password_hash'] for row in rows}


# ==================== Pool Functions ====================

def create_pool(pool_id, username, orig_name, file_path):
    """Create a new pool (uploaded problem set)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO pools (id, username, orig_name, file_path) VALUES (?, ?, ?, ?)",
            (pool_id, username, orig_name, file_path)
        )
    return True


def get_pools(username=None):
    """Get all pools, optionally filtered by username."""
    with get_db() as conn:
        cursor = conn.cursor()
        if username:
            # Get both global pools (username IS NULL) and user's pools
            cursor.execute(
                "SELECT * FROM pools WHERE username IS NULL OR username = ? ORDER BY created_at DESC",
                (username,)
            )
        else:
            cursor.execute("SELECT * FROM pools ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_pool(pool_id):
    """Get a specific pool by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pools WHERE id = ?", (pool_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_pool(pool_id):
    """Delete a pool and its associated progress."""
    with get_db() as conn:
        cursor = conn.cursor()
        # Get file path before deleting
        cursor.execute("SELECT file_path FROM pools WHERE id = ?", (pool_id,))
        row = cursor.fetchone()
        file_path = row['file_path'] if row else None
        
        # Delete pool (progress will cascade delete)
        cursor.execute("DELETE FROM pools WHERE id = ?", (pool_id,))
        
        # Delete the file if it exists
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
    return True


def update_pool_name(pool_id, new_name):
    """Update pool name."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE pools SET orig_name = ? WHERE id = ?",
            (new_name, pool_id)
        )
    return True


# ==================== Progress Functions ====================

def get_progress(username, pool_id):
    """Get all progress for a user in a specific pool."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM progress WHERE username = ? AND pool_id = ?",
            (username, pool_id)
        )
        rows = cursor.fetchall()
        # Return as dict: question_id -> CardState-like dict
        result = {}
        for row in rows:
            result[row['question_id']] = {
                'box': row['box'],
                'correct_streak': row['correct_streak'],
                'incorrect_count': row['incorrect_count'],
                'last_seen': row['last_seen'],
                'due': row['due']
            }
        return result


def update_progress(username, pool_id, question_id, card_state):
    """Update progress for a specific question."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO progress (username, pool_id, question_id, box, correct_streak, 
                                 incorrect_count, last_seen, due, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(username, pool_id, question_id) 
            DO UPDATE SET
                box = excluded.box,
                correct_streak = excluded.correct_streak,
                incorrect_count = excluded.incorrect_count,
                last_seen = excluded.last_seen,
                due = excluded.due,
                updated_at = CURRENT_TIMESTAMP
        """, (username, pool_id, question_id, card_state['box'], 
              card_state['correct_streak'], card_state['incorrect_count'],
              card_state['last_seen'], card_state['due']))
    return True


def save_bulk_progress(username, pool_id, progress_dict):
    """Save multiple progress records at once."""
    with get_db() as conn:
        cursor = conn.cursor()
        for question_id, card_state in progress_dict.items():
            cursor.execute("""
                INSERT INTO progress (username, pool_id, question_id, box, correct_streak, 
                                     incorrect_count, last_seen, due, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(username, pool_id, question_id) 
                DO UPDATE SET
                    box = excluded.box,
                    correct_streak = excluded.correct_streak,
                    incorrect_count = excluded.incorrect_count,
                    last_seen = excluded.last_seen,
                    due = excluded.due,
                    updated_at = CURRENT_TIMESTAMP
            """, (username, pool_id, question_id, card_state['box'], 
                  card_state['correct_streak'], card_state['incorrect_count'],
                  card_state['last_seen'], card_state['due']))
    return True


# ==================== Gamestate Functions ====================

def get_gamestate(username):
    """Get gamestate for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gamestates WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            gs = dict(row)
            # Parse JSON fields
            gs['badges'] = json.loads(gs.get('badges') or '[]')
            gs['history'] = json.loads(gs.get('history') or '[]')
            return gs
        else:
            # Create default gamestate if doesn't exist
            cursor.execute(
                "INSERT INTO gamestates (username, points, rank) VALUES (?, 0, 'Unranked')",
                (username,)
            )
            conn.commit()
            return {
                'username': username,
                'points': 0,
                'rank': 'Unranked',
                'answer_streak': 0,
                'daily_streak': 0,
                'last_active': None,
                'badges': [],
                'history': []
            }


def update_gamestate(username, gamestate_dict):
    """Update gamestate for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE gamestates 
            SET points = ?, rank = ?, answer_streak = ?, daily_streak = ?,
                last_active = ?, badges = ?, history = ?
            WHERE username = ?
        """, (
            gamestate_dict.get('points', 0),
            gamestate_dict.get('rank', 'Unranked'),
            gamestate_dict.get('answer_streak', 0),
            gamestate_dict.get('daily_streak', 0),
            gamestate_dict.get('last_active'),
            json.dumps(gamestate_dict.get('badges', [])),
            json.dumps(gamestate_dict.get('history', [])),
            username
        ))
    return True


def get_leaderboard():
    """Get all users sorted by points for leaderboard."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, points, rank, daily_streak
            FROM gamestates
            ORDER BY points DESC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


# ==================== Session Functions ====================

def create_session(sid, username, pool_id, pool_data, exam_set, num_questions, progress_data):
    """Create a new quiz session."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sessions (sid, username, pool_id, pool_data, exam_set, 
                                 wrong_set, current_index, num_questions, progress_data)
            VALUES (?, ?, ?, ?, ?, '[]', 0, ?, ?)
        """, (sid, username, pool_id, json.dumps(pool_data), json.dumps(exam_set),
              num_questions, json.dumps(progress_data)))
    return True


def get_session(sid):
    """Get session by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE sid = ?", (sid,))
        row = cursor.fetchone()
        if row:
            session_data = dict(row)
            # Parse JSON fields
            session_data['pool'] = json.loads(session_data['pool_data'])
            session_data['set'] = json.loads(session_data['exam_set'])
            session_data['wrong'] = json.loads(session_data.get('wrong_set') or '[]')
            session_data['index'] = session_data['current_index']
            session_data['num'] = session_data['num_questions']
            session_data['progress'] = json.loads(session_data.get('progress_data') or '{}')
            return session_data
        return None


def update_session(sid, session_data):
    """Update session state."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sessions
            SET pool_data = ?, exam_set = ?, wrong_set = ?, current_index = ?,
                progress_data = ?, updated_at = CURRENT_TIMESTAMP
            WHERE sid = ?
        """, (
            json.dumps(session_data.get('pool', [])),
            json.dumps(session_data.get('set', [])),
            json.dumps(session_data.get('wrong', [])),
            session_data.get('index', 0),
            json.dumps(session_data.get('progress', {})),
            sid
        ))
    return True


def delete_session(sid):
    """Delete a session."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE sid = ?", (sid,))
    return True


# ==================== Migration from JSON ====================

def migrate_from_json():
    """Migrate existing JSON data to SQLite database."""
    import json as _json
    
    print("Starting migration from JSON to SQLite...")
    
    # Initialize database
    init_db()
    
    # Migrate users
    users_file = "data/users.json"
    if os.path.exists(users_file):
        try:
            with open(users_file, 'r') as f:
                users = _json.load(f)
            for username, user_data in users.items():
                try:
                    # Handle both dict format {'pw': 'hash'} and string format
                    if isinstance(user_data, dict):
                        password_hash = user_data.get('pw', '')
                    else:
                        password_hash = user_data
                    create_user(username, password_hash)
                    print(f"Migrated user: {username}")
                except Exception as e:
                    print(f"Skipping user {username}: {e}")
        except Exception as e:
            print(f"Error migrating users: {e}")
    
    # Migrate pools
    pools_file = "data/pools.json"
    if os.path.exists(pools_file):
        try:
            with open(pools_file, 'r') as f:
                pools = _json.load(f) or []
            for pool in pools:
                try:
                    create_pool(
                        pool['id'],
                        None,  # global pool
                        pool['orig_name'],
                        pool['path']
                    )
                    print(f"Migrated pool: {pool['orig_name']}")
                except Exception as e:
                    print(f"Skipping pool {pool.get('id')}: {e}")
        except Exception as e:
            print(f"Error migrating pools: {e}")
    
    # Migrate user-specific pools
    data_dir = "data"
    if os.path.exists(data_dir):
        for filename in os.listdir(data_dir):
            if filename.startswith("pools_") and filename.endswith(".json"):
                username = filename[6:-5]  # Remove "pools_" and ".json"
                try:
                    with open(os.path.join(data_dir, filename), 'r') as f:
                        user_pools = _json.load(f) or []
                    for pool in user_pools:
                        try:
                            create_pool(
                                pool['id'],
                                username,
                                pool['orig_name'],
                                pool['path']
                            )
                            print(f"Migrated user pool for {username}: {pool['orig_name']}")
                        except Exception as e:
                            print(f"Skipping user pool: {e}")
                except Exception as e:
                    print(f"Error migrating user pools for {username}: {e}")
    
    print("Migration complete!")


if __name__ == "__main__":
    # Initialize database and optionally migrate
    init_db()
    print("Database initialized successfully!")
    
    # Uncomment to run migration
    # migrate_from_json()
