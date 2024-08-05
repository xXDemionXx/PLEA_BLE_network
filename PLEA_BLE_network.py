from bluepy.btle import Peripheral, UUID
from bluepy.btle import DefaultDelegate
import time

BLE_MAC_ADDRESS = "84:FC:E6:6B:D6:C1"  # ESP_MAC
NETWORK_SERVICE_UUID = "9fd1e9cf-97f7-4b0b-9c90-caac19dba4f8"  # NETWORK_SERVICE_UUID
NETWORK_NAMES_CH_UUID = "0fd59f95-2c93-4bf8-b5f0-343e838fa302"  # NETWORK_NAMES_CH_UUID
NETWORK_CONNECT_CH_UUID = "68b82c8a-28ce-43c3-a6d2-509c71569c44"  # NETWORK_CONNECT_UUID
NETWORK_MESSAGE_CH_UUID = "773f99ff-4d87-4fe4-81ff-190ee1a6c916"
NETWORK_COMMANDS_CH_UUID = "68b82c8a-28ce-43c3-a6d2-509c71569c44"



class MyDelegate(DefaultDelegate):
    def _init_(self):
        DefaultDelegate._init_(self)

    def handleNotification(self, cHandle, data):
        print("Received data: {}".format(data))

def main():
    # Create peripheral object
    peripheral = Peripheral(BLE_MAC_ADDRESS)

    # Set delegate to handle notifications
    peripheral.setDelegate(MyDelegate())

    # Connect to the service
    service = peripheral.getServiceByUUID(UUID(NETWORK_SERVICE_UUID))

    # Connect to the receive characteristic
    receive_char = service.getCharacteristics(UUID(NETWORK_CONNECT_CH_UUID))[0]

    # Connect to the send characteristic
    send_char = service.getCharacteristics(UUID(NETWORK_NAMES_CH_UUID))[0]

    # Enable notifications on the receive characteristic
    receive_char_handle = receive_char.getHandle() + 1
    peripheral.writeCharacteristic(receive_char_handle, b"\x01\x00")

    print("Connected to ESP32 BLE server and notifications enabled")

    try:
        counter = 1
        while True:
            # Wait for notifications
            if peripheral.waitForNotifications(1.0):
                continue

            # Send counter value to the send characteristic every second
            send_char.write(bytes(str(counter), 'utf-8'))
            print("Sent data: {}".format(counter))
            counter += 1
            time.sleep(5)

    except KeyboardInterrupt:
        print("Disconnecting...")
    finally:
        peripheral.disconnect()

if __name__ == "__main__":
    main()