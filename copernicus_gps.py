# An implementation of a GPS driver for the Trimble Copernicus (1) GPS

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

import gps
from asyn import Event

class Copernicus_GPS(gps.GPS):
    _enable_sentences = {'GGA': (1<<0),
                        'GLL': (1<<1),
                        'VTG': (1<<2),
                        'GSV': (1<<3),
                        'GSA': (1<<4),
                        'ZDA': (1<<5),
                        'RMC': (1<<8),
                        'TF': (1<<9),
                        'BA': (1<<13)}

    class PPS_Mode:
        OFF = 0
        ON = 1
        FIX = 2
    class PPS_Polarity:
        ACTIVE_LOW = 0
        ACTIVE_HIGH = 1

    # we have some special events for config apply
    def __init__(self,uart):
        super().__init__(uart)
        self._nm_ack = Event()
        self._ps_ack = Event()

    # Additional incoming message processing (on to of gps.py)

    # PTNLRNM - Automatic Message Output (Response)
    async def _rx_ptnlrnm(self,segs):
        self._nm_ack.set()
        return

    # PTNLRPS - PPS Configuration (Response)
    async def _rx_ptnlrps(self,segs):
        self._ps_ack.set()
        return

    async def set_auto_messages(self,types,interval):
        # compute bitmask to enable messages
        bitmask = 0
        for type in types:
            bitmask |= self._enable_sentences[type]
        #print(bin(bitmask))
        # send the command
        fmt = 'PTNLSNM,{:04x},{:02d}'
        #print(fmt.format(bitmask,interval))
        print('gps: setting auto messages to',types,'every',interval,'seconds')
        await self._send(fmt.format(bitmask,interval))
        # wait for ack
        print('gps: awaiting messages config ack')
        await self._nm_ack
        self._nm_ack.clear()
        print('gps: messages config accepted')
        return

    async def set_pps_mode(self,mode,length_ns,polarity,cable_ns):
        fmt = 'PTNLSPS,{},{},{},{}'
        # length is in 1/100th of ns
        length_ns = int(length_ns/100)
        print('gps: setting PPS config')
        await self._send(fmt.format(mode,length_ns,polarity,cable_ns))
        print('gps: awaiting ack to PPS config')
        await self._ps_ack
        self._ps_ack.clear()
        print('gps: PPS config accepted')
        return
