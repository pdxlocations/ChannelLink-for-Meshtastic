#!/usr/bin/env python3

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
HOP_MODIFIER = 1 # Add this many hops to account for bridge losses
FORWARDED_PORTNUMS = [1,3,4,5,6,8,70]
"""
https://buf.build/meshtastic/protobufs/file/main:meshtastic/portnums.proto

UNKNOWN_APP = 0;
TEXT_MESSAGE_APP = 1;
REMOTE_HARDWARE_APP = 2;
POSITION_APP = 3;
NODEINFO_APP = 4;
ROUTING_APP = 5;
ADMIN_APP = 6;
TEXT_MESSAGE_COMPRESSED_APP = 7;
WAYPOINT_APP = 8;
AUDIO_APP = 9;
DETECTION_SENSOR_APP = 10;
REPLY_APP = 32;
IP_TUNNEL_APP = 33;
PAXCOUNTER_APP = 34;
SERIAL_APP = 64;
STORE_FORWARD_APP = 65;
RANGE_TEST_APP = 66;
TELEMETRY_APP = 67;
ZPS_APP = 68;
SIMULATOR_APP = 69;
TRACEROUTE_APP = 70;
NEIGHBORINFO_APP = 71;
ATAK_PLUGIN = 72;
MAP_REPORT_APP = 73;
POWERSTRESS_APP = 74;
PRIVATE_APP = 256;
ATAK_FORWARDER = 257;
MAX = 511;
"""