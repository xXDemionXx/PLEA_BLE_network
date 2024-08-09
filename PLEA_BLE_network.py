from bluepy import btle
from bluepy.btle import Peripheral, UUID, DefaultDelegate
import subprocess
import time
import threading

# Define the UUIDs of the characteristics you want to subscribe to
DEVICE_MAC_ADDRESS = "84:FC:E6:6B:D6:C1"
NETWORK_SERVICE_UUID = "9fd1e9cf-97f7-4b0b-9c90-caac19dba4f8"
NETWORK_NAMES_CH_UUID = "0fd59f95-2c93-4bf8-b5f0-343e838fa302"
NETWORK_CONNECT_CH_UUID = "15eb77c1-6581-4144-b510-37d09f4294ed"
NETWORK_MESSAGE_CH_UUID = "773f99ff-4d87-4fe4-81ff-190ee1a6c916"
NETWORK_COMMANDS_CH_UUID = "68b82c8a-28ce-43c3-a6d2-509c71569c44"

# Class that handles network notifications
class NetworkNotificationDelegate(btle.DefaultDelegate):
    def __init__(self, network_connect_ch, network_commands_ch):
        super().__init__()
        self.network_connect_ch = network_connect_ch
        self.network_commands_ch = network_commands_ch
        self.connect_network_string = ""
        self.connect_network_string_finished = False

    def handleNotification(self, cHandle, data):
        if cHandle == self.network_connect_ch.getHandle():
            self.connect_network_string += data.decode('utf-8')
            if self.connect_network_string[-1] == '#':
                self.connect_network_string_finished = True
        elif cHandle == self.network_commands_ch.getHandle():
            handle_network_commands(data.decode('utf-8'))

def notification_loop(peripheral, stop_event):
    while not stop_event.is_set():
        try:
            if peripheral.waitForNotifications(1.0):  # Constantly listen for notifications
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

def network_service(peripheral):
    # Connect to the service
    network_service = peripheral.getServiceByUUID(UUID(NETWORK_SERVICE_UUID))
    
    # Send characteristics #
    network_names_ch = network_service.getCharacteristics(NETWORK_NAMES_CH_UUID)[0]
    network_message_ch = network_service.getCharacteristics(NETWORK_MESSAGE_CH_UUID)[0]
    ###
    
    # Receive characteristics #
    network_connect_ch = network_service.getCharacteristics(NETWORK_CONNECT_CH_UUID)[0]
    network_commands_ch = network_service.getCharacteristics(NETWORK_COMMANDS_CH_UUID)[0]
    
    delegate = NetworkNotificationDelegate(network_connect_ch, network_commands_ch)
    peripheral.setDelegate(delegate)
    
    network_connect_ch_handle = network_connect_ch.getHandle() + 1
    peripheral.writeCharacteristic(network_connect_ch_handle, b'\x01\x00', withResponse=True)  # Enable notifications

    network_commands_ch_handle = network_commands_ch.getHandle() + 1
    peripheral.writeCharacteristic(network_commands_ch_handle, b'\x01\x00', withResponse=True)  # Enable notifications

    return network_names_ch, network_connect_ch, network_message_ch, network_commands_ch, delegate

