from flask import Flask, jsonify, request
import mysql.connector, pika, json, os, time

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
MQ_USER     = read_secret('mq_user', 'MQ_USER')
MQ_PASS     = read_secret('mq_password', 'MQ_PASS')

def conn_products():
    return mysql.connector.connect(
        host=os.environ['DB_PRODUCTS_HOST'],
        user=os.environ['DB_USER'],
        password=DB_PASSWORD,                          # ← canviat
        database='products_db')

def conn_orders():
    return mysql.connector.connect(
        host=os.environ['DB_ORDERS_HOST'],
        user=os.environ['DB_USER'],
        password=DB_PASSWORD,                          # ← canviat
        database='orders_db')

def init_db():
    for i in range(30):
        try:
            conn = conn_orders()
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS orders(
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT,
                quantity INT,
                status VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            conn.commit(); conn.close()
            print("[init_db] Taula 'orders' inicialitzada correctament", flush=True)
            return
        except Exception as e:
            print(f"[init_db] Intent {i+1}/30 fallit: {e}", flush=True)
            time.sleep(5)
    print("[init_db] AVÍS: no s'ha pogut inicialitzar la BD orders", flush=True)

def publish_message(order):
    creds = pika.PlainCredentials(MQ_USER, MQ_PASS)    # ← canviat
    params = pika.ConnectionParameters(host=os.environ['MQ_HOST'], credentials=creds)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue='orders', durable=True)
    channel.basic_publish(
        exchange='',
        routing_key='orders',
        body=json.dumps(order),
        properties=pika.BasicProperties(delivery_mode=2))
    connection.close()

@app.route('/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)

    cp = conn_products()
    cur = cp.cursor(dictionary=True)
    cur.execute("SELECT * FROM products WHERE id=%s", (product_id,))
    product = cur.fetchone()
    if not product:
        cp.close()
        return jsonify({"error": "Producte no trobat"}), 404
    if product['stock'] < quantity:
        cp.close()
        return jsonify({"error": "Stock insuficient"}), 400
    cur.execute("UPDATE products SET stock=stock-%s WHERE id=%s",
                (quantity, product_id))
    cp.commit(); cp.close()

    co = conn_orders()
    cur = co.cursor()
    cur.execute("INSERT INTO orders(product_id, quantity, status) VALUES(%s, %s, %s)",
                (product_id, quantity, 'CREATED'))
    order_id = cur.lastrowid
    co.commit(); co.close()

    order_msg = {
        "order_id": order_id,
        "product_id": product_id,
        "product_name": product['name'],
        "quantity": quantity
    }
    publish_message(order_msg)

    return jsonify({"message": "Comanda creada", "order": order_msg}), 201

@app.route('/orders', methods=['GET'])
def list_orders():
    co = conn_orders()
    cur = co.cursor(dictionary=True)
    cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
    orders = cur.fetchall()
    co.close()
    for o in orders:
        o['created_at'] = str(o['created_at'])
    return jsonify(orders)

@app.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    co = conn_orders()
    cur = co.cursor(dictionary=True)
    cur.execute("SELECT * FROM orders WHERE id=%s", (order_id,))
    order = cur.fetchone()
    co.close()
    if not order:
        return jsonify({"error": "Comanda no trobada"}), 404
    order['created_at'] = str(order['created_at'])
    return jsonify(order)

@app.route('/health')
def health(): return {"status": "ok"}

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)