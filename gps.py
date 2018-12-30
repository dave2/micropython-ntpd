# GPS main driver

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
from pyb import UART

class GPS():
    # initialiser
    def __init__(self,uart):
        # the uart must be pre-configured
        self._sreader = asyncio.StreamReader(uart)
        self._swriter = asyncio.StreamWriter(uart,{})
        self._lock = False
        # self._lattitude = 0.0
        # self._longitude = 0.0
        # self._altitude = 0.0
        self._time = (0,0,0)
        self._date = (0,0,0)
        loop = asyncio.get_event_loop()
        loop.create_task(self._reader())
        return

    def isLocked(self):
        return self._lock

    def date(self):
        return self._date

    def time(self):
        return self._time

    # these should be subclassed for the specific GPS unit, as
    # write commands vary between recievers
    async def set_auto_messages(self,types,interval):
        print("called set_auto_messages in parent")
        await asyncio.sleep(0)
        return

    async def set_pps_mode(self,mode,length_ns,polarity,cable_ns):
        print("called set_pps_mode in parent")
        await asyncio.sleep(0)
        return

    # format conversion functions
    def _nmea_lat_to_float(self,lat):
        m = float(lat[2:])
        d = float(lat[0:2])
        return (d+(m/60))
    def _nmea_long_to_float(self,long):
        m = float(long[3:])
        d = float(long[0:3])
        return (d+(m/60))
    def _nmea_time_to_list(self,time):
        h = int(time[0:2])
        m = int(time[2:4])
        s = int(time[4:6])
        #ss = float(time[6:])
        return (h, m, s)
    def _nmea_date_to_list(self,date):
        d = int(date[0:2])
        m = int(date[2:4])
        y = int(date[4:6])+2000
        return (d, m, y)

    # incoming sentence parsing

    # GPGGA "GPS Fix Data"
    async def _rx_gpgga(self,segs):
        # we're not very time critical, let other things run
        await asyncio.sleep(0)
        # update lock status
        was_lock = self._lock
        if(segs[6] == '0'):
            self._lock = False
        if(segs[6] == '1'):
            self._lock = True
        if (was_lock != self._lock):
            print('gps: lock status now ',self._lock)
        await asyncio.sleep(0)
        # update data
        if (self._lock):
            # self._lattitude = self._nmea_lat_to_float(segs[2])
            # if (segs[3] == 'S'):
            #     self._lattitude = -self._lattitude
            # self._longitude = self._nmea_long_to_float(segs[4])
            # if (segs[5] == 'W'):
            #     self._longitude = -self._longitude
            # self._altitude = float(segs[9])
            self._time = self._nmea_time_to_list(segs[1])
            #print('gps:',self._time,'pos:',self._lattitude,self._longitude,self._altitude)
        return

    # GPRMC "Recommended Minimum Specific GPS/Transit Data"
    def _rx_gprmc(self,segs):
        await asyncio.sleep(0)
        was_lock = self._lock
        if(segs[2] == 'A'):
            self._lock = True
        else:
            self._lock = False
        if (was_lock != self._lock):
            print('gps: locked status now',self._lock)
        await asyncio.sleep(0)
        # update navigation data
        if (self._lock):
            # self._lattitude = self._nmea_lat_to_float(segs[3])
            # if (segs[4] == 'S'):
            #     self._lattitude = -self._lattitude
            # self._longitude = self._nmea_long_to_float(segs[5])
            # if (segs[6] == 'W'):
            #     self._longitude = -self._longitude
            # self._altitude = 0.0
            self._time = self._nmea_time_to_list(segs[1])
            self._date = self._nmea_date_to_list(segs[9])
            #print('gps:',self._date,self._time,'pos:',self._lattitude,self._longitude,self._altitude)
        return

    async def _send(self,message):
        # write the message checksum present and send
        csum = 0
        for c in message:
            csum ^= ord(c)
        #print('${}*{:02x}\r\n'.format(message,csum))
        await self._swriter.awrite('${}*{:02x}\r\n'.format(message,csum))

    # read loop
    async def _reader(self):
        _rx_sentences = { 'GPGGA': self._rx_gpgga,
                          'GPRMC': self._rx_gprmc}
        print('gps: starting read loop')
        while True:
            line = await self._sreader.readline()
            try:
                line = line.decode('utf-8')
            except:
                continue
            # check it's valid first
            if (line[0] != '$' or line[-5] != '*'):
                continue
            # we don't use CRC processing because it's spendy in python
            # break up string stripping leading $ and trailing \r\n
            segs = line[1:-6].split(',')
            # this will call a method named like a message if it exists
            # apparently this is the 'python way' rather than an index
            # of messages to methods
            try:
                await getattr(self, '_rx_'+segs[0].lower())(segs)
            except:
                pass
