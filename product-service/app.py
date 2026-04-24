from flask import Flask, jsonify, request
import mysql.connector
import redis
import os
import json
import time

app = Flask(__name__)

# Configuració
REDIS_HOST = os.getenv("REDIS_HOST", "cache")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_TTL  = int(os.getenv("REDIS_TTL", 60))

DB_HOST = os.getenv("DB_HOST", "db-products")
DB_USER = os.getenv("DB_USER", "shopuser")
DB_PASS = os.getenv("DB_PASSWORD", "shoppass")
DB_NAME = os.getenv("DB_NAME", "products_db")

def get_db():
    for _ in range(10):
        try:
            return mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
        except Exception:
            time.sleep(2)
    raise Exception("No s'ha pogut connectar a la BD")

def get_redis():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            stock INT NOT NULL DEFAULT 0
        )
    """)
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        sample = [
            ("Laptop Pro 15", "Processador Intel i7, 16GB RAM, 512GB SSD", 1299.99, 10),
            ("Teclat Mecànic RGB", "Switches Cherry MX Red, retroil·luminat", 89.99, 25),
            ("Monitor 4K 27\"", "Panel IPS, 144Hz, HDR400", 449.99, 8),
            ("Auriculars BT Pro", "Noise Cancelling, 30h bateria", 199.99, 15),
            ("Ratolí Gaming", "16000 DPI, 7 botons programmables", 59.99, 30),
            ("Webcam 1080p", "Autofocus, microfon integrat", 79.99, 0),
        ]
        cur.executemany("INSERT INTO products (name, description, price, stock) VALUES (%s,%s,%s,%s)", sample)
        conn.commit()
    cur.close()
    conn.close()

@app.route("/", methods=["GET"])
def list_products():
    cache_key = "products:all"
    try:
        r = get_redis()
        cached = r.get(cache_key)
        if cached:
            app.logger.info("Cache HIT → retornant des de Redis")
            products = json.loads(cached)
            return jsonify(products)
    except Exception as e:
        app.logger.warning(f"Redis no disponible: {e}")

    app.logger.info("Cache MISS → consultant db-products")
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    cur.close()
    conn.close()
    for p in products:
        p["price"] = float(p["price"])

    try:
        r = get_redis()
        r.setex(cache_key, REDIS_TTL, json.dumps(products))
        app.logger.info(f"Resultat desat a Redis (TTL={REDIS_TTL}s)")
    except Exception:
        pass

    return jsonify(products)

@app.route("/<int:product_id>", methods=["GET"])
def get_product(product_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    p = cur.fetchone()
    cur.close()
    conn.close()
    if not p:
        return jsonify({"error": "Producte no trobat"}), 404
    p["price"] = float(p["price"])
    return jsonify(p)

@app.route("/", methods=["POST"])
def create_product():
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO products (name, description, price, stock) VALUES (%s,%s,%s,%s)",
        (data["name"], data.get("description",""), data["price"], data.get("stock",0))
    )
    conn.commit()
    pid = cur.lastrowid
    cur.close()
    conn.close()
    try:
        get_redis().delete("products:all")
    except Exception:
        pass
    return jsonify({"id": pid, "message": "Producte creat"}), 201

@app.route("/update-stock", methods=["POST"])
def update_stock():
    """Endpoint intern usat per order-service per descomptar stock."""
    data = request.json
    product_id = data["product_id"]
    quantity = data["quantity"]
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT stock FROM products WHERE id = %s", (product_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return jsonify({"error": "Producte no trobat"}), 404
    if row["stock"] < quantity:
        cur.close(); conn.close()
        return jsonify({"error": "Stock insuficient"}), 400
    cur.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (quantity, product_id))
    conn.commit()
    cur.close()
    conn.close()
    try:
        get_redis().delete("products:all")
    except Exception:
        pass
    return jsonify({"message": "Stock actualitzat", "product_id": product_id})

if __name__ == "__main__":
    time.sleep(5)
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)