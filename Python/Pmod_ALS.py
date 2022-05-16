""" This module realizes communication with the Pmod ALS """

"""
    The ambient light sensor uses the SPI interface for communication,
    with three lines (chip select, serial data out and serial clock) and
    a clock frequency between 1MHz and 4MHz. The on-board analog to digital
    converter returns 2 bytes of data, most significant bit first,
    which contain 3 leading and 4 trailing zeros. The sensor saturates
    at the output value 127. The module also converts the raw data into
    percentage.
"""

import WF_SDK as wf # import WaveForms instruments
from time import sleep, time

"""-------------------------------------------------------------------"""

class pins:
    cs = 0  # CS pin of the Pmod
    sdo = 1  # SDO pin of the Pmod
    sck = 2  # SCK pin of the Pmod

class _flags_:
    _static_init_ = False

class settings:
    DEBUG = False
    _spi_frequency_ = 1e06
    _spi_mode_ = 0
    _msb_first_ = True
    _bytes_count_ = 2

"""-------------------------------------------------------------------"""
""" FUNCTIONS FOR INTERNAL USE """
"""-------------------------------------------------------------------"""

def _read_static_(bytes_count):
    """
        read a list of bytes on SPI using the logic analyzer and the pattern generator
    """
    period = 1 / settings._spi_frequency_
    # set chip select LOW
    wf.static.set_state(wf.device.data, pins.cs, False)
    # repeat for every bit
    bits = []
    for _ in range(8 * bytes_count):
        # get current time
        period_start = time()
        # provide a clock edge
        if settings._spi_mode_ < 2:
            wf.static.set_state(wf.device.data, pins.sck, True)
        else:
            wf.static.set_state(wf.device.data, pins.sck, False)
        # get data on first edge
        if settings._spi_mode_ / 2 == 0:
            bits.append(wf.static.get_state(wf.device.data, pins.sdo))
        # provide another clock edge
        if settings._spi_mode_ < 2:
            wf.static.set_state(wf.device.data, pins.sck, False)
        else:
            wf.static.set_state(wf.device.data, pins.sck, True)
        # get data on second edge
        if settings._spi_mode_ / 2 == 1:
            bits.append(wf.static.get_state(wf.device.data, pins.sdo))
        # delay if necessary
        try:
            sleep(period + period_start - time())
        except:
            pass
    # set chip select HIGH
    wf.static.set_state(wf.device.data, pins.cs, True)
    # decode bit list
    data = []
    for index_high in range(bytes_count):
        current_byte = []
        for index_low in range(8):
            # convert from bool
            if bits[round(index_high * 8 + index_low)]:
                bits[round(index_high * 8 + index_low)] = 1
            else:
                bits[round(index_high * 8 + index_low)] = 0
            current_byte.append(bits[round(index_high * 8 + index_low)])
        # invert byte if necessary
        if settings._msb_first_:
            current_byte = current_byte[::-1]
        # convert bit list in integer
        multiplier = 1
        data.append(0)
        for bit in current_byte:
            data[index_high] += (multiplier * bit)
            multiplier *= 2
    return data

"""-------------------------------------------------------------------"""

def _open_static_():
    """
        initialize the static I/O pins
    """
    # set data direction
    wf.static.set_mode(wf.device.data, pins.cs, output=True)
    wf.static.set_mode(wf.device.data, pins.sdo, output=False)
    wf.static.set_mode(wf.device.data, pins.sck, output=True)
    # set initial states
    wf.static.set_state(wf.device.data, pins.cs, True)
    if settings._spi_mode_ < 2:
        wf.static.set_state(wf.device.data, pins.sck, False)
    else:
        wf.static.set_state(wf.device.data, pins.sck, True)
    _flags_._static_init_ = True
    return

"""-------------------------------------------------------------------"""

def _close_static_():
    """
        reinitializes the static I/O pins
    """
    _flags_._static_init_ = False
    wf.static.set_mode(wf.device.data, pins.cs, output=False)
    wf.static.set_mode(wf.device.data, pins.sdo, output=False)
    wf.static.set_mode(wf.device.data, pins.sck, output=False)
    return

"""-------------------------------------------------------------------"""
""" USER FUNCTIONS """
"""-------------------------------------------------------------------"""

def open():
    """
        initializes the necessary instruments for the Pmod ALS
    """
    # start the power supplies
    if wf.supplies.state.off:
        supplies_data = wf.supplies.data()
        supplies_data.master_state = True
        supplies_data.state = True
        supplies_data.voltage = 3.3
        wf.supplies.switch(wf.device.data, supplies_data)
    if settings.DEBUG:
        print("ALS: device opened")
    return

"""-------------------------------------------------------------------"""

def close(reset=False):
    """
        closes all instruments if reset=True
    """
    if reset:
        # stop and reset the power supplies
        if wf.supplies.state.on:
            supplies_data = wf.supplies.data()
            supplies_data.master_state = True
            supplies_data.state = True
            supplies_data.voltage = 3.3
            wf.supplies.switch(wf.device.data, supplies_data)
            wf.supplies.close(wf.device.data)
        wf.static.close(wf.device.data)
    if settings.DEBUG:
        print("ALS: device closed")
    return

"""-------------------------------------------------------------------"""

def read(rx_mode="spi", reopen=False):
    """
        read raw data in spi/static mode
    """
    # read 2 bytes
    data = []
    if rx_mode == "spi":
        if not wf.protocol.spi.state.on or reopen:
            wf.protocol.spi.open(wf.device.data, cs=pins.cs, sck=pins.sck, miso=pins.sdo, clk_frequency=settings._spi_frequency_, mode=settings._spi_mode_, order=settings._msb_first_)
        data = wf.protocol.spi.read(wf.device.data, settings._bytes_count_, pins.cs)
        if reopen:
            wf.protocol.spi.close(wf.device.data)
    elif rx_mode == "static":
        if not _flags_._static_init_ or reopen:
            _open_static_()
        data = _read_static_(settings._bytes_count_)
        if reopen:
            _close_static_()
    try:
        msb = data[0] << 4
        lsb = data[1] >> 4
        # concatenate bytes without trailing and leading zeros
        result = msb | lsb
        return result
    except:
        return 0

"""-------------------------------------------------------------------"""

def read_percent(rx_mode="spi", reopen=False):
    """
        receive and convert raw data
    """
    data = read(rx_mode, reopen) * 100 / 255
    return round(data, 2)
