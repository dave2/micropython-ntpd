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
