# Hisense air conditioners & Domoticz integration
A simple plugin for Domoticz that reads data from the [AirCon](https://github.com/deiger/AirCon) server.
## Installation
**First install and configure the [AirCon](https://github.com/deiger/AirCon) server created by [@deiger](https://github.com/deiger).**

If everything works fine, navigate to the plugin directory and install the plugin straight from github
```
cd domoticz/plugins
git clone https://github.com/bblaszkiewicz/Hisense-AirCon-Domoticz.git HisenseAircon
```
Next, restart Domoticz so that it will find the plugin
```
sudo systemctl restart domoticz.service
```

## Plugin update
Go to plugin folder and pull new version
```
cd domoticz/plugins/FoxESS
git pull
```
Restart domoticz
```
sudo systemctl restart domoticz.service
```
