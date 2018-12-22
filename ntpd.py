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
from pyb import UART
gc.collect()

from copernicus_gps import Copernicus_GPS as GPS

# real start ensures we're inside scheduling when we start to interact
# with things
def real_start():
    uart = UART(2,4800, read_buf_len=200)
    gps = GPS(uart)
    await gps.set_auto_messages(['RMC'],1)
    await gps.set_pps_mode(GPS.PPS_Mode.FIX,42,GPS.PPS_Polarity.ACTIVE_HIGH,0)
    while True:
        await asyncio.sleep(1)

# simply ensure our main loop is a task and scheduler is running
def start():
    loop = asyncio.get_event_loop()
    loop.create_task(real_start())
    loop.run_forever()
