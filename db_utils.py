import psycopg2, bcrypt, config, json
from sqlalchemy.engine.url import make_url


def get_db_connection():
    url = make_url(config.DATABASE_URL)
    return psycopg2.connect(
        user=url.username, password=url.password,
        host=url.host, port=url.port, database=url.database
    )


def init_db():
    conn = get_db_connection();
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS user_groups (id SERIAL PRIMARY KEY, group_name VARCHAR(100) UNIQUE NOT NULL);")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username VARCHAR(100) UNIQUE NOT NULL, hashed_password VARCHAR(100) NOT NULL, is_admin BOOLEAN DEFAULT FALSE);")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS collections (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, owner_username VARCHAR(100) NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS collection_files (id SERIAL PRIMARY KEY, collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE, file_name VARCHAR(255) NOT NULL);")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS permissions (id SERIAL PRIMARY KEY, collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE, target_username VARCHAR(100), target_group VARCHAR(100));")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS chat_archives (id SERIAL PRIMARY KEY, collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE, username VARCHAR(100) NOT NULL, history_json JSONB NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS active_chats (
            id SERIAL PRIMARY KEY, 
            collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE, 
            username VARCHAR(100) NOT NULL, 
            history_json JSONB NOT NULL, 
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(collection_id, username)
        );
    """)

    cur.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
        cur.execute("INSERT INTO users (username, hashed_password, is_admin) VALUES ('admin', %s, TRUE)", (hashed,))
    conn.commit();
    conn.close()


def verify_user(u, p):
    conn = get_db_connection();
    cur = conn.cursor()
    cur.execute("SELECT hashed_password, is_admin FROM users WHERE username = %s", (u,))
    r = cur.fetchone();
    conn.close()
    if r and bcrypt.checkpw(p.encode(), r[0].encode()): return True, r[1]
    return False, False


def create_user(u, p):
    try:
        conn = get_db_connection();
        cur = conn.cursor()
        hashed = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        cur.execute("INSERT INTO users (username, hashed_password) VALUES (%s, %s)", (u, hashed))
        conn.commit();
        conn.close();
        return True, "Zarejestrowano pomyślnie!"
    except:
        return False, "Użytkownik już istnieje."


def get_accessible_collections(username):
    conn = get_db_connection();
    cur = conn.cursor()
    query = "SELECT DISTINCT c.id, c.name, c.owner_username FROM collections c LEFT JOIN permissions p ON c.id = p.collection_id WHERE c.owner_username = %s OR p.target_username = %s"
    cur.execute(query, (username, username))
    res = cur.fetchall();
    conn.close();
    return res


def create_collection(name, owner, files):
    conn = get_db_connection();
    cur = conn.cursor()
    cur.execute("INSERT INTO collections (name, owner_username) VALUES (%s, %s) RETURNING id", (name, owner))
    cid = cur.fetchone()[0]
    for f in files: cur.execute("INSERT INTO collection_files (collection_id, file_name) VALUES (%s, %s)", (cid, f))
    conn.commit();
    conn.close();
    return cid


def get_collection_files(cid):
    conn = get_db_connection();
    cur = conn.cursor()
    cur.execute("SELECT file_name FROM collection_files WHERE collection_id = %s", (cid,))
    res = [r[0] for r in cur.fetchall()];
    conn.close();
    return res


def remove_file_from_collection(cid, fname):
    conn = get_db_connection();
    cur = conn.cursor()
    cur.execute("DELETE FROM collection_files WHERE collection_id = %s AND file_name = %s", (cid, fname))
    conn.commit();
    conn.close()


def delete_collection(cid):
    conn = get_db_connection();
    cur = conn.cursor()
    cur.execute("DELETE FROM collections WHERE id = %s", (cid,))
    conn.commit();
    conn.close()


def archive_chat(cid, user, history):
    conn = get_db_connection();
    cur = conn.cursor()
    cur.execute("INSERT INTO chat_archives (collection_id, username, history_json) VALUES (%s, %s, %s)",
                (cid, user, json.dumps(history)))
    cur.execute("DELETE FROM active_chats WHERE collection_id = %s AND username = %s", (cid, user))
    conn.commit();
    conn.close()


def get_user_history(user):
    conn = get_db_connection();
    cur = conn.cursor()
    query = "SELECT a.id, c.name, a.created_at FROM chat_archives a JOIN collections c ON a.collection_id = c.id WHERE a.username = %s ORDER BY a.created_at DESC"
    cur.execute(query, (user,))
    res = cur.fetchall();
    conn.close();
    return res


def get_archive_detail(archive_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT history_json FROM chat_archives WHERE id = %s", (archive_id,))
        res = cur.fetchone()
        conn.close()
        if res:
            data = res[0]
            if isinstance(data, (list, dict)): return data
            return json.loads(data)
        return None
    except Exception as e:
        print(f"Błąd pobierania szczegółów archiwum: {e}")
        return None


def share_collection_with_user(owner, collection_id, target_username):
    if owner == target_username:
        return False, "Nie możesz udostępnić kolekcji samemu sobie."
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = %s", (target_username,))
    if not cur.fetchone():
        conn.close()
        return False, f"Użytkownik {target_username} nie istnieje."
    cur.execute("SELECT id FROM permissions WHERE collection_id = %s AND target_username = %s",
                (collection_id, target_username))
    if cur.fetchone():
        conn.close()
        return False, f"Już udostępniono użytkownikowi {target_username}."
    try:
        cur.execute("INSERT INTO permissions (collection_id, target_username) VALUES (%s, %s)",
                    (collection_id, target_username))
        conn.commit()
        conn.close()
        return True, f"Kolekcja udostępniona dla {target_username}!"
    except Exception as e:
        conn.close()
        return False, f"Błąd bazy danych: {str(e)}"


def save_active_chat(cid, user, history):
    conn = get_db_connection()
    cur = conn.cursor()
    history_json = json.dumps(history)
    query = """
        INSERT INTO active_chats (collection_id, username, history_json, last_updated)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (collection_id, username) 
        DO UPDATE SET history_json = EXCLUDED.history_json, last_updated = CURRENT_TIMESTAMP;
    """
    cur.execute(query, (cid, user, history_json))
    conn.commit()
    conn.close()


def load_active_chat(cid, user):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT history_json FROM active_chats WHERE collection_id = %s AND username = %s", (cid, user))
    res = cur.fetchone()
    conn.close()
    if res:
        data = res[0]
        if isinstance(data, (list, dict)): return data
        return json.loads(data)
    return []


def delete_selected_archives(ids_list):
    if not ids_list: return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM chat_archives WHERE id IN %s", (tuple(ids_list),))
    conn.commit()
    conn.close()


def delete_all_user_archives(user):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM chat_archives WHERE username = %s", (user,))
    conn.commit()
    conn.close()


def get_collection_permissions(cid):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT target_username FROM permissions WHERE collection_id = %s", (cid,))
    res = [r[0] for r in cur.fetchall()]
    conn.close()
    return res


def revoke_permission(cid, username):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM permissions WHERE collection_id = %s AND target_username = %s", (cid, username))
    conn.commit()
    conn.close()


# --- NOWA FUNKCJA DODAJĄCA PLIK DO ISTNIEJĄCEJ KOLEKCJI ---
def add_file_to_collection(cid, filename):
    """Dodaje wpis o pliku do tabeli SQL."""
    conn = get_db_connection()
    cur = conn.cursor()
    # Sprawdź czy plik już nie istnieje w tej kolekcji (żeby nie było duplikatów na liście)
    cur.execute("SELECT id FROM collection_files WHERE collection_id = %s AND file_name = %s", (cid, filename))
    if not cur.fetchone():
        cur.execute("INSERT INTO collection_files (collection_id, file_name) VALUES (%s, %s)", (cid, filename))
    conn.commit()
    conn.close()


init_db()