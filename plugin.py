"""
<plugin key="aircon_status" name="Hisense - AirCon Plugin" version="0.1" author="BBlaszkiewicz"
    type="hardware" 
    description="Plugin do odczytu i sterowania klimatyzatorem Hisense">
    
    <params>
        <!-- Parametr Mode1 dla debugowania (opcjonalne) -->
        <param field="Mode1" label="Debug" width="75px">
            <options>
                <option label="False" value="false" default="true" />
                <option label="True" value="true" />
            </options>
        </param>
        
        <!-- Parametr Mode2 dla ustawienia adresu serwera klimatyzatora (opcjonalne) -->
        <param field="Mode2" label="AirCon server address" width="200px" required="true" default="localhost" />
        
        <!-- Parametr Mode3 dla interwału odświeżania -->
        <param field="Mode3" label="Refresh interval (minutes)" width="75px" required="true" default="5" />
    </params>
</plugin>

"""
import Domoticz
import subprocess
import os
import requests
import json
import time
import datetime

class BasePlugin:
    enabled = False

    def __init__(self):
        self.api_url = 'http://localhost:8888/hisense/status'
        self.command_url = 'http://localhost:8888/hisense/command'
        self.pollinterval = 300  
        self.nextpoll = datetime.datetime.now()  

    def onStart(self):
        Domoticz.Log("AirCon Status Plugin Started")

        # Pobierz wartość interwału z parametru Mode3 (jeśli ustawiony)
        if "Mode3" in Parameters:
            self.pollinterval = int(Parameters["Mode3"]) * 60  
            Domoticz.Log(f"Polling interval set to {self.pollinterval // 60} minutes")

        # Tworzenie urządzeń w Domoticz dla sterowania
        if 1 not in Devices:
            Domoticz.Device(Name="Room Temperature", Unit=1, TypeName="Temperature").Create()
        if 2 not in Devices:
            Domoticz.Device(Name="Power Control", Unit=2, Type=244, Subtype=73, Switchtype=0).Create()
        if 3 not in Devices:
            Domoticz.Device(Name="Mode Control", Unit=3, Type=244, Subtype=62, Switchtype=18, Options={"LevelActions": "|||||", "LevelNames": "Off|Fan|Heat|Cool|Dry|Auto", "LevelOffHidden": "false", "SelectorStyle": "0"}).Create()
        if 4 not in Devices:
            Domoticz.Device(Name="Set Temperature", Unit=4, Type=242, Subtype=1).Create()  # Selector for set temperature

        self.wait_for_server()

    def onStop(self):
        Domoticz.Log("AirCon Status Plugin Stopped")

    def onHeartbeat(self):
        now = datetime.datetime.now()
        if now < self.nextpoll:
            Domoticz.Debug(f"Awaiting next poll: {self.nextpoll}")
            return

        # Wywołaj adres localhost:8888/hisense/status
        response = self.get_status()
        if response:
            self.update_devices(response)

        self.postponeNextPool(self.pollinterval)

    def onCommand(self, Unit, Command, Level, Color):
        if Unit == 2:  # Power Control
            self.control_power(Command)
        elif Unit == 3:  # Mode Control
            self.control_mode(Level)
        elif Unit == 4:  # Set Temperature
            self.set_temperature(Level)

    def wait_for_server(self):
        # Sprawdzanie dostępności serwera
        for attempt in range(10):
            try:
                response = requests.get(self.api_url, timeout=5)
                if response.status_code == 200:
                    Domoticz.Log("AirCon server is up and running")
                    return True
            except requests.exceptions.RequestException:
                Domoticz.Log(f"Waiting for AirCon server... Attempt {attempt + 1}/10")
                time.sleep(5)
        
        Domoticz.Error("AirCon server failed to start or is not reachable")
        return False

    def get_status(self):
        try:
            # Wysłanie żądania GET do API
            response = requests.get(self.api_url, timeout=10)
            if response.status_code == 200:
                return response.json()  # Zwróć odpowiedź JSON
            else:
                Domoticz.Error(f"Error fetching status: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            Domoticz.Error(f"Error fetching status: {str(e)}")
            return None

    def control_power(self, command):
        # Wysyłanie komendy włączania/wyłączania
        value = "ON" if command.upper() == "ON" else "OFF"
        url = f"{self.command_url}?property=t_power&value={value}"
        self.send_command(url)
        Domoticz.Log(f"Power command sent: {value}")
        self.update_power_state(value)

    def control_mode(self, level):
        modes = {10: "FAN", 20: "HEAT", 30: "COOL", 40: "DRY", 50: "AUTO"}
        mode = modes.get(level, "OFF")
        url = f"{self.command_url}?property=t_work_mode&value={mode}"
        self.send_command(url)
        Domoticz.Log(f"Mode command sent: {mode}")
        self.update_mode_state(mode)

    def set_temperature(self, temp_celsius):
        url = f"{self.command_url}?property=t_temp&value={temp_celsius}&property=t_temptype&value=CELSIUS"
        self.send_command(url)
        Domoticz.Log(f"Temperature set to {temp_celsius}C")
        self.update_set_temperature_state(temp_celsius)

    def send_command(self, url):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                Domoticz.Log(f"Command successful: {url}")
            else:
                Domoticz.Error(f"Command failed: {url} - Status {response.status_code}")
        except requests.exceptions.RequestException as e:
            Domoticz.Error(f"Error sending command: {str(e)}")

    def update_devices(self, data):
        try:
            # Sprawdzenie czy odpowiedź zawiera dane urządzeń
            devices = data.get("devices", [])
            if len(devices) == 0:
                Domoticz.Error("No devices found in the response")
                return

            # Pobranie pierwszego urządzenia z listy
            device = devices[0]
            props = device.get("props", {})

            # Pobranie aktualnej temperatury (Room Temperature), stanu zasilania i trybu pracy
            room_temperature = props.get("f_temp_in", None)  # Odczyt room temperature
            power = props.get("t_power", None)  # Odczyt stanu zasilania
            mode = props.get("t_work_mode", None)  # Odczyt trybu pracy
            set_temperature = props.get("t_temp", None)  # Odczyt temperatury zadanej

            # Aktualizacja urządzenia dla aktualnej temperatury w pomieszczeniu
            if room_temperature is not None and 1 in Devices:
                Devices[1].Update(nValue=0, sValue=str(room_temperature))
                Domoticz.Log(f"Updated room temperature: {room_temperature}°C")

            # Aktualizacja urządzenia dla włączania/wyłączania
            if power is not None and 2 in Devices:
                nVal = 1 if power == "ON" else 0
                sVal = "On" if power == "ON" else "Off"
                Devices[2].Update(nValue=nVal, sValue=sVal)
                Domoticz.Log(f"Updated power state: {power} nvalue: {nVal}")

            # Aktualizacja urządzenia dla trybu pracy
            if mode is not None and 3 in Devices:
                mode_level = {"FAN": 10, "HEAT": 20, "COOL": 30, "DRY": 40, "AUTO": 50}.get(mode, 0)
                Devices[3].Update(nValue=mode_level, sValue=str(mode_level))
                Domoticz.Log(f"Updated work mode: {mode}")

            # Aktualizacja urządzenia dla temperatury zadanej
            if set_temperature is not None and 4 in Devices:
                Devices[4].Update(nValue=0, sValue=str(set_temperature))
                Domoticz.Log(f"Updated set temperature: {set_temperature}°C")

        except KeyError as e:
            Domoticz.Error(f"Key error in JSON response: {str(e)}")
        except Exception as e:
            Domoticz.Error(f"Error updating devices: {str(e)}")

    def update_power_state(self, value):
        nValue = 1 if value == "ON" else 0
        Devices[2].Update(nValue=nValue, sValue=str(value))

    def update_mode_state(self, mode):
        mode_level = {"FAN": 10, "HEAT": 20, "COOL": 30, "DRY": 40, "AUTO": 50}.get(mode, 0)
        Devices[3].Update(nValue=mode_level, sValue=str(mode_level))

    def update_set_temperature_state(self, temp_celsius):
        Devices[4].Update(nValue=0, sValue=str(temp_celsius))

    def postponeNextPool(self, seconds=3600):
        self.nextpoll = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        return self.nextpoll

# Funkcje wymagane przez Domoticz
def onStart():
    global _plugin
    _plugin = BasePlugin()
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onCommand(Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Color)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

