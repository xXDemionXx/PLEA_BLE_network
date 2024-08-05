from bluepy import btle
import time
import threading

# Define the UUIDs of the characteristics you want to subscribe to
DEVICE_MAC_ADDRESS = "84:FC:E6:6B:D6:C1"
NETWORK_NAMES_CH_UUID = "0fd59f95-2c93-4bf8-b5f0-343e838fa302"
NETWORK_CONNECT_CH_UUID = "15eb77c1-6581-4144-b510-37d09f4294ed"
NETWORK_MESSAGE_CH_UUID = "773f99ff-4d87-4fe4-81ff-190ee1a6c916"
NETWORK_COMMANDS_CH_UUID = "68b82c8a-28ce-43c3-a6d2-509c71569c44"

class NetworkNotificationDelegate(btle.DefaultDelegate):
    def __init__(self, char1, char2):
        super().__init__()
        self.char1 = char1
        self.char2 = char2

    def handleNotification(self, cHandle, data):
        if cHandle == self.char1.getHandle():
            print("Notification from Characteristic 1:", data)
        elif cHandle == self.char2.getHandle():
            print("Notification from Characteristic 2:", data)

def notification_loop(peripheral, stop_event):
    while not stop_event.is_set():
        try:
            if peripheral.waitForNotifications(1.0):
                continue
            print("Performing other tasks in the notification loop")
        except btle.BTLEDisconnectError:
            print("Notification loop detected disconnection.")
            stop_event.set()  # Signal the main thread that disconnection has occurred

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

def BLE_main():
    peripheral = None

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
                try:
                    print("Connected, performing main loop tasks...")
                    time.sleep(5)  # Simulate other main loop tasks
                except btle.BTLEDisconnectError:
                    print("Detected disconnection during main loop tasks.")
                    stop_event.set()

if __name__ == "__main__":
    BLE_main()
