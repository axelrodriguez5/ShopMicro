import pika, json, os, time, sys

def connect_mq():
    # Reintents fins que RabbitMQ estigui disponible
    creds = pika.PlainCredentials(os.environ['MQ_USER'], os.environ['MQ_PASS'])
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
    # Es crida cada vegada que arriba un missatge nou
    order = json.loads(body)
    print(f"[NOTIFICACIÓ] Comanda #{order['order_id']} creada: "
          f"{order['quantity']} x {order['product_name']} "
          f"(producte ID {order['product_id']})", flush=True)
    # Confirmem que hem processat el missatge
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    connection = connect_mq()
    channel = connection.channel()
    channel.queue_declare(queue='orders', durable=True)
    channel.basic_qos(prefetch_count=1)  # processem un missatge a la vegada
    channel.basic_consume(queue='orders', on_message_callback=callback)
    print("[notification] Esperant missatges a la cua 'orders'...", flush=True)
    channel.start_consuming()

if __name__ == '__main__':
    main()