""" This module realizes communication with the Pmod BLE """

"""
    The Pmod BLE is a Bluetooth Low Energy module, which communicates
    on UART interface, using a 115200bps baud rate. The controlling
    module contains functions to factory reset the device by putting
    it into command mode and sending the necessary commands. Besides that,
    it also can send and receive data, decoding the received bytes
    and separating the buffer into a list which contains only data
    and one which contains only system messages (starting and ending with "%").
"""

import time
import WF_SDK as wf # import WaveForms instruments

"""-------------------------------------------------------------------"""
""" SETTINGS, VARIABLES AND DATA TYPES """
"""-------------------------------------------------------------------"""

class pins:
    rx = 0  # RX pin of the Pmod
    tx = 1  # TX pin of the Pmod
    rst = 2  # RESET pin of the Pmod
    status = 3  # STATUS pin of the Pmod

class commands:
    command_mode = "$$$"    # enter command mode
    data_mode = "---\r"  # enter data mode
    rename = "S-,PmodBLE\r"  # set name to PmodBLE_XXXX
    factory_reset = "SF,1\r"    # factory reset
    high_power = "SGA,0\r"  # set high power output
    code = "SP,123456\r"    # set pin code to "123456"
    mode = "SS,C0\r"    # support device info + UART Transparent
    reboot = "R,1\r"    # reboots the device

class _flags_:
    _currently_sys_ = False
    _previous_msg_ = ""

class settings:
    DEBUG = False
    _baud_rate_ = 115200
    _record_multiplier_ = round(9.978)
    _buffer_size_ = 600    # max 32000 for the ADP3250
    _treshold_ = 0.5

class _word_type_:
    _start_ = 1
    _stop_ = 0
    _data_ = 0

"""-------------------------------------------------------------------"""
""" FUNCTIONS FOR INTERNAL USE """
"""-------------------------------------------------------------------"""

def _write_pattern_(data):
    """
        send UART data using the pattern generator
    """
    # cast data to integer list
    if type(data) == str:
        data = list(data)
        data = [ord(character) for character in data]
    elif type(data) == int:
        data = [data]
    # do for every element
    out_data = []
    for element in data:
        # convert to bit list
        element = [1 if element & (1 << (7 - n)) else 0 for n in range(8)]
        element = element[::-1]
        # append start and stop bits
        element.insert(0, 0)
        element.append(1)
        for bit in element:
            out_data.append(bit)
    # generate data
    wf.pattern.generate(wf.device.data, pins.rx, wf.pattern.function.custom, settings._baud_rate_, data=out_data, idle=wf.pattern.idle_state.high)
    wf.pattern.disable(wf.device.data, pins.rx)
    return

"""-------------------------------------------------------------------"""

def _read_logic_():
    """
        get UART data using the logic analyzer
    """
    # record buffer
    buffer, _ = wf.logic.record(wf.device.data, pins.tx)
    # get bits from buffer
    bits = []
    normalizer = max(buffer)
    for index_high in range(round(len(buffer) / settings._record_multiplier_)):
        bits.append(0)
        for index_low in range(settings._record_multiplier_):
            try:
                bits[index_high] += (buffer[round(index_high * settings._record_multiplier_ + index_low)] / normalizer)
            except:
                pass
        if bits[index_high] > settings._record_multiplier_ * settings._treshold_:
            bits[index_high] = 1
        else:
            bits[index_high] = 0
    # split list
    words = []
    for index_high in range(round(len(bits) / 10)):
        words.append([])
        for index_low in range(10):
            try:
                words[index_high].append(bits[round(index_high * 10 + index_low)])
            except:
                pass
    # decode word list
    data_struct = []
    for element in words:
        try:
            temp = _word_type_()
            temp._start_ = element[0]
            temp._stop_ = element[9]
            temp._data_ = 0
            multiplier = 1
            for bit in element[1:9]:
                temp._data_ += multiplier * bit
                multiplier *= 2
            data_struct.append(temp)
        except:
            pass
    data = []
    for element in data_struct:
        if element._start_ == 0 and element._stop_ == 1:
            data.append(element._data_)
    return data, ""

