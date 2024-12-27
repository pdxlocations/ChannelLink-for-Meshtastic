A Python script using MQTT to bridge Meshtastic networks using different modem settings.

Example Topology:<br>
<img width="831" alt="example topology" src="https://github.com/user-attachments/assets/0c269d65-3b17-4aa8-b159-08e404bca69f">

## ChannelLink Installation
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

## Run ChannelLink as a Service

Create a new file:
```
sudo nano /etc/systemd/system/channellink.service
```
Paste the below text and edit to fit your file paths and username:
```[Unit]
Description = ChannelLink
After = network.target

[Service]
Type = simple
Environment="PATH=/home/pdxlocs/github/pdxlocations/ChannelLink-for-Meshtastic/.venv/bin"
ExecStart = /home/pdxlocs/ChannelLink-for-Meshtastic/.venv/bin/python3 /home/pdxlocs/ChannelLink-for-Meshtastic/main.py
User = pdxlocs
Restart = on-failure
RestartSec = 5
TimeoutStartSec = infinity

[Install]
WantedBy = multi-user.target
```
Save/Exit, then run:
```
sudo systemctl enable channellink
sudo systemctl daemon-reload
sudo systemctl start channellink
```
Check the status:
```
sudo systemctl status channellink.service
```
Check the logs to make sure everything is working right:
```
End of the log:
journalctl -u meshlink.service -e

Live view:
journalctl -u meshlink.service -f
```
Stop or restart the service:
```
sudo systemctl stop channellink
sudo systemctl restart channellink
```

## Build Custom Firmware (Optional)

I recommend building your own firmware so that you may remove the code that marks these packets at passing through an MQTT broker. Since this broker does not require the internet, the links all depend on RF and will function without web access.

Follow the instructions at https://meshtastic.org/docs/development/firmware/build/

Then comment out this line in MQTT.cpp:
https://github.com/meshtastic/firmware/blob/80fc0f2bdafe2cca248afec92589bad341143d75/src/mqtt/MQTT.cpp#L98

## Install Moquitto Broker
```
sudo apt update && sudo apt upgrade
sudo apt install mosquitto
sudo systemctl enable mosquitto.service
```
Edit moquitto.conf
```
sudo nano /etc/mosquitto/mosquitto.conf
```
Add to the end of the file:
```
listener 1883
allow_anonymous true
```
Run:
```
sudo systemctl restart mosquitto
```

### To use a password (optional and not tested by me):
```
sudo mosquitto_passwd -c /etc/mosquitto/passwd YOUR_USERNAME
sudo nano /etc/mosquitto/mosquitto.conf
```
Add to top of the file:
```
per_listener_settings true
```
Add to bottom of the file:
```
allow_anonymous false
listener 1883
password_file /etc/mosquitto/passwd
```

## Enable AP Mode on a Raspberry Pi

I recommend installing a secondary wifi or ethernet module on your raspberry pi before enabling AP mode so you can ssh in without switching your dev machine's AP.

### Enable AP mode
Run:
```
sudo nmcli device wifi hotspot ssid <example-network-name> password <example-password>
```

### If you need to disable the AP and connect to your wifi
To shut down the AP:
```
sudo nmcli connection down Hotspot
```
To start it back up:
```
sudo nmcli connection up Hotspot
```

### Enable the AP to start on boot
find your hotspot UUID:
```
nmcli connection
```
You should get an output listing your UUID's like this:
```
NAME                UUID                                  TYPE      DEVICE 
Hotspot             1ceca58e-0652-4f36-b817-eb5907aa441a  wifi      wlan0  
Wired connection 1  bbcec6db-fdac-3146-b27c-e18a04e5f7b9  ethernet  eth0   
lo                  f8521b4c-0194-4f9f-944c-0bdf29d78a02  loopback  lo     
preconfigured       fa2146db-d5b0-49b2-a6b7-e6f7a07e9c84  wifi      --
```
then, replaceing <examplie-UUID> with your UUID, run:
```
sudo nmcli connection modify <example-UUID> connection.autoconnect yes connection.autoconnect-priority 100
```
Then:
```
nmcli connection show <example-UUID> 
```
Look for:
```
connection.autoconnect:                 yes
connection.autoconnect-priority:        100
```

