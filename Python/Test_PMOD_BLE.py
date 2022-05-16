""" To test the Pmod BLE, all messages received on Bluetooth are displayed, the string "ok" is sent as a response. """
 
# import modules
import Pmod_BLE as ble
import WF_SDK as wf # import WaveForms instruments
 
# define pins
ble.pins.tx = 4
ble.pins.rx = 3
ble.pins.rst = 5
ble.pins.status = 6

# turn on messages
ble.settings.DEBUG = True
 
try:
    # initialize the interface
    device_data = wf.device.open()
    # check for connection errors
    wf.device.check_error(device_data)
    ble.open()
    ble.reset(rx_mode="uart", tx_mode="uart", reopen=True)
    ble.reboot()
 
    while True:
        # check connection status
        if ble.get_status():
            # receive data
            data, sys_msg, error = ble.read(blocking=True, rx_mode="logic", reopen=False)
            # display data and system messages
            if data != "":
                print("data: " + data)  # display it
                ble.write_data("ok", tx_mode="pattern", reopen=False)  # and send response
            elif sys_msg != "":
                print("system: " + sys_msg)
            elif error != "":
                print("error: " + error)    # display the error
 
except KeyboardInterrupt:
    pass
finally:
    # close the device
    ble.close(reset=True)
    wf.device.close(device_data)
