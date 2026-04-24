import pika
import os
import json
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [notification-service] %(message)s"
)
log = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "message-queue")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "shopuser")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "shoppass")

def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        log.info("=" * 55)
        log.info("📬 NOVA NOTIFICACIÓ REBUDA")
        log.info(f"   Esdeveniment : {message.get('event')}")
        log.info(f"   Comanda ID   : {message.get('order_id')}")
        log.info(f"   Usuari       : {message.get('user_id')}")
        log.info(f"   Producte ID  : {message.get('product_id')}")
        log.info(f"   Quantitat    : {message.get('quantity')}")
        log.info("   ✅ Notificació processada correctament")
        log.info("=" * 55)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        log.error(f"Error processant missatge: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def connect_with_retry():
    for attempt in range(20):
        try:
            log.info(f"Connectant a RabbitMQ (intent {attempt+1}/20)...")
            creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            params = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                credentials=creds,
                heartbeat=30,
                blocked_connection_timeout=300
            )
            return pika.BlockingConnection(params)
        except Exception as e:
            log.warning(f"RabbitMQ no disponible: {e}. Reintentant en 5s...")
            time.sleep(5)
    raise Exception("No s'ha pogut connectar a RabbitMQ")

if __name__ == "__main__":
    time.sleep(10)
    conn = connect_with_retry()
    ch = conn.channel()
    ch.queue_declare(queue="orders", durable=True)
    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(queue="orders", on_message_callback=callback)
    log.info("✅ notification-service escoltant cua 'orders'...")
    ch.start_consuming()