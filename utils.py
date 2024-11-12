from meshtastic.protobuf import portnums_pb2
import base64

def get_portnum_name(portnum) -> str:
    """For Logging: Retrieve the name of the port number from the protobuf enum."""
    try:
        return portnums_pb2.PortNum.Name(portnum)  # Use protobuf's enum name lookup
    except ValueError:
        return f"Unknown ({portnum})"  # Handle unknown port numbers gracefully
    
def protobuf_to_clean_string(proto_message) -> str:
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