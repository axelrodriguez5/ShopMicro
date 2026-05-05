from flask import Flask, jsonify, request
import mysql.connector, redis, json, os, time

app = Flask(__name__)

def read_secret(name, fallback_env=None):
    """Llegeix un secret de /run/secrets/<name>.
    Si no existeix, llegeix de la variable d'entorn (per compatibilitat amb Compose)."""
    secret_path = f'/run/secrets/{name}'
    if os.path.exists(secret_path):
        with open(secret_path, 'r') as f:
            return f.read().strip()
    if fallback_env and fallback_env in os.environ:
        return os.environ[fallback_env]
    raise RuntimeError(f"Secret '{name}' no trobat ni a /run/secrets/ ni com a variable {fallback_env}")

# Carreguem les credencials un sol cop a l'arrencada
DB_PASSWORD = read_secret('db_user_password', 'DB_PASSWORD')

def init_db():
    for i in range(30):
        try:
            conn = mysql.connector.connect(
                host=os.environ['DB_HOST'],
                user=os.environ['DB_USER'],
                password=DB_PASSWORD,                 # ← canviat
                database=os.environ['DB_NAME'])
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS products(
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100), price DECIMAL(10,2), stock INT)""")
            cur.execute("SELECT COUNT(*) FROM products")
            if cur.fetchone()[0] == 0:
                cur.executemany(
                    "INSERT INTO products(name,price,stock) VALUES(%s,%s,%s)",
                    [("Portàtil",899.99,10),("Ratolí",19.99,50),("Teclat",49.99,30)])
            conn.commit(); conn.close()
            print("[init_db] Taula 'products' inicialitzada correctament", flush=True)
            return
        except Exception as e:
            print(f"[init_db] Intent {i+1}/30 fallit: {e}", flush=True)
            time.sleep(5)
    print("[init_db] AVÍS: no s'ha pogut inicialitzar la BD products", flush=True)

r = redis.Redis(host=os.environ['REDIS_HOST'], port=6379, decode_responses=True)

@app.route('/products', methods=['GET'])
def list_products():
    cached = r.get('products')
    if cached:
        return jsonify({"source": "cache", "data": json.loads(cached)})
    conn = mysql.connector.connect(
        host=os.environ['DB_HOST'], user=os.environ['DB_USER'],
        password=DB_PASSWORD,                          # ← canviat
        database=os.environ['DB_NAME'])
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    for p in products: p['price'] = float(p['price'])
    conn.close()
    r.setex('products', 60, json.dumps(products))
    return jsonify({"source": "db", "data": products})

@app.route('/health')
def health(): return {"status": "ok"}

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)