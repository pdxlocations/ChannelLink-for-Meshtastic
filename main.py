from meshtastic.protobuf import mesh_pb2, mqtt_pb2, portnums_pb2
import paho.mqtt.client as mqtt
import logging
import time
from collections import deque
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
import sys

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

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

DIVIDER = '-' * 50

def log_forwarded_message(from_topic, to_topic, portnum, orig_channel, new_channel, orig_hop_limit, new_hop_limit, orig_hop_start, new_hop_start, payload, action):
    logging.info(
        f"\n{DIVIDER}\n"
        f"From Topic : {from_topic:<35}CH {orig_channel:<3}| HL {orig_hop_limit:<2}| HS {orig_hop_start:<2}\n"
        f"To Topic   : {to_topic:<35}CH {new_channel:<3}| HL {new_hop_limit:<2}| HS {new_hop_start:<2}\n"
        f"Portnum    : {portnum}\n"
        f"Payload    : {payload}\n"
        f"Action     : {action}\n"
        f"{DIVIDER}"
    )

def log_skipped_message(from_topic, portnum, action):
    logging.info(
        f"\n{DIVIDER}\n"
        f"From Topic : {from_topic:<35}\n"
        f"Portnum    : {portnum}\n"
        f"Action     : {action}\n"
        f"{DIVIDER}"
    )

def on_connect(client, userdata, flags, reason_code, properties=None):
    """Callback function when the client connects to the broker.""" 
    if reason_code == 0:
        logging.info("Connected to broker successfully")
        for topic in TOPICS:
            client.subscribe(topic + "/#")
            logging.info(f"Subscribed to topic: {topic}")
    else:
        logging.error(f"Failed to connect with reason code {reason_code}")

def is_recent_message(topic, payload):
    """Check if a message was recently processed to avoid loops."""
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
    """Compute an XOR hash from bytes."""
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

def get_other_topics(current_topic, topics):
    """Return a list of all topics except the current one."""
    return [topic for topic in topics if topic != current_topic.split('/!')[0]]

def on_message(client, userdata, msg):
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
    
    # # Decrypt the payload if necessary
    # if original_mp.HasField("encrypted") and not original_mp.HasField("decoded"):
    #     decoded_data = decode_encrypted(original_mp)
    # else:
    #     decoded_data = original_mp.decoded
    

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
    
        # Decode payloads based on portnum type
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
        elif decoded_mp.decoded.portnum == portnums_pb2.ROUTING_APP:
            ack = mesh_pb2.Routing()
            ack.ParseFromString(decoded_mp.decoded.payload)
            payload = protobuf_to_clean_string(ack)

        # # Package the modified packet for publishing
        service_envelope = mqtt_pb2.ServiceEnvelope()
        service_envelope.packet.CopyFrom(modified_mp)

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

            # if KEY == "":
            #     modified_mp.decoded.CopyFrom(encoded_message)

            # else:
            #     modified_mp.encrypted = encrypt_message(channel, KEY, mesh_packet, encoded_message)


            # Package the modified packet for publishing
            # service_envelope = mqtt_pb2.ServiceEnvelope()
            # service_envelope.packet.CopyFrom(modified_mp)



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

def encrypt_message(channel, key, mp, encoded_message):
    """Encrypt a message."""
    try:
        mp.channel = generate_hash(channel, key)
        key_bytes = base64.b64decode(key.encode('ascii'))

        nonce_packet_id = getattr(mp, "id").to_bytes(8, "little")
        nonce_from_node = getattr(mp, "from").to_bytes(8, "little")
        
        # Put both parts into a single byte array.
        nonce = nonce_packet_id + nonce_from_node

        cipher = Cipher(algorithms.AES(key_bytes), modes.CTR(nonce), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_bytes = encryptor.update(encoded_message.SerializeToString()) + encryptor.finalize()

        return encrypted_bytes
    
    except Exception as e:
        logging.error(f"Failed to decrypt: {e}")
        return None


def main():
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