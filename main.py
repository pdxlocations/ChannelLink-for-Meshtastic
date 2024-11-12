
import logging
import sys

import config
from mqtt import create_mqtt_client
from message_handler import on_message

def main():
    client = create_mqtt_client()
    client.on_message = on_message

    logging.info(f"Connecting to broker at {config.BROKER}:{config.PORT}...")
    try:
        client.connect(config.BROKER, config.PORT, keepalive=60)
    except Exception as e:
        print(f"Failed to connect to broker: {e}")
        sys.exit(1)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logging.info("Bridge stopped by user")

if __name__ == "__main__":
    main()