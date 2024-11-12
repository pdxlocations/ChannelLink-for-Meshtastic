A Python script using MQTT to bridge Meshtastic networks using different modem settings.

Example Topology:<br>
<img width="831" alt="example topology" src="https://github.com/user-attachments/assets/0c269d65-3b17-4aa8-b159-08e404bca69f">

To install:
```
git clone https://github.com/pdxlocations/ChannelLink-for-Meshtastic.git
cd ChannelLink-for-Meshtastic
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Rename config-example.json and edit configuration:
```
sudo mv config-example.json config.json
sudo nano config.json
```
