import pika, json, os, time, sys

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
MQ_USER = read_secret('mq_user', 'MQ_USER')
MQ_PASS = read_secret('mq_password', 'MQ_PASS')

def connect_mq():
    creds = pika.PlainCredentials(MQ_USER, MQ_PASS)    # ← canviat
    params = pika.ConnectionParameters(
        host=os.environ['MQ_HOST'],
        credentials=creds,
        heartbeat=600)
    for i in range(15):
        try:
            return pika.BlockingConnection(params)
        except Exception as e:
            print(f"[notification] Esperant RabbitMQ... intent {i+1}", flush=True)
            time.sleep(3)
    print("[notification] No s'ha pogut connectar a RabbitMQ", flush=True)
    sys.exit(1)

def callback(ch, method, properties, body):
    order = json.loads(body)
    print(f"[NOTIFICACIÓ] Comanda #{order['order_id']} creada: "
          f"{order['quantity']} x {order['product_name']} "
          f"(producte ID {order['product_id']})", flush=True)
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    connection = connect_mq()
    channel = connection.channel()
    channel.queue_declare(queue='orders', durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='orders', on_message_callback=callback)
    print("[notification] Esperant missatges a la cua 'orders'...", flush=True)
    channel.start_consuming()

if __name__ == '__main__':
    main()