from flask import Flask, jsonify, request
import mysql.connector, redis, json, os, time

app = Flask(__name__)

# Esperem a que MySQL estigui llest i creem la taula
def init_db():
    for _ in range(10):
        try:
            conn = mysql.connector.connect(
                host=os.environ['DB_HOST'],
                user=os.environ['DB_USER'],
                password=os.environ['DB_PASSWORD'],
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
            conn.commit(); conn.close(); return
        except Exception as e:
            print("Esperant DB...", e); time.sleep(3)

r = redis.Redis(host=os.environ['REDIS_HOST'], port=6379, decode_responses=True)

@app.route('/products', methods=['GET'])
def list_products():
    cached = r.get('products')
    if cached:
        return jsonify({"source": "cache", "data": json.loads(cached)})
    conn = mysql.connector.connect(
        host=os.environ['DB_HOST'], user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'], database=os.environ['DB_NAME'])
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    for p in products: p['price'] = float(p['price'])
    conn.close()
    r.setex('products', 60, json.dumps(products))  # TTL 60s
    return jsonify({"source": "db", "data": products})

@app.route('/health')
def health(): return {"status": "ok"}

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)