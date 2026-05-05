from flask import Flask, jsonify, request
import mysql.connector, pika, json, os, time

app = Flask(__name__)

def conn_products():
    return mysql.connector.connect(
        host=os.environ['DB_PRODUCTS_HOST'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        database='products_db')

def conn_orders():
    return mysql.connector.connect(
        host=os.environ['DB_ORDERS_HOST'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        database='orders_db')

# Inicialitzem la taula d'orders a db-orders
def init_db():
    for _ in range(10):
        try:
            conn = conn_orders()
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS orders(
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT,
                quantity INT,
                status VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            conn.commit(); conn.close(); return
        except Exception as e:
            print("Esperant DB orders...", e); time.sleep(3)

def publish_message(order):
    # Publiquem el missatge a RabbitMQ
    creds = pika.PlainCredentials(os.environ['MQ_USER'], os.environ['MQ_PASS'])
    params = pika.ConnectionParameters(host=os.environ['MQ_HOST'], credentials=creds)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue='orders', durable=True)
    channel.basic_publish(
        exchange='',
        routing_key='orders',
        body=json.dumps(order),
        properties=pika.BasicProperties(delivery_mode=2))  # missatge persistent
    connection.close()

@app.route('/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)

    # 1. Comprovem i descomptem stock a db-products
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

    # 2. Creem la comanda a db-orders
    co = conn_orders()
    cur = co.cursor()
    cur.execute("INSERT INTO orders(product_id, quantity, status) VALUES(%s, %s, %s)",
                (product_id, quantity, 'CREATED'))
    order_id = cur.lastrowid
    co.commit(); co.close()

    # 3. Publiquem missatge a RabbitMQ
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
    # Convertim datetime a string per al JSON
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