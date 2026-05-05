from flask import Flask, jsonify, request
import mysql.connector, jwt, hashlib, os, time, datetime

app = Flask(__name__)
JWT_SECRET = os.environ['JWT_SECRET']

def get_conn():
    return mysql.connector.connect(
        host=os.environ['DB_HOST'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        database=os.environ['DB_NAME'])

# Inicialitzem la taula d'usuaris amb reintents robustos
def init_db():
    for i in range(30):
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS users(
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE,
                password_hash VARCHAR(64))""")
            conn.commit(); conn.close()
            print("[init_db] Taula 'users' inicialitzada correctament", flush=True)
            return
        except Exception as e:
            print(f"[init_db] Intent {i+1}/30 fallit: {e}", flush=True)
            time.sleep(5)
    print("[init_db] AVÍS: no s'ha pogut inicialitzar la BD users", flush=True)

def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

@app.route('/users/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({"error": "username i password obligatoris"}), 400
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO users(username, password_hash) VALUES(%s, %s)",
                    (username, hash_pwd(password)))
        conn.commit(); conn.close()
        return jsonify({"message": "Usuari registrat", "username": username}), 201
    except mysql.connector.errors.IntegrityError:
        return jsonify({"error": "Usuari ja existeix"}), 409

@app.route('/users/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE username=%s AND password_hash=%s",
                (username, hash_pwd(password)))
    user = cur.fetchone()
    conn.close()
    if not user:
        return jsonify({"error": "Credencials incorrectes"}), 401
    # Generem token JWT vàlid 1 hora
    token = jwt.encode({
        "user_id": user['id'],
        "username": user['username'],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }, JWT_SECRET, algorithm="HS256")
    return jsonify({"token": token})

@app.route('/users', methods=['GET'])
def list_users():
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, username FROM users")
    users = cur.fetchall()
    conn.close()
    return jsonify(users)

@app.route('/health')
def health(): return {"status": "ok"}

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)