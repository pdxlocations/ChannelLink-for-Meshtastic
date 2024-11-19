
from meshtastic.protobuf import mqtt_pb2
from meshtastic import protocols
import logging
import time
from collections import deque

import load_config
from encryption import decrypt_packet, encrypt_packet
from utils import protobuf_to_clean_string, get_portnum_name, generate_hash
from logger import log_forwarded_message, log_skipped_message


# Manage recent messages to avoid loops
RECENT_MESSAGES = deque(maxlen=100)  # Store recent messages to prevent loops
CACHE_EXPIRY_TIME = 5  # Messages expire from cache after 5 seconds

def is_recent_message(payload) -> bool:
    """Check if a message was recently processed to avoid loops."""
    current_time = time.time()
    for msg_payload, timestamp in RECENT_MESSAGES:
        if msg_payload == payload and current_time - timestamp < CACHE_EXPIRY_TIME:
            return True
    return False

def on_message(client, userdata, msg) -> None:
    """Handle incoming MQTT messages."""
    se = mqtt_pb2.ServiceEnvelope()  # Main variable for parsing and decoding
    modified_se = mqtt_pb2.ServiceEnvelope()  # For modifications and republishing

    try:
        # Parse message payload into ServiceEnvelope objects
        se.ParseFromString(msg.payload)
        modified_se.ParseFromString(msg.payload)
        original_mp = se.packet
        modified_mp = modified_se.packet
    except Exception as e:
        print(f"*** ServiceEnvelope: {str(e)}")
        return
    
    # Decrypt the payload if necessary
    if original_mp.HasField("encrypted") and not original_mp.HasField("decoded"):
        decoded_data = decrypt_packet(original_mp, load_config.EXPANDED_KEY)
        if decoded_data is None:  # Check if decryption failed
            logging.error("Decryption failed; skipping message")
            return  # Skip processing this message if decryption failed
    else:
        decoded_data = original_mp.decoded
    
    original_mp.decoded.CopyFrom(decoded_data)

    # Modify hop limit and hop start. Keep hop_limit/hop_start ratio the same.
    if original_mp.hop_start > 0:
        modified_mp.hop_limit = min(original_mp.hop_limit + load_config.HOP_MODIFIER, 7 - (original_mp.hop_start - original_mp.hop_limit))
        modified_mp.hop_start = min(original_mp.hop_start + load_config.HOP_MODIFIER, 7)
    else:
        modified_mp.hop_limit = min(original_mp.hop_limit + load_config.HOP_MODIFIER, 7)

    if original_mp.decoded.portnum in load_config.FORWARDED_PORTNUMS:
        # Extract portnum name and payload for logging
        portnum_name = get_portnum_name(original_mp.decoded.portnum)
        payload = original_mp.decoded.payload
        portNumInt = original_mp.decoded.portnum
        handler = protocols.get(portNumInt)
        if handler.protobufFactory is not None:
            pb = handler.protobufFactory()
            pb.ParseFromString(original_mp.decoded.payload)
            payload = protobuf_to_clean_string(pb)

        # Get a list of all topics except the current one
        target_topics = [topic for topic in load_config.TOPICS if topic != msg.topic.split('/!')[0]]

        # Check if the message was forwarded recently
        if is_recent_message(payload):
            return
        
        # Cache the message to prevent loops
        RECENT_MESSAGES.append((payload, time.time()))

        # Forward the message to all other topics
        for target_topic in target_topics:
            gateway_node_id = msg.topic.split("/")[-1]
            forward_to_preset = target_topic.split("/")[-1]
            target_topic =f"{target_topic}/{gateway_node_id}"
    
            new_channel = generate_hash(forward_to_preset, load_config.EXPANDED_KEY)
            modified_mp.channel = new_channel
            original_channel = msg.topic
            original_channel = original_channel.split("/")[3]
            original_channel = generate_hash(original_channel, load_config.EXPANDED_KEY)

            if load_config.EXPANDED_KEY == "":
                modified_mp.decoded.CopyFrom(original_mp.decoded)
            else:
                modified_mp.encrypted = encrypt_packet(forward_to_preset, load_config.EXPANDED_KEY, modified_mp, original_mp.decoded)


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
        log_skipped_message(msg.topic,get_portnum_name(original_mp.decoded.portnum), "Skipped" )

    time.sleep(0.1)
