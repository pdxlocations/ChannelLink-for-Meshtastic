from meshtastic.protobuf import mqtt_pb2, portnums_pb2
from meshtastic import protocols
import paho.mqtt.client as mqtt
import time
from collections import deque
import os
import logging
import sys

from logger import log_forwarded_message, log_skipped_message
from encryption import decrypt_packet, encrypt_packet, generate_hash

### Load Config
# Get the directory where the script is located to build the path for the config file
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, 'config.py')

# Load configuration from the config.py file
config = {}
if os.path.exists(config_path):
    with open(config_path, 'r') as config_file:
        exec(config_file.read(), config)
else:
    raise FileNotFoundError(f"Configuration file not found: {config_path}")

# Extract necessary config values
BROKER = config.get('BROKER')
PORT = config.get('PORT')
USER = config.get('USER')
PASSWORD = config.get('PASSWORD')
TOPICS = config.get('TOPICS')
KEY = config.get('KEY')
FORWARDED_PORTNUMS = config.get('FORWARDED_PORTNUMS')
HOP_MODIFIER = config.get('HOP_MODIFIER')

# Manage recent messages to avoid loops
RECENT_MESSAGES = deque(maxlen=100)  # Store recent messages to prevent loops
CACHE_EXPIRY_TIME = 5  # Messages expire from cache after 5 seconds

# Get the full default key
expanded_key = "1PG7OiApB1nwvP+rz05pAQ==" if KEY == "AQ==" else KEY


def on_connect(client, userdata, flags, reason_code, properties=None) -> None:
    """Callback function when the client connects to the broker.""" 
    if reason_code == 0:
        logging.info("Connected to broker successfully")
        for topic in TOPICS:
            client.subscribe(topic + "/#")
            logging.info(f"Subscribed to topic: {topic}")
    else:
        logging.error(f"Failed to connect with reason code {reason_code}")

def is_recent_message(topic, payload) -> bool:
    """Check if a message was recently processed to avoid loops."""
    current_time = time.time()
    for msg_payload, timestamp in RECENT_MESSAGES:
        if msg_payload == payload and current_time - timestamp < CACHE_EXPIRY_TIME:
            return True
    return False

def get_portnum_name(portnum) -> str:
    """For Logging: Retrieve the name of the port number from the protobuf enum."""
    try:
        return portnums_pb2.PortNum.Name(portnum)  # Use protobuf's enum name lookup
    except ValueError:
        return f"Unknown ({portnum})"  # Handle unknown port numbers gracefully
    
def protobuf_to_clean_string(proto_message) -> str:
    """For Logging: Convert protobuf message to string and remove newlines."""
    return str(proto_message).replace('\n', ' ').replace('\r', ' ').strip()

def get_other_topics(current_topic, topics) -> list[str]:
    """Return a list of all topics except the current one."""
    return [topic for topic in topics if topic != current_topic.split('/!')[0]]

def on_message(client, userdata, msg) -> None:
    """Handle incoming MQTT messages."""
    se = mqtt_pb2.ServiceEnvelope()
    se_modified = mqtt_pb2.ServiceEnvelope()
    se_decoded = mqtt_pb2.ServiceEnvelope()

    try:
        # Parse message payload into ServiceEnvelope objects
        se.ParseFromString(msg.payload)
        se_modified.ParseFromString(msg.payload)
        se_decoded.ParseFromString(msg.payload)
        original_mp = se.packet
        modified_mp = se_modified.packet
        decoded_mp = se_decoded.packet
    except Exception as e:
        print(f"*** ServiceEnvelope: {str(e)}")
        return
    
    # Decrypt the payload if necessary
    if original_mp.HasField("encrypted") and not original_mp.HasField("decoded"):
        decoded_data = decrypt_packet(original_mp, expanded_key)
        if decoded_data is None:  # Check if decryption failed
            logging.error("Decryption failed; skipping message")
            return  # Skip processing this message if decryption failed
    else:
        decoded_data = original_mp.decoded
    
    decoded_mp.decoded.CopyFrom(decoded_data)

    # Modify hop limit and hop start. Keep hop_limit/hop_start ratio the same.
    if original_mp.hop_start > 0:
        modified_mp.hop_limit = min(original_mp.hop_limit + HOP_MODIFIER, 7 - (original_mp.hop_start - original_mp.hop_limit))
        modified_mp.hop_start = min(original_mp.hop_start + HOP_MODIFIER, 7)
    else:
        modified_mp.hop_limit = min(original_mp.hop_limit + HOP_MODIFIER, 7)

    if decoded_mp.decoded.portnum in FORWARDED_PORTNUMS:
        # Extract portnum name and payload for logging
        portnum_name = get_portnum_name(decoded_mp.decoded.portnum)
        payload = decoded_mp.decoded.payload
        portNumInt = decoded_mp.decoded.portnum
        handler = protocols.get(portNumInt)
        if handler.protobufFactory is not None:
            pb = handler.protobufFactory()
            pb.ParseFromString(decoded_mp.decoded.payload)
            payload = protobuf_to_clean_string(pb)

        # Get a list of target topics to forward the message to
        target_topics = get_other_topics(msg.topic, TOPICS)

        # Check if the message was forwarded recently
        if is_recent_message(msg.topic, payload):
            return
        
        # Cache the message to prevent loops
        RECENT_MESSAGES.append((payload, time.time()))

        # Forward the message to all other topics
        for target_topic in target_topics:
            gateway_node_id = msg.topic.split("/")[-1]
            forward_to_preset = target_topic.split("/")[-1]
            target_topic =f"{target_topic}/{gateway_node_id}"
    
            new_channel = generate_hash(forward_to_preset, expanded_key)
            modified_mp.channel = new_channel
            original_channel = msg.topic
            original_channel = original_channel.split("/")[3]
            original_channel = generate_hash(original_channel, expanded_key)

            if KEY == "":
                modified_mp.decoded.CopyFrom(decoded_mp.decoded)
            else:
                modified_mp.encrypted = encrypt_packet(forward_to_preset, expanded_key, modified_mp, decoded_mp.decoded)

            # Package the modified packet for publishing
            service_envelope = mqtt_pb2.ServiceEnvelope()
            service_envelope.packet.CopyFrom(modified_mp)
            service_envelope.channel_id = forward_to_preset
            service_envelope.gateway_id = gateway_node_id

            modified_payload = service_envelope.SerializeToString()

            result = client.publish(target_topic, modified_payload)

            if result.rc == 0:
                log_forwarded_message(msg.topic, target_topic, portnum_name, original_channel, new_channel, original_mp.hop_limit, modified_mp.hop_limit, original_mp.hop_start, modified_mp.hop_start, payload, "Forwarded")
            else:
                logging.error(f"Failed to forward message to {target_topic} (Status: {result.rc})")
    else:
        log_skipped_message(msg.topic,get_portnum_name(decoded_mp.decoded.portnum), "Skipped" )

    time.sleep(0.1)

def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(USER, PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message

    logging.info(f"Connecting to broker at {BROKER}:{PORT}...")
    try:
        client.connect(BROKER, PORT, keepalive=60)
    except Exception as e:
        print(f"Failed to connect to broker: {e}")
        sys.exit(1)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logging.info("Bridge stopped by user")

if __name__ == "__main__":
    main()