from bluepy import btle
import time
import threading

# Define the UUIDs of the characteristics you want to subscribe to
CHARACTERISTIC_UUID_1 = "68b82c8a-28ce-43c3-a6d2-509c71569c44"  # Commands
CHARACTERISTIC_UUID_2 = "68b82c8a-28ce-43c3-a6d2-509c71569c44"  # Connect
DEVICE_MAC_ADDRESS = "84:FC:E6:6B:D6:C1"

class NotificationDelegate(btle.DefaultDelegate):
    def _init_(self, char1, char2):
        btle.DefaultDelegate._init_(self)
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

        char1 = peripheral.getCharacteristics(uuid=CHARACTERISTIC_UUID_1)[0]
        char2 = peripheral.getCharacteristics(uuid=CHARACTERISTIC_UUID_2)[0]

        peripheral.setDelegate(NotificationDelegate(char1, char2))

        char1_handle = char1.getHandle() + 1
        char2_handle = char2.getHandle() + 1

        peripheral.writeCharacteristic(char1_handle, b'\x01\x00', withResponse=True)
        peripheral.writeCharacteristic(char2_handle, b'\x01\x00', withResponse=True)

        return peripheral, char1, char2
    except Exception as e:
        print(f"Failed to connect: {e}")
        return None, None, None

def main():
    peripheral, char1, char2 = None, None, None
    notification_thread = None
    stop_event = threading.Event()

    while True:
        if peripheral is None:
            peripheral, char1, char2 = connect_to_device()

            if peripheral is not None:
                stop_event.clear()
                notification_thread = threading.Thread(target=notification_loop, args=(peripheral, stop_event))
                notification_thread.daemon = True
                notification_thread.start()
            else:
                print("Retrying in 5 seconds...")
                time.sleep(5)

        else:
            if stop_event.is_set():
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
                try:
                    print("Connected, performing main loop tasks...")
                    time.sleep(5)  # Simulate other main loop tasks
                except btle.BTLEDisconnectError:
                    print("Detected disconnection during main loop tasks.")
                    stop_event.set()

if _name_ == "_main_":
    main()