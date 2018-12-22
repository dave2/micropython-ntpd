import uasyncio as asyncio
from asyn import Event
import pyb

class LED_Flashable():
    def __init__(self, loop, led_no):
        self.led = pyb.LED(led_no)
        self.event = Event()
        loop.create_task(self.flash_task())

    def flash(self, period_ms):
        if self.event.is_set():
            return
        self.event.set(period_ms)

    async def flash_task(self):
        while True:
            await self.event
            period_ms = self.event.value()
            self.event.clear()
            self.led.on()
            await asyncio.sleep_ms(period_ms)
            self.led.off()
