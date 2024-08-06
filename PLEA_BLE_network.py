from bluepy import btle
import subprocess
import time
import threading

# Define the UUIDs of the characteristics you want to subscribe to
DEVICE_MAC_ADDRESS = "84:FC:E6:6B:D6:C1"
NETWORK_NAMES_CH_UUID = "0fd59f95-2c93-4bf8-b5f0-343e838fa302"
NETWORK_CONNECT_CH_UUID = "15eb77c1-6581-4144-b510-37d09f4294ed"
NETWORK_MESSAGE_CH_UUID = "773f99ff-4d87-4fe4-81ff-190ee1a6c916"
NETWORK_COMMANDS_CH_UUID = "68b82c8a-28ce-43c3-a6d2-509c71569c44"


# Clas that handles network notifications
class NetworkNotificationDelegate(btle.DefaultDelegate):
    def __init__(self, network_connect_ch, network_commands_ch):
        super().__init__()
        self.network_connect_ch = network_connect_ch
        self.network_commands_ch = network_commands_ch

    def handleNotification(self, cHandle, data):
        if cHandle == self.network_connect_ch.getHandle():
            print("Notification from network_connect_ch:", data)
        elif cHandle == self.network_commands_ch.getHandle():
            print("Notification from network_commands_ch:", data)
            handle_network_commands(data)

def notification_loop(peripheral, stop_event):
    while not stop_event.is_set():
        try:
            if peripheral.waitForNotifications(1.0):    # Constantly listen for notifications
                continue
        except btle.BTLEDisconnectError:
            print("Notification loop detected disconnection.")
            stop_event.set()  # Signal the main thread that disconnection has occurred

# Connect functions
def connect_to_device():
    try:
        print("Attempting to connect to ESP32...")
        peripheral = btle.Peripheral(DEVICE_MAC_ADDRESS)
        print("Connected to ESP32")
        return peripheral
    except Exception as e:
        print(f"Failed to connect: {e}")
        return None

def connect_to_network_characteristics(peripheral):
    # Send characteristics #
    network_names_ch = peripheral.getCharacteristics(uuid=NETWORK_NAMES_CH_UUID)[0]
    network_message_ch = peripheral.getCharacteristics(uuid=NETWORK_MESSAGE_CH_UUID)[0]
    ###
    
    # Receive characteristics #
    network_connect_ch = peripheral.getCharacteristics(uuid=NETWORK_CONNECT_CH_UUID)[0]
    network_commands_ch = peripheral.getCharacteristics(uuid=NETWORK_COMMANDS_CH_UUID)[0]
    
    peripheral.setDelegate(NetworkNotificationDelegate(network_connect_ch, network_commands_ch))
    
    network_connect_ch_handle = network_connect_ch.getHandle() + 1
    peripheral.writeCharacteristic(network_connect_ch_handle, b'\x01\x00', withResponse=True)  # Enable notifications

    network_commands_ch_handle = network_commands_ch.getHandle() + 1
    peripheral.writeCharacteristic(network_commands_ch_handle, b'\x01\x00', withResponse=True)  # Enable notifications

    return network_names_ch, network_connect_ch, network_message_ch, network_commands_ch
###

# Network names #
def is_ethernet_connected(device):
    # Use nmcli to check if an Ethernet device is connected
    result = subprocess.run(['nmcli', '-g', 'GENERAL.STATE', 'device', 'show', device], capture_output=True, text=True)
    state = result.stdout.strip()
    return state == '100 (connected)'

def get_networks_string():
    networks = ""
    
    # List available Wi-Fi networks
    wifi_result = subprocess.run(['nmcli', '-t', '-f', 'SSID', 'device', 'wifi', 'list'], capture_output=True, text=True)
    wifi_networks = wifi_result.stdout.split('\n')
    
    for ssid in wifi_networks:
        if ssid.strip():  # Skip empty SSIDs
            networks += f"W:<<{ssid.strip()}>>"
    
    # List available Ethernet connections
    ethernet_result = subprocess.run(['nmcli', '-t', '-f', 'DEVICE,TYPE', 'device', 'status'], capture_output=True, text=True)
    ethernet_lines = ethernet_result.stdout.split('\n')
    
    for line in ethernet_lines:
        if 'ethernet' in line:
            parts = line.split(':')
            device_name = parts[0].strip()
            if is_ethernet_connected(device_name):
                networks += f"E:<<{device_name}>>"
    networks += '#'     # Tells the receiver the string is done
    return networks
###

# IP #
def get_ip_for_device(device):
    # Use nmcli to get IP address for a specific device
    result = subprocess.run(['nmcli', '-g', 'IP4.ADDRESS', 'device', 'show', device], capture_output=True, text=True)
    ip_address = result.stdout.strip()
    return ip_address if ip_address else "No IP assigned"
###


def handle_network_commands(network_command):
	
	#print(network_command)
	
    match network_command:
        case b's':   # Search for networks
            print("Search for networks")
            netwoeks_string = get_networks_string()
            print(netwoeks_string)
            return
        case "p":   # Get IP
            print("Get IP")
            return
        case "d":   # Disconnect from network
            print("Disconnect from network")
            return
        case _:
            print("Unknown command")
            return


def BLE_main():
    # Variables #
    peripheral = None
    new_network_command_flag = False
    #network_command = None
    ###

    # Declare wanted characteristics #
    # Declare network characteristics:
    network_names_ch, network_connect_ch, network_message_ch, network_commands_ch = None, None, None, None
    ###
    notification_thread = None      # Thread for handling incoming notifications
    stop_event = threading.Event()

    while True:
        if peripheral is None:  # We are not connected
            peripheral = connect_to_device()    # Try to connect
            if peripheral is not None:          # If we succeeded
                # Connect to wanted characteristics #
                # Connect to network characteristics
                network_names_ch, network_connect_ch, network_message_ch, network_commands_ch = connect_to_network_characteristics(peripheral)
                ###
                stop_event.clear()
                notification_thread = threading.Thread(target=notification_loop, args=(peripheral, stop_event))
                notification_thread.daemon = True
                notification_thread.start()
            else:   # If we didn't succeed, retry
                print("Retrying in 5 seconds...")
                time.sleep(5)

        else:   # We are connected
            if stop_event.is_set(): # If we lost the connection
                print("Connection lost, attempting to reconnect...")
                if notification_thread:
                    notification_thread.join()
                try:
                    peripheral.disconnect() # Ensure disconnection
                except Exception as e:
                    print(f"Error during disconnection: {e}")
                peripheral = None
                time.sleep(5)
            else:
                try:    # Main loop handling
                    if new_network_command_flag == True:
                        print("Received command: ")
                        #handle_network_commands(network_command)
                        #new_network_command_flag = False
                except btle.BTLEDisconnectError:
                    print("Detected disconnection during main loop tasks.")
                    stop_event.set()

if __name__ == "__main__":
    BLE_main()
