import paho.mqtt.client as mqtt
import load_config
from logger import logging

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        logging.info("Connected to broker successfully")
        for topic in load_config.TOPICS:
            client.subscribe(topic + "/#")
            logging.info(f"Subscribed to topic: {topic}")
    else:
        logging.error(f"Failed to connect with reason code {reason_code}")

def create_mqtt_client():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(load_config.USER, load_config.PASSWORD)
    client.on_connect = on_connect
    return client