"""-------------------------------------------------------------------"""

def _open_logic_(blocking=False):
    """
        initialize the logic analyzer
        blocking (True/False) - read function is blocking in logic mode
    """
    # initialize the logic analizer interface
    wf.logic.open(wf.device.data, settings._baud_rate_ * settings._record_multiplier_, buffer_size=settings._buffer_size_)
    # configure triggering
    timeout = 0 if blocking else 1
    wf.logic.trigger(wf.device.data, True, pins.tx, timeout=timeout, rising_edge=False, count=0)
    return

"""-------------------------------------------------------------------"""
""" USER FUNCTIONS """
"""-------------------------------------------------------------------"""

def get_status():
    """
        returns True when the Pmod is connected and False otherwise
    """
    # check connection status
    if wf.static.get_state(wf.device.data, pins.status) == True:
        return False
    else:
        return True

"""-------------------------------------------------------------------"""

def open():
    """
        initializes the necessary instruments for the Pmod BLE
    """
    # start the power supplies
    if wf.supplies.state.off:
        supplies_data = wf.supplies.data()
        supplies_data.master_state = True
        supplies_data.state = True
        supplies_data.voltage = 3.3
        wf.supplies.switch(wf.device.data, supplies_data)
    # initialize the reset line
    wf.static.set_mode(wf.device.data, pins.rst, output=True)
    wf.static.set_mode(wf.device.data, pins.status, output=False)
    wf.static.set_state(wf.device.data, pins.rst, True)
    if settings.DEBUG:
        print("BLE: device opened")
    return

"""-------------------------------------------------------------------"""

def reboot():
    """
        hard reset the device
    """
    # pull down the reset line
    wf.static.set_state(wf.device.data, pins.rst, False)
    # wait
    time.sleep(1)
    # pull up the reset line
    wf.static.set_state(wf.device.data, pins.rst, True)
    if settings.DEBUG:
        print("BLE: rebooting")
    return

"""-------------------------------------------------------------------"""

def reset(rx_mode="uart", tx_mode="uart", reopen=False):
    """
        factory reset the device
        sets:   name to PmodBLE_XXXX
                high power mode
                UART transparent mode
    """
    # enter command mode
    write_command(commands.command_mode, rx_mode, tx_mode, reopen)
    if settings.DEBUG:
        print("BLE: entering command mode")
    time.sleep(3)
    # factory reset the Pmod
    success = write_command(commands.factory_reset, rx_mode, tx_mode, reopen)
    while success != True:
        success = write_command(commands.factory_reset, rx_mode, tx_mode, reopen)
        time.sleep(1)
    if settings.DEBUG:
        print("BLE: factory reset finished")
    # enter command mode
    write_command(commands.command_mode, rx_mode, tx_mode, reopen)
    if settings.DEBUG:
        print("BLE: entering command mode")
    time.sleep(3)
    # rename device
    write_command(commands.rename, rx_mode, tx_mode, reopen)
    if settings.DEBUG:
        print("BLE: device renamed: PmodBLE_XXXX")
    time.sleep(1)
    # set high power mode
    write_command(commands.high_power, rx_mode, tx_mode, reopen)
    if settings.DEBUG:
        print("BLE: high power mode enabled")
    time.sleep(1)
    # set communication mode
    write_command(commands.mode, rx_mode, tx_mode, reopen)
    if settings.DEBUG:
        print("BLE: UART transparent mode enabled")
    time.sleep(1)
    # exit command mode
    write_command(commands.data_mode, rx_mode, tx_mode, reopen)
    if settings.DEBUG:
        print("BLE: exiting command mode")
    time.sleep(3)
    return

"""-------------------------------------------------------------------"""

