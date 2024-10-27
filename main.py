from meshtastic.protobuf import mesh_pb2, mqtt_pb2, portnums_pb2
import paho.mqtt.client as mqtt
import logging
import time
from collections import deque
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

### Load Config
config_path =  'config.py'
config = {}
if os.path.exists(config_path):
    with open(config_path, 'r') as config_file:
        exec(config_file.read(), config)
else:
    raise FileNotFoundError(f"Configuration file not found: {config_path}")

BROKER = config.get('BROKER')
PORT = config.get('PORT')
USER = config.get('USER')
PASSWORD = config.get('PASSWORD')
TOPIC_1 = config.get('TOPIC_1')
TOPIC_2 = config.get('TOPIC_2')
KEY = config.get('KEY')
FORWARDED_PORTNUMS = config.get('FORWARDED_PORTNUMS')

RECENT_MESSAGES = deque(maxlen=100)  # Store recent messages to prevent loops
CACHE_EXPIRY_TIME = 5  # Messages expire from cache after 5 seconds

expanded_key = "1PG7OiApB1nwvP+rz05pAQ==" if KEY == "AQ==" else KEY

DIVIDER = '-' * 50
def log_message(from_topic, to_topic, portnum, payload, action):
    """Log messages with a formatted output."""
    logging.info(
        f"\n{DIVIDER}\n"
        f"From Topic : {from_topic}\n"
        f"To Topic   : {to_topic}\n"
        f"Portnum    : {portnum}\n"
        f"Payload    : {payload}\n"
        f"Action     : {action}\n"
        f"{DIVIDER}"
    )

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        logging.info("Connected to broker successfully")
        client.subscribe(TOPIC_1 + "/#")
        client.subscribe(TOPIC_2 + "/#")
    else:
        logging.error(f"Failed to connect with reason code {reason_code}")

def is_recent_message(topic, payload):
    """Check if the message is recently processed."""
    current_time = time.time()
    for msg_payload, timestamp in RECENT_MESSAGES:
        if msg_payload == payload and current_time - timestamp < CACHE_EXPIRY_TIME:
            return True
    return False

def get_portnum_name(portnum):
    """For Logging: Retrieve the name of the port number from the protobuf enum."""
    try:
        return portnums_pb2.PortNum.Name(portnum)  # Use protobuf's enum name lookup
    except ValueError:
        return f"Unknown ({portnum})"  # Handle unknown port numbers gracefully
    
def protobuf_to_clean_string(proto_message):
    """For Logging: Convert protobuf message to string and remove newlines."""
    return str(proto_message).replace('\n', ' ').replace('\r', ' ').strip()

def xor_hash(data: bytes) -> int:
    """Return XOR hash of all bytes in the provided string."""
    result = 0
    for char in data:
        result ^= char
    return result

def generate_hash(name: str, key: str) -> int:
    """generate the channel number by hashing the channel name and psk"""
    replaced_key = key.replace('-', '+').replace('_', '/')
    key_bytes = base64.b64decode(replaced_key.encode('utf-8'))
    h_name = xor_hash(bytes(name, 'utf-8'))
    h_key = xor_hash(key_bytes)
    result: int = h_name ^ h_key
    return result


