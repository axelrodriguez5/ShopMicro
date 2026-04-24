from flask import Flask, jsonify, request
import mysql.connector
import hashlib
import os
import time
import json

app = Flask(__name__)

DB_HOST = os.getenv("DB_HOST", "db-orders")
DB_USER = os.getenv("DB_USER", "shopuser")
DB_PASS = os.getenv("DB_PASSWORD", "shoppass")
DB_NAME = os.getenv("DB_NAME", "orders_db")
SECRET   = os.getenv("JWT_SECRET", "supersecret")

def get_db():
    for _ in range(10):
        try:
            return mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
        except Exception:
            time.sleep(2)
    raise Exception("No s'ha pogut connectar")

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(64) NOT NULL,
            email VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    # Usuari de mostra
    try:
        ph = hashlib.sha256("password123".encode()).hexdigest()
        cur.execute("INSERT INTO users (username, password_hash, email) VALUES (%s,%s,%s)",
                    ("user1", ph, "user1@shopmicro.cat"))
        conn.commit()
    except Exception:
        pass
    cur.close()
    conn.close()

def make_token(user_id, username):
    """Token JWT minimal simulat (base64 sense signatura real per simplicitat)."""
    import base64
    payload = json.dumps({"user_id": user_id, "username": username, "iat": int(time.time())})
    token = base64.b64encode(payload.encode()).decode()
    return f"eyJhbGciOiJub25lIn0.{token}.sig"

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    email    = data.get("email", "")
    if not username or not password:
        return jsonify({"error": "username i password obligatoris"}), 400
    ph = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password_hash, email) VALUES (%s,%s,%s)", (username, ph, email))
        conn.commit()
        uid = cur.lastrowid
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Usuari ja existeix"}), 409
    finally:
        cur.close(); conn.close()
    return jsonify({"id": uid, "username": username, "message": "Registre completat"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    ph = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE username = %s AND password_hash = %s", (username, ph))
    user = cur.fetchone()
    cur.close(); conn.close()
    if not user:
        return jsonify({"error": "Credencials incorrectes"}), 401
    token = make_token(user["id"], user["username"])
    return jsonify({"token": token, "user_id": user["id"], "username": user["username"]})

@app.route("/users", methods=["GET"])
def list_users():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, username, email, created_at FROM users")
    users = cur.fetchall()
    cur.close(); conn.close()
    for u in users:
        if u.get("created_at"):
            u["created_at"] = str(u["created_at"])
    return jsonify(users)

if __name__ == "__main__":
    time.sleep(8)
    init_db()
    app.run(host="0.0.0.0", port=5003, debug=True)