#!/usr/bin/env python3

from meshtastic.protobuf import portnums_pb2

### Bridge will not work on the default server - you must specify a private broker
BROKER = "mqtt.meshtastic.org"
PORT = 1883
USER = "meshdev"
PASSWORD = "large4cats"
TOPICS = [
    "msh/US/BRIDGE/2/e/LongFast",
    "msh/US/BRIDGE/2/e/MediumFast",
    "msh/US/BRIDGE/2/e/ShortFast"
]
KEY = "AQ=="
FORWARDED_PORTNUMS = [
    portnums_pb2.TEXT_MESSAGE_APP, 
    portnums_pb2.NODEINFO_APP, 
    portnums_pb2.POSITION_APP, 
    portnums_pb2.ROUTING_APP
]

HOP_MODIFIER = 1 # Add this many hops to account for bridge losses