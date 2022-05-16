""" Control an RGB LED with the ADP3450 """

# import modules
import Pmod_BLE as ble
import Pmod_ALS as als
import WF_SDK as wf
from time import time

# define connections
# PMOD BLE pins
ble.pins.rx = 3
ble.pins.tx = 4
ble.pins.rst = 5
ble.pins.status = 6
# PMOD ALS pins
als.pins.cs = 8
als.pins.sdo = 9
als.pins.sck = 10
# scope channels
SC_BAT_P = 1
SC_BAT_N = 2
SC_CHARGE = 4
# LED colors
LED_R = 0
LED_G = 1
LED_B = 2

# other parameters
scope_average = 10  # how many measurements to average with the scope
light_average = 10  # how many measurements to average with the light sensor
led_pwm_frequency = 1e03    # in Hz
out_data_update = 10    # output data update time [s]
ble.settings.DEBUG = True   # turn on messages from Pmod BLE
als.settings.DEBUG = True   # turn on messages from Pmod ALS
DEBUG = True                # turn on messages

# encoding prefixes
pre_red = 0b11
pre_green = 0b10
pre_blue = 0b01
pre_bat = 0b11
pre_charge = 0b10
pre_light = 0b01

class flags:
    red = 0
    green = 0
    blue = 0
    last_red = -1
    last_green = -1
    last_blue = -1
    start_time = 0

"""-------------------------------------------------------------------"""

def rgb_led(red, green, blue, device_data):
    """
        define the LED color in precentage
    """
    wf.pattern.generate(device_data, LED_R, wf.pattern.function.pulse, led_pwm_frequency, duty_cycle=red)
    wf.pattern.generate(device_data, LED_G, wf.pattern.function.pulse, led_pwm_frequency, duty_cycle=green)
    wf.pattern.generate(device_data, LED_B, wf.pattern.function.pulse, led_pwm_frequency, duty_cycle=blue)
    return

"""-------------------------------------------------------------------"""

def decode(data):
    """
        decode incoming Bluetooth data
    """
    # convert to list
    for character in list(data):
        # convert character to integer
        character = ord(character)
        # check prefixes and extract content
        if character & 0xC0 == pre_red << 6:
            flags.red = round((character & 0x3F) / 0x3F * 100)
        elif character & 0xC0 == pre_green << 6:
            flags.green = round((character & 0x3F) / 0x3F * 100)
        elif character & 0xC0 == pre_blue << 6:
            flags.blue = round((character & 0x3F) / 0x3F * 100)
        else:
            pass
    return

"""-------------------------------------------------------------------"""

def encode(data, prefix, lim_max, lim_min=0):
    """
        encode real numbers between lim_min and lim_max
    """
    try:
        # clamp between min and max limits
        data = max(min(data, lim_max), lim_min)
        # map between 0b000000 and 0b111111
        data = (data - lim_min) / (lim_max - lim_min) * 0x3F
        # append prefix
        data = (int(data) & 0x3F) | (prefix << 6)
        return data
    except:
        return 0

"""-------------------------------------------------------------------"""

try:
    # initialize the interface
    device_data = wf.device.open()
    # check for connection errors
    wf.device.check_error(device_data)
    if DEBUG:
        print(device_data.name + " connected")
    # start the power supplies
    supplies_data = wf.supplies.data()
    supplies_data.master_state = True
    supplies_data.state = True
    supplies_data.voltage = 3.3
    wf.supplies.switch(device_data, supplies_data)
    if DEBUG:
        print("power supplies started")
    # initialize the light sensor
    als.open()
    # initialize the Bluetooth module
    ble.open()
    ble.reboot()
    
    # turn off the lamp
    rgb_led(0, 0, 0, device_data)
    if DEBUG:
        print("entering main loop")

    """----------------"""

    # main loop
    while True:
        if ble.get_status():
            # check timing
            duration = time() - flags.start_time
            if duration >= out_data_update:
                # save current time
                flags.start_time = time()
                # measure the light intensity
                light = 0
                for _ in range(light_average):
                    light += als.read_percent(rx_mode="static", reopen=False)
                light /= light_average

                # encode and send the light intensity
                light = encode(light, pre_light, 100)
                ble.write_data(light, tx_mode="pattern", reopen=False)

                # read battery voltage
                batt_n = 0
                batt_p = 0
                for _ in range(scope_average):
                    batt_n += wf.scope.measure(device_data, SC_BAT_N)
                batt_n /= scope_average
                for _ in range(scope_average):
                    batt_p += wf.scope.measure(device_data, SC_BAT_P)
                batt_p /= scope_average
                battery_voltage = batt_p - batt_n

                # encode and send voltage
                battery_voltage = encode(battery_voltage, pre_bat, 5)
                ble.write_data(battery_voltage, tx_mode="pattern", reopen=False)

                # read charger state
                charger_voltage = 0
                for _ in range(scope_average):
                    charger_voltage += wf.scope.measure(device_data, SC_CHARGE)
                charger_voltage /= scope_average

                # encode and send voltage
                charger_voltage = encode(charger_voltage, pre_charge, 5)
                ble.write_data(charger_voltage, tx_mode="pattern", reopen=False)

            """----------------"""

            # process the data and set lamp color
            data, sys_msg, error = ble.read(blocking=True, rx_mode="logic", reopen=False)
            if len(data) > 0:
                # decode incoming data
                decode(data)
                # set the color
                if flags.red != flags.last_red:
                    flags.last_red = flags.red
                    rgb_led(flags.red, flags.green, flags.blue, device_data)
                    if DEBUG:
                        print("red: " + str(flags.red) + "%")
                elif flags.green != flags.last_green:
                    flags.last_green = flags.green
                    rgb_led(flags.red, flags.green, flags.blue, device_data)
                    if DEBUG:
                        print("green: " + str(flags.green) + "%")
                elif flags.last_blue != flags.blue:
                    flags.last_blue = flags.blue
                    rgb_led(flags.red, flags.green, flags.blue, device_data)
                    if DEBUG:
                        print("blue: " + str(flags.blue) + "%")
        else:
            rgb_led(0, 0, 0, device_data)

        """----------------"""     

except KeyboardInterrupt:
    # exit on Ctrl+C
    if DEBUG:
        print("keyboard interrupt detected")

finally:
    if DEBUG:
        print("closing used instruments")
    # turn off the lamp
    rgb_led(0, 0, 0, device_data)
    # close PMODs
    ble.close(True)
    als.close(True)
    # stop and reset the power supplies
    supplies_data = wf.supplies.data()
    supplies_data.master_state = False
    supplies_data.state = False
    supplies_data.voltage = 0
    wf.supplies.switch(device_data, supplies_data)
    wf.supplies.close(device_data)
    if DEBUG:
        print("power supplies stopped")
    # close device
    wf.device.close(device_data)
    if DEBUG:
        print("script stopped")
