# Simple uasyncio LED flasher

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
