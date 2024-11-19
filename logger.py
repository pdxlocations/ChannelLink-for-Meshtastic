import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

DIVIDER = '-' * 50

def log_forwarded_message(from_topic, to_topic, portnum, orig_channel, new_channel, orig_hop_limit, new_hop_limit, orig_hop_start, new_hop_start, payload, action) -> None:
    logging.info(
        f"\n{DIVIDER}\n"
        f"From Topic : {from_topic:<35}CH {orig_channel:<3}| HL {orig_hop_limit:<2}| HS {orig_hop_start:<2}\n"
        f"To Topic   : {to_topic:<35}CH {new_channel:<3}| HL {new_hop_limit:<2}| HS {new_hop_start:<2}\n"
        f"Portnum    : {portnum}\n"
        f"Payload    : {payload}\n"
        f"Action     : {action}\n"
        f"{DIVIDER}"
    )

def log_skipped_message(from_topic, portnum, action) -> None:
    logging.info(
        f"\n{DIVIDER}\n"
        f"From Topic : {from_topic:<35}\n"
        f"Portnum    : {portnum}\n"
        f"Action     : {action}\n"
        f"{DIVIDER}"
    )