def on_message(client, userdata, msg):
    se = mqtt_pb2.ServiceEnvelope()
    se_modified = mqtt_pb2.ServiceEnvelope()
    se_decoded = mqtt_pb2.ServiceEnvelope()
    try:
        se.ParseFromString(msg.payload)
        se_modified.ParseFromString(msg.payload)
        se_decoded.ParseFromString(msg.payload)
        original_mp = se.packet
        modified_mp = se_modified.packet
        decoded_mp = se_decoded.packet
    except Exception as e:
        print(f"*** ServiceEnvelope: {str(e)}")
        return
    
    if original_mp.HasField("encrypted") and not original_mp.HasField("decoded"):
        decoded_data = decode_encrypted(original_mp)
    else:
        decoded_data = original_mp.decoded
    
    decoded_mp.decoded.CopyFrom(decoded_data)

    # Determine the target topic
    gateway_node_id = msg.topic.split("/")[-1]
    target_topic = f"{TOPIC_2}" if msg.topic.startswith(TOPIC_1) else f"{TOPIC_1}"

    # Use the last segment of the target topic to generate the new channel
    forward_to_preset = target_topic.split("/")[-1]

    new_channel = generate_hash(forward_to_preset, expanded_key)
    modified_mp.channel = new_channel
    modified_mp.hop_limit = min(original_mp.hop_limit + 3, 7)

    if decoded_mp.decoded.portnum in FORWARDED_PORTNUMS:

        portnum_name = get_portnum_name(decoded_mp.decoded.portnum)
        payload = decoded_mp.decoded.payload
    
        if decoded_mp.decoded.portnum == portnums_pb2.TEXT_MESSAGE_APP:
            payload = payload.decode('utf-8').replace('\n', ' ').replace('\r', ' ')

        elif decoded_mp.decoded.portnum == portnums_pb2.NODEINFO_APP:
            user_info = mesh_pb2.User()
            user_info.ParseFromString(decoded_mp.decoded.payload)
            payload = protobuf_to_clean_string(user_info)

        elif decoded_mp.decoded.portnum == portnums_pb2.POSITION_APP:
            pos = mesh_pb2.Position()
            pos.ParseFromString(decoded_mp.decoded.payload)
            payload = protobuf_to_clean_string(pos)

        # Determine the target topic
        gateway_node_id = msg.topic.split("/")[-1]
        target_topic = f"{TOPIC_2}/{gateway_node_id}" if msg.topic.startswith(TOPIC_1) else f"{TOPIC_1}/{gateway_node_id}"

        # Check if the message was already forwarded recently
        if is_recent_message(msg.topic, payload):
            log_message(msg.topic, target_topic, portnum_name, payload, "Skipped (Duplicate)")
            return

        # Store the message to prevent loops
        RECENT_MESSAGES.append((payload, time.time()))

        # package up the modified packet
        service_envelope = mqtt_pb2.ServiceEnvelope()
        service_envelope.packet.CopyFrom(modified_mp)
        service_envelope.channel_id = forward_to_preset
        service_envelope.gateway_id = gateway_node_id
        modified_payload = service_envelope.SerializeToString()

        # print (f"\n\nOriginal Payload: {original_mp}")
        # print (f"\nModified Payload: {modified_mp}")
        # print ('')

        # Publish the message to the target topic
        result = client.publish(target_topic, modified_payload)

        if result.rc == 0:
            log_message(msg.topic, target_topic, portnum_name, payload, "Forwarded")
        else:
            log_message(msg.topic, target_topic, portnum_name, payload, f"Failed (Status: {result.rc})")

    time.sleep(0.1)

def decode_encrypted(mp):
    """Decrypt the encrypted message payload and return the decoded data."""
    try:
        key_bytes = base64.b64decode(expanded_key.encode('ascii'))

        # Build the nonce from message ID and sender
        nonce_packet_id = getattr(mp, "id").to_bytes(8, "little")
        nonce_from_node = getattr(mp, "from").to_bytes(8, "little")
        nonce = nonce_packet_id + nonce_from_node

        # Decrypt the encrypted payload
        cipher = Cipher(algorithms.AES(key_bytes), modes.CTR(nonce), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_bytes = decryptor.update(getattr(mp, "encrypted")) + decryptor.finalize()

        # Parse the decrypted bytes into a Data object
        data = mesh_pb2.Data()
        data.ParseFromString(decrypted_bytes)
        return data

    except Exception as e:
        logging.error(f"Failed to decrypt: {e}")
        return None

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(USER, PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message

    logging.info(f"Connecting to broker at {BROKER}:{PORT}...")
    client.connect(BROKER, PORT, keepalive=60)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logging.info("Bridge stopped by user")

if __name__ == "__main__":
    main()