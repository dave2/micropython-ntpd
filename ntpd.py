# Main ntpd setup and loop
# call this from main.py on a MicroPython environment

# Copyright 2018 David Zanetti
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import gc

import uasyncio as asyncio
from asyn import Event
gc.collect()

from led_flashable import LED_Flashable
from pyb import UART, RTC, Pin, ExtInt
gc.collect()

from copernicus_gps import Copernicus_GPS as GPS
gc.collect()

import micropython
micropython.alloc_emergency_exception_buf(100)

pps_event = Event()
rtc = RTC()
# ensure memory is allocated for this
rtc_pps = (0,0,0,0,0,0,0,0)

# handler for PPS interupts, just pings an event
def _pps(p):
    # grab RTC data when we tick
    global rtc_pps
    rtc_pps = rtc.datetime()
    pps_event.set()
    return

# real start ensures we're inside scheduling when we start to interact
# with things
async def _ntpd():
    # PPS pin defintion
    pps_pin = Pin(Pin.board.A1, Pin.IN)
    # start RTC
    print("ntpd: starting rtc")
    rtc.init()
    # open and configure GPS
    print("ntpd: opening gps")
    uart = UART(2,4800, read_buf_len=200)
    gps = GPS(uart)
    await gps.set_auto_messages(['RMC'],1)
    await gps.set_pps_mode(GPS.PPS_Mode.FIX,42,GPS.PPS_Polarity.ACTIVE_HIGH,0)
    # major loop in the case of resets etc
    while True:
        # start with looking for a lock
        print("ntpd: waiting for gps lock")
        while True:
            if (gps.isLocked()):
                break
            await asyncio.sleep(1)
        # wait for a PPS pulse, so we know we're getting them
        print("ntpd: enabling pps interrupt and waiting for a PPS pulse")
        pps_pin.irq(trigger=Pin.IRQ_RISING, handler=_pps)
        await pps_event
        print("ntpd: PPS pulse detected, start calibration")
        # start in the middle
        rtc.calibration(0)
        # ensure we ignore the first cycle
        last_rtc_ss = -1
        # count 32 seconds and calculate the error
        count = 0
        tick_error = 0
        while True:
            # each time we get an PPS event, work out the ticks difference
            await pps_event
            pps_event.clear()
            # grab it before it changes
            rtc_ss = rtc_pps[7]
            # first pass, just discard the value
            if (last_rtc_ss == -1):
                last_rtc_ss = rtc_ss
                continue
            await asyncio.sleep(0)
            count += 1
            # compute the difference in ticks between this and the last
            tick_error += (rtc_ss - last_rtc_ss)
            print(last_rtc_ss, rtc_ss, tick_error)
            last_rtc_ss = rtc_ss
            if (count == 32):
                # if the tick error is 0, then accept as calibrated
                if (tick_error == 0):
                    break
                await asyncio.sleep(0)
                # the total ticks missing should be applied to the calibration
                rtc.calibration(rtc.calibration()+tick_error)
                print(rtc.calibration())
                count = 0
                tick_error = 0
        print("ntpd: rtc is calibrated with",rtc.calibration())
        while True:
            await asyncio.sleep(1)

def _gc():
    while True:
        await asyncio.sleep(10)
        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())

# simply ensure our main loop is a task and scheduler is running
def start():
    gc.collect()
    loop = asyncio.get_event_loop()
    loop.create_task(_ntpd())
    loop.create_task(_gc())
    loop.run_forever()
