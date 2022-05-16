""" To test the Pmod ALS, the ambient light intensity is read and displayed continuously. """

# import modules
import Pmod_ALS as als
import WF_SDK as wf # import WaveForms instruments
from time import sleep

# define pins
als.pins.cs = 8
als.pins.sdo = 9
als.pins.sck = 10

try:
    # initialize the interface
    device_data = wf.device.open()
    # check for connection errors
    wf.device.check_error(device_data)
    als.open()

    while True:
        # display measurements
        light = als.read_percent(rx_mode="static", reopen=True)
        print("static: " + str(light) + "%")
        light = als.read_percent(rx_mode="spi", reopen=True)
        print("spi: " + str(light) + "%")
        sleep(0.5)

except KeyboardInterrupt:
    pass
finally:
    # close the device
    als.close(reset=True)
    wf.device.close(device_data)
