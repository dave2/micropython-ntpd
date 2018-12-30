# A synchronised clock using STM32 as the clock source

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

import syncedclock
from copernicus_gps import Copernicus_GPS as GPS
from pyb import RTC, Pin, ExtInt
import uasyncio as asyncio
from asyn import Event
import utime
import uctypes

class SyncedClock_RTC(syncedclock.SyncedClock):

    # since pyb.RTC() is unreliable for reads, do it ourselves directly
    _RTC_BASE = const(0x40002800)
    _RTC_SSR_OFFSET = const(0x28)
    _rtc_ssr_struct = {
        "ss": 0 | uctypes.BFUINT32 | 0 << uctypes.BF_POS | 15 << uctypes.BF_LEN
    }
    _RTC_TR_OFFSET = const(0x00)
    _rtc_tr_struct = {
        "pm": 0 | uctypes.BFUINT32 | 22 << uctypes.BF_POS | 1 << uctypes.BF_LEN,
        "ht": 0 | uctypes.BFUINT32 | 20 << uctypes.BF_POS | 2 << uctypes.BF_LEN,
        "hu": 0 | uctypes.BFUINT32 | 16 << uctypes.BF_POS | 4 << uctypes.BF_LEN,
        "mnt": 0 | uctypes.BFUINT32 | 12 << uctypes.BF_POS | 3 << uctypes.BF_LEN,
        "mnu": 0 | uctypes.BFUINT32 | 8 << uctypes.BF_POS | 4 << uctypes.BF_LEN,
        "st": 0 | uctypes.BFUINT32 | 4 << uctypes.BF_POS | 3 << uctypes.BF_LEN,
        "su": 0 | uctypes.BFUINT32 | 0 << uctypes.BF_POS | 4 << uctypes.BF_LEN
    }
    _RTC_DR_OFFSET = const(0x04)
    _rtc_dr_struct = {
        "yt": 0 | uctypes.BFUINT32 | 20 << uctypes.BF_POS | 4 << uctypes.BF_LEN,
        "yu": 0 | uctypes.BFUINT32 | 16 << uctypes.BF_POS | 4 << uctypes.BF_LEN,
        "wdu": 0 | uctypes.BFUINT32 | 13 << uctypes.BF_POS | 3 << uctypes.BF_LEN,
        "mt": 0 | uctypes.BFUINT32 | 12 << uctypes.BF_POS | 1 << uctypes.BF_LEN,
        "mu": 0 | uctypes.BFUINT32 | 8 << uctypes.BF_POS | 4 << uctypes.BF_LEN,
        "dt": 0 | uctypes.BFUINT32 | 4 << uctypes.BF_POS | 2 << uctypes.BF_LEN,
        "du": 0 | uctypes.BFUINT32 | 0 << uctypes.BF_POS | 4 << uctypes.BF_LEN
    }


    _RTC_MAX = const(8192)

    # wrap initialiser
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self._uart = None
        self._pps_pin = None
        if kwargs is not None:
            if 'gps_uart' in kwargs:
                self._uart = kwargs['gps_uart']
            if 'pps_pin' in kwargs:
                self._pps_pin = kwargs['pps_pin']

        if (self._uart == None):
            raise ValueError("need a uart for the gps")
        if (self._pps_pin == None):
            raise ValueError("need a pin that gps sends 1pps to us on")

        # we also need the RTC device
        self._rtc = RTC()
        self._pps_event = Event()
        self._rtc_ssr = uctypes.struct(_RTC_BASE+_RTC_SSR_OFFSET,self._rtc_ssr_struct,uctypes.NATIVE)
        self._rtc_dr = uctypes.struct(_RTC_BASE+_RTC_DR_OFFSET,self._rtc_dr_struct,uctypes.NATIVE)
        self._pps_rtc = 0
        self._pps_discard = 0
        self._ss_offset = 0
        self._refclk = (0,0,0,0,0,0)

    # try to get some better perf out of this, it's staticish code
    @micropython.native
    def _pps(self,p):
        # grab RTC data when we tick
        # we need to pull this directly out of the registers because we don't want to
        # allocate ram, and the RTC() module does
        self._pps_rtc = self._rtc_ssr.ss
        # need to read DR to nothing to unlock shadow registers
        self._pps_discard = self._rtc_dr.du
        self._pps_event.set()
        return

    async def _wait_gpslock(self):
        try:
            while True:
                if (self._gps.isLocked()):
                    return True
                await asyncio.sleep(1)
        except asyncio.TimeoutError:
            print("syncedclock_rtc: failed to get lock, reinit gps")
        return False

    async def _wait_pps(self):
        try:
            await self._pps_event
            self._pps_event.clear()
            return True
        except asyncio.TimeoutError:
            print("syncedclock_rtc: failed to get pps event in time")
        return False

    # this will now be running in a thread, safe to do things which block
    async def _calibration_loop(self):
        # start RTC
        print("syncedclock_rtc: start rtc")
        self._rtc.init()
        # initalise gps
        self._gps = GPS(self._uart)
        ppsint = ExtInt(self._pps_pin, ExtInt.IRQ_RISING, Pin.PULL_NONE, self._pps)
        ppsint.disable()
        self._pps_event.clear()
        while True:
            print("syncedclock_rtc: initalise gps")
            await self._gps.set_auto_messages(['RMC'],1)
            await self._gps.set_pps_mode(GPS.PPS_Mode.FIX,42,GPS.PPS_Polarity.ACTIVE_HIGH,0)
            print("syncedclock_rtc: waiting for gps lock (30s)")
            res = await asyncio.wait_for(self._wait_gpslock(),30)
            if (res == False):
                continue
            print("syncedclock_rtc: gps locked, start pps interrupt and wait for pps (3s)")
            #self._pps_pin.irq(trigger=Pin.IRQ_RISING, handler=self._pps)
            ppsint.enable()
            res = await asyncio.wait_for(self._wait_pps(),3)
            if (res == False):
                print("syncedclock_rtc: pps signal never recieved, bad wiring?")
                print("syncedclock_rtc: terminating")
                return
            # PPS signal leads GPS data by about half a second or so
            # so the GPS data contains the *previous* second at this point
            # add 1 second and reset RTC
            print("syncedclock_rtc: pps pulse recieved, set RTC clock")
            date = self._gps.date()
            time = self._gps.time()
            # helpfully utime and pyb.RTC use different order in the tuple
            now = utime.localtime(utime.mktime((date[2],date[1],date[0],time[0],time[1],time[2],0,0)))
            self._rtc.datetime((now[0],now[1],now[2],0,now[3],now[4],now[5],0))
            print("syncedclock_rtc: rtc clock now",self._rtc.datetime())
            await asyncio.sleep(0)
            print("syncedclock_rtc: calibration loop started")
            # ensure we ignore the first cycle
            last_rtc_ss = -1
            # count 32 seconds and calculate the error
            count = 0
            tick_error = 0
            while True:
                # each time we get an PPS event, work out the ticks difference
                res = await asyncio.wait_for(self._wait_pps(),3)
                if (res == False):
                    print("syncedclock_rtc: lost pps signal, restarting")
                    self._locked = False
                    #self._pps_pin.irq(handler=None)
                    ppsint.disable()
                    break
                rtc_ss = self._pps_rtc
                # first pass, just discard the value
                if (last_rtc_ss == -1):
                    last_rtc_ss = rtc_ss
                    continue
                await asyncio.sleep(0)
                count += 1
                # compute the difference in ticks between this and the last
                tick_error += (rtc_ss - last_rtc_ss)
                last_rtc_ss = rtc_ss
                await asyncio.sleep(0)
                if (count == 32):
                    # if the tick error is +/-1 ticks, it's locked enough
                    # we're only then about 3.81ppm but that's close enough
                    if (self._locked == True and (tick_error > 1 or tick_error < -1)):
                        print("syncedclock_rtc: lost lock")
                        self._locked = False
                    await asyncio.sleep(0)
                    if (self._locked == False and (tick_error <= 1 and tick_error >= -1)):
                        print("syncedclock_rtc: locked with",self._rtc.calibration())
                        self._locked = True
                    await asyncio.sleep(0)
                    if (self._locked == True):
                        # cache current top-of-second offset and update reference clock datetime
                        self._ss_offset = (_RTC_MAX-rtc_ss)
                        self._refclk = self._rtc.datetime()
                    await asyncio.sleep(0)
                    if (self._locked == False):
                        print("syncedclock_rtc: error now",tick_error)
                    # the total ticks missing should be applied to the calibration
                    # we do this continously so we can ensure the clock is always remaining in sync
                    await asyncio.sleep(0)
                    try:
                        self._rtc.calibration(self._rtc.calibration()+tick_error)
                    except:
                        print("syncedclock_rtc: error too large, ignoring")
                    # allow us to to be interrupted now
                    await asyncio.sleep(0)
                    #print(rtc.calibration())
                    count = 0
                    tick_error = 0

    def _rtc_to_unixtime(self,rtc_tuple,rtc_offset):
        ts = utime.mktime((rtc_tuple[0], # year
                         rtc_tuple[1], # month
                         rtc_tuple[2], # day
                         rtc_tuple[4], # hour
                         rtc_tuple[5], # minute
                         rtc_tuple[6], # second
                         0,0)) + 946684800 # weekday and dayofyear are ignored
        tss = (_RTC_MAX - rtc_tuple[7]) + rtc_offset
        if tss >= _RTC_MAX:
            tss -= _RTC_MAX
            ts += 1
        if tss < 0:
            tss += _RTC_MAX
            ts -= 1
        return (ts,tss << 19)

    def now(self):
        if not self._locked:
            return None
        return self._rtc_to_unixtime(self._rtc.datetime(), self._ss_offset)

    def refclk(self):
        if not self._locked:
            return None
        return self._rtc_to_unixtime(self._refclk, self._ss_offset)

    async def start(self):
        super().start()
        loop = asyncio.get_event_loop()
        loop.create_task(self._calibration_loop())
        print("syncedclock_rtc: calibration loop created")
        await asyncio.sleep(0)
        return
