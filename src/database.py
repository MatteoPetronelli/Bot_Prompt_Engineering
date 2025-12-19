import sqlite3
import json
import os

DB_FILE = os.path.join("../data", "bot.db")

def get_connection():
    """Crée une connexion à la base de données."""
    if not os.path.exists("../data"):
        os.makedirs("../data")
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialise les tables si elles n'existent pas."""
    conn = get_connection()
    c = conn.cursor()
    
    # Table 1 : Historique des commandes
    c.execute('''
        CREATE TABLE IF NOT EXISTS command_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            command TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table 2 : Sessions Actives (Arbres)
    c.execute('''
        CREATE TABLE IF NOT EXISTS active_sessions (
            user_id INTEGER PRIMARY KEY,
            tree_data TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS saved_prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, name) -- Empêche d'avoir 2 prompts avec le même nom
        )
    ''')
    
    conn.commit()
    conn.close()
    print("💾 Base de données SQLite initialisée.")

# --- GESTION HISTORIQUE ---

def add_history(user_id, command):
    conn = get_connection()
    conn.execute('INSERT INTO command_history (user_id, command) VALUES (?, ?)', (user_id, command))
    conn.commit()
    conn.close()

def get_user_history(user_id, limit=20):
    """Récupère les X dernières commandes."""
    conn = get_connection()
    cursor = conn.execute(
        'SELECT command FROM command_history WHERE user_id = ? ORDER BY id DESC LIMIT ?', 
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    # On inverse pour avoir l'ordre chronologique (plus vieux -> plus récent)
    return [row['command'] for row in rows][::-1]

def get_last_command(user_id):
    conn = get_connection()
    cursor = conn.execute(
        'SELECT command FROM command_history WHERE user_id = ? ORDER BY id DESC LIMIT 2', 
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    # On veut l'avant-dernière (car la dernière est la commande /last elle-même)
    if len(rows) >= 2:
        return rows[1]['command']
    return None

def clear_user_history(user_id):
    conn = get_connection()
    conn.execute('DELETE FROM command_history WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# --- GESTION SESSIONS (ARBRES) ---

def save_session(user_id, tree_object):
    """Sauvegarde un objet DialogueTree dans la DB."""
    conn = get_connection()
    
    tree_json = json.dumps(tree_object.to_dict())
    
    # UPSERT (Insert ou Update si existe déjà)
    conn.execute('''
        INSERT INTO active_sessions (user_id, tree_data) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET tree_data=excluded.tree_data
    ''', (user_id, tree_json))
    
    conn.commit()
    conn.close()

def load_session(user_id):
    """Charge le JSON depuis la DB et retourne les données brutes."""
    conn = get_connection()
    cursor = conn.execute('SELECT tree_data FROM active_sessions WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return json.loads(row['tree_data'])
    return None

def delete_session(user_id):
    conn = get_connection()
    conn.execute('DELETE FROM active_sessions WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# --- GESTION BIBLIOTHÈQUE (SAVED PROMPTS) ---

def save_prompt_to_library(user_id, name, content):
    conn = get_connection()
    try:
        conn.execute(
            'INSERT INTO saved_prompts (user_id, name, content) VALUES (?, ?, ?)', 
            (user_id, name, content)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_all_prompts_names(user_id):
    """Retourne la liste des noms des prompts sauvegardés pour l'autocomplétion."""
    conn = get_connection()
    cursor = conn.execute('SELECT name FROM saved_prompts WHERE user_id = ? ORDER BY name ASC', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row['name'] for row in rows]

def get_prompt_content(user_id, name):
    conn = get_connection()
    cursor = conn.execute('SELECT content FROM saved_prompts WHERE user_id = ? AND name = ?', (user_id, name))
    row = cursor.fetchone()
    conn.close()
    return row['content'] if row else None

def delete_prompt_from_library(user_id, name):
    conn = get_connection()
    cursor = conn.execute('DELETE FROM saved_prompts WHERE user_id = ? AND name = ?', (user_id, name))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted