import os
import json

### Load Config
# Get the directory where the script is located to build the path for the config file
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, 'config.json')

# Load configuration from the config.py file
config = {}
if os.path.exists(config_path):
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)
else:
    raise FileNotFoundError(f"Configuration file not found: {config_path}")

# Extract necessary config values
BROKER = config['broker']['address']
PORT = config['broker']['port']
USER = config['broker']['user']
PASSWORD = config['broker']['password']
TOPICS = config['topics']
KEY = config['key']
FORWARDED_PORTNUMS = config['forwarded_portnums']
HOP_MODIFIER = config['hop_modifier']

# Get the full default key
EXPANDED_KEY = "1PG7OiApB1nwvP+rz05pAQ==" if KEY == "AQ==" else KEY