def close(reset=False):
    """
        reboots the deivice

        closes all instruments if reset=True
    """
    reboot()
    # restart the module
    if reset:
        # reset the instruments
        wf.pattern.close(wf.device.data)
        wf.logic.close(wf.device.data)
        wf.protocol.uart.close(wf.device.data)
        wf.static.close(wf.device.data)
        # stop and reset the power supplies
        if wf.supplies.state.on:
            supplies_data = wf.supplies.data()
            supplies_data.master_state = False
            supplies_data.state = False
            supplies_data.voltage = 0
            wf.supplies.switch(wf.device.data, supplies_data)
            wf.supplies.close(wf.device.data)
    if settings.DEBUG:
        print("BLE: device closed")
    return

"""-------------------------------------------------------------------"""

def write_command(command, rx_mode="uart", tx_mode="uart", reopen=False):
    """
        send a command to the Pmod BLE

        command list: Pmod_BLE.commands
    """
    # send the command
    write_data(command, tx_mode=tx_mode, reopen=reopen)
    # record response
    response, _, error = read(rx_mode=rx_mode, blocking=False, reopen=reopen)
    # analyze response
    response = response[0:3]
    if response == "ERR" or response == "Err" or error != "":
        return False
    return True

"""-------------------------------------------------------------------"""

def write_data(data, tx_mode="uart", reopen=False):
    """
        transmit data over UART using the protocol.uart, or the pattern instrument
    """
    # send data
    if tx_mode == "uart":
        if not wf.protocol.uart.state.on or reopen:
            wf.protocol.uart.open(wf.device.data, rx=pins.tx, tx=pins.rx, baud_rate=settings._baud_rate_)
        wf.protocol.uart.write(wf.device.data, data)
        if reopen:
            wf.protocol.uart.close(wf.device.data)
    elif tx_mode == "pattern":
        _write_pattern_(data)
    return

"""-------------------------------------------------------------------"""

def read(blocking=False, rx_mode="uart", reopen=False):
    """
        receive a message on UART using the protocol.uart, or the logic instrument
        blocking (True/False) blocks until message is received

        returns:    data, system message, error
    """
    # record incoming message
    data = []
    error = ""
    if rx_mode == "uart":
        if not wf.protocol.uart.state.on or reopen:
            wf.protocol.uart.open(wf.device.data, rx=pins.tx, tx=pins.rx, baud_rate=settings._baud_rate_)
        data, error = wf.protocol.uart.read(wf.device.data)
        if blocking:
            while len(data) <= 0 and len(error) <= 0:
                data, error = wf.protocol.uart.read(wf.device.data)
        if reopen:
            wf.protocol.uart.close(wf.device.data)
    elif rx_mode == "logic":
        if not wf.logic.state.on or reopen:
            _open_logic_(blocking)
        data, error = _read_logic_()
        if reopen:
            wf.logic.close(wf.device.data)
    # convert the integer list to string
    temp = ""
    for index in range(len(data)):
        data[index] = chr (data[index])
        temp += data[index]
    data = temp
    sys_msg = ""
    # check for system messages
    special = data.count("%")
    """---------------------------------"""
    if rx_mode == "uart":
        if special == 0:
            if _flags_._currently_sys_:
                # the middle of a system message
                _flags_._previous_msg_ = _flags_._previous_msg_ + data
                data = ""
            else:
                # not a system message
                pass
            """---------------------------------"""
        elif special == 2:
            # clear system message
            sys_msg = data
            data = ""
            _flags_._currently_sys_ = False
            _flags_._previous_msg_ = ""
            """---------------------------------"""
        else:
            # fragmented system message
            data_list = data.split("%")
            if _flags_._currently_sys_:
                # the end of the message
                sys_msg = _flags_._previous_msg_ + data_list[0] + "%"
                _flags_._currently_sys_ = False
                _flags_._previous_msg_ = ""
                data = data_list[1]
            else:
                # the start of the message
                _flags_._currently_sys_ = True
                _flags_._previous_msg_ = "%" + data_list[1]
                data = data_list[0]
    elif rx_mode == "logic":
        if special > 0:
            sys_msg = data
            data = ""
    return data, sys_msg, error