def BLE_send_networks_string(networks_string):
    string_length = len(networks_string)
    chunks_array = []

    # Size of chunks we can send over BLE is 20 bytes
    for i in range(string_length // 20):
        chunks_array.append(networks_string[i * 20 : (i + 1) * 20])
    
    if string_length % 20 != 0:  # If there is a leftover smaller than 20 chars
        chunks_array.append(networks_string[-(string_length % 20):])
    
    for chunk in chunks_array:  # Send the chunks over BLE
        network_names_ch.write(bytes(str(chunk), 'utf-8'))
        time.sleep(0.003)
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
    
    # Check if eth0 is physically connected
    result = subprocess.run(['sudo', 'ethtool', 'eth0'], capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if 'Link detected:' in line:
            # Check if the link is detected as yes
            if 'yes' in line:
                networks += f"E:<<eth0>>"
    networks += '#'  # Tells the receiver the string is done
    return networks
###

# IPv4 #
def get_ipv4_addresses():
    try:
        # Run the ip command to get IP address information
        result = subprocess.run(['ip', 'addr'], capture_output=True, text=True)
        
        interfaces = {}
        interface_name = None

        # Parse the output to extract IPv4 addresses
        for line in result.stdout.split('\n'):
            if line.startswith(' '):
                # This line contains IP address information
                if 'inet ' in line:  # Only consider 'inet' for IPv4
                    ip_address = line.strip().split()[1]
                    if interface_name:
                        interfaces[interface_name].append(ip_address)
            else:
                # This line contains the interface name
                if line:
                    parts = line.split(': ')
                    if len(parts) > 1:
                        interface_name = parts[1].split('@')[0]
                        if interface_name not in interfaces:
                            interfaces[interface_name] = []
        
        IPs_string = "<<IP info>>"
        for interface, addresses in interfaces.items():  # Corrected 'interface' to 'interfaces'
            IPs_string += f"<<{interface}: {', '.join(addresses)}>>"
        IPs_string += '#'
        return IPs_string

    except Exception as e:
        print(f"Error retrieving IP addresses: {e}")
        return ""
###

# Handle network commands #
def handle_network_commands(network_command):
    match network_command:
        case 's':  # Search for networks
            print("Search for networks")
            networks_string = get_networks_string()
            BLE_send_networks_string(networks_string)
            return
        case 'p':  # Get IP
            print("Get IP")
            IPv4_string = get_ipv4_addresses()
            IPv4_array = BLE_chop_string_to_chunks(IPv4_string, 20)
            BLE_send_array(IPv4_array, network_message_ch)
            return
        case 'd':  # Disconnect from network
            print("Disconnect from all networks")
            disconnect_all_networks()
            return
        case _:
            print("Unknown command")
            return
###

# Network #
def connect_to_network(network_info):
    # Incoming string looks like this:
    # If it's WiFi: <<W:>><<NetworkName>><<Password>>
    # If it's Eth:  <<E:>><<NetworkName>>
    #
    # Function takes in a string, chops it into type,
    # name and password and connects to it
    #
    network_info = network_info[:-3]  # Removes >>#
    network_info = network_info[2:]  # Removes <<
    network_info_list = network_info.split('>><<')  # Makes it a list
    
    if len(network_info_list) < 2:  # Validate the list length
        print("Error: network_info string is not in the expected format.")
        return
    
    network_type = network_info_list[0]
    network_name = network_info_list[1]
    
    if network_type == "W:":
        network_password = network_info_list[2]
        # Connect to WiFi
        result = subprocess.run(['nmcli', 'device', 'wifi', 'connect', network_name, 'password', network_password], capture_output=True, text=True)
        print(result)
        if result.returncode == 0:
            print(f"Successfully connected to Wi-Fi network {network_name}")
        else:
            print(f"Failed to connect to Wi-Fi network {network_name}")
            print(result.stderr)
    elif network_type == "E:":
        # Connect to Ethernet
        result = subprocess.run(['nmcli', 'device', 'connect', network_name], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Successfully connected to Ethernet network {network_name}")
        else:
            print(f"Failed to connect to Ethernet network {network_name}")
            print(result.stderr)
    else:
        print("Error: Unknown network type.")

def get_active_networks():
    result = subprocess.run(['nmcli', '-t', '-f', 'UUID,DEVICE', 'connection', 'show', '--active'],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error getting active connections: {result.stderr}")
        return []
    
    active_connections = []
    for line in result.stdout.strip().split('\n'):
        if line:
            uuid, device = line.split(':')
            active_connections.append((uuid, device))
    
    return active_connections

def disconnect_all_networks():
    active_connections = get_active_networks()
    for uuid, device in active_connections:
        if device != "lo":
           result = subprocess.run(['nmcli', 'device', 'down', device], capture_output=True, text=True)
           if result.returncode == 0:
              print(f"Disconnected {device} with UUID {uuid}")
           else:
              print(f"Failed to disconnect {device} with UUID {uuid}: {result.stderr}")

def get_networks_connection_status_string():
    try:
        # Run nmcli to get the status of network devices
        device_status_result = subprocess.run(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE', 'device', 'status'], capture_output=True, text=True)
        
        connected_devices = []
        for line in device_status_result.stdout.splitlines():
            device, type_, state = line.split(':')
            if state == 'connected':
                # Get the details of the active connection for this device
                connection_result = subprocess.run(['nmcli', '-t', '-f', 'NAME,DEVICE', 'connection', 'show', '--active'], capture_output=True, text=True)
                for conn_line in connection_result.stdout.splitlines():
                    conn_name, conn_device = conn_line.split(':')
                    if conn_device == device:
                        if type_ == 'wifi':
                            ssid_result = subprocess.run(['nmcli', '-t', '-f', 'SSID', 'device', 'wifi', 'list'], capture_output=True, text=True)
                            ssid = ''
                            for ssid_line in ssid_result.stdout.splitlines():
                                if ssid_line.startswith('SSID:'):
                                    ssid = ssid_line.split(':')[1].strip()
                                    break
                            connected_devices.append(f"W:{conn_name}")
                        else:
                            connected_devices.append(f"E:{conn_name}")

        if connected_devices:
            return "<<C>><<" + ", ".join(connected_devices) + ">>#"
        else:
            return "<<D>>#"		# Send all networks disconnected message
    
    except Exception as e:
        print(f"Error checking network connection: {e}")
        return "Error retrieving network status"
###

# BLE #
def BLE_chop_string_to_chunks(string, chunk_size):
	#
	# Takes in a string and chops it into an arraz
	# of chunks, size of chunk_size.
	#
	chunks_array = []
	string_length = len(string)

    # Size of chunks we can send over BLE is 20 bytes
	for i in range(string_length // chunk_size):
		chunks_array.append(string[i * chunk_size : (i + 1) * chunk_size])
		
	if string_length % chunk_size != 0:	# If there is a leftover smaller than 20 chars
		chunks_array.append(string[-(string_length % chunk_size):])
		
	return chunks_array

def BLE_send_array(array, characteristic):
	for entry in array:	# Send the chunks over BLE
		characteristic.write(bytes(str(entry), 'utf-8'))
		time.sleep(0.003)

def BLE_main():
    # Variables #
    peripheral = None
    global network_names_ch, network_connect_ch, network_message_ch, network_commands_ch, delegate
    last_connection_status = ""
    #current_connection_status = ""
    ###
    
    # Declare wanted characteristics #
    notification_thread = None  # Thread for handling incoming notifications
    stop_event = threading.Event()
    
    while True:
        if peripheral is None:  # We are not connected
            peripheral = connect_to_device()  # Try to connect
            if peripheral is not None:  # If we succeeded
                # Connect to wanted characteristics #
                network_names_ch, network_connect_ch, network_message_ch, network_commands_ch, delegate = network_service(peripheral)
                ###
                stop_event.clear()
                notification_thread = threading.Thread(target=notification_loop, args=(peripheral, stop_event))
                notification_thread.daemon = True
                notification_thread.start()
            else:  # If we didn't succeed, retry
                print("Retrying in 5 seconds...")
                time.sleep(5)

        else:  # We are connected
            if stop_event.is_set():  # If we lost the connection
                print("Connection lost, attempting to reconnect...")
                if notification_thread:
                    notification_thread.join()
                try:
                    peripheral.disconnect()  # Ensure disconnection
                except Exception as e:
                    print(f"Error during disconnection: {e}")
                peripheral = None
                time.sleep(5)
            else:
                try:  # Main loop handling
                    if delegate.connect_network_string_finished:	# Check if we need to connect to a network
                        
                        connect_to_network(delegate.connect_network_string)
                        
                        # After connecting reset flag and string
                        delegate.connect_network_string = ""
                        delegate.connect_network_string_finished = False
                        
                    #current_connection_status = get_networks_connection_status_string()
                    #if last_connection_status != current_connection_status:		# Check if any network connection has changed
                        #print(current_connection_status)
                        #last_connection_status = current_connection_status
                        #net_status_array = BLE_chop_string_to_chunks(current_connection_status, 20)
                        #print(net_status_string)
                        #print(net_status_array)
                        #BLE_send_array(net_status_array, network_message_ch)
                     
                except btle.BTLEDisconnectError:
                    print("Detected disconnection during main loop tasks.")
                    stop_event.set()
###

if __name__ == "__main__":
    BLE_main()
