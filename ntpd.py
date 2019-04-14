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

import uasyncio
#import uasyncio.udp
import usocket as socket
import uselect
from asyn import Event
gc.collect()

from led_flashable import LED_Flashable
from pyb import UART, RTC, Pin, ExtInt, SPI
import uctypes
gc.collect()

from syncedclock_rtc import SyncedClock_RTC
gc.collect()

from network import WIZNET5K

import micropython
micropython.alloc_emergency_exception_buf(100)

ntpstruct = {
    "mode": 0 | uctypes.BFUINT8 | 0 << uctypes.BF_POS | 3 << uctypes.BF_LEN,
    "vn": 0 | uctypes.BFUINT8 | 3 << uctypes.BF_POS | 3 << uctypes.BF_LEN,
    "li": 0 | uctypes.BFUINT8 | 6 << uctypes.BF_POS | 2 << uctypes.BF_LEN,
    "stratum": 1 | uctypes.UINT8,
    "poll": 2 | uctypes.INT8,
    "precision": 3 | uctypes.INT8,
    "root_delay": 4 | uctypes.UINT32,
    "root_dispersion": 8 | uctypes.UINT32,
    "reference_id": (12 | uctypes.ARRAY, 4 | uctypes.UINT8),
    "reference_timestamp_s": 16 | uctypes.UINT32,
    "reference_timestamp_frac": 20 | uctypes.UINT32,
    "origin_timestamp_s": 24 | uctypes.UINT32,
    "origin_timestamp_frac": 28 | uctypes.UINT32,
    "receive_timestamp_s": 32 | uctypes.UINT32,
    "receive_timestamp_frac": 36 | uctypes.UINT32,
    "transmit_timestamp_s": 40 | uctypes.UINT32,
    "transmit_timestamp_frac": 44 | uctypes.UINT32
}

_NTP_LI_NOWARN = const(0)
_NTP_LI_PLUSONE = const(1)
_NTP_LI_MINUSONE = const(2)
_NTP_LI_UNKNOWN = const(3)

_NTP_MODE_CLIENT = const(3)
_NTP_MODE_SERVER = const(4)

_NTP_STRATUM_INVALID = const(0)
_NTP_STRATUM_PRIMARY = const(1)
_NTP_STRATUM_UNSYNCHRONISED = const(16)

_NTP_REFID_0 = const(71) # 'G'
_NTP_REFID_1 = const(80) # 'P'
_NTP_REFID_2 = const(83) # 'S'
_NTP_REFID_3 = const(0) # zero-pad

# poller to ensure we get packets quickly
async def _get_ntp_packet(poller):
    while True:
        ev = poller.poll(0)
        if (ev):
            break
        await uasyncio.sleep(0)
    return ev[0][0].recvfrom(90)

# ensures we're inside scheduling when we start to interact
# with things
async def _ntpd():
    print("ntpd: starting synced clock service")
    clock = SyncedClock_RTC(gps_uart=UART(2,4800,read_buf_len=200),pps_pin=Pin(Pin.board.A1,Pin.IN))
    await clock.start()
    print("ntpd: listen on udp/123")
    nic = WIZNET5K(SPI('Y'),Pin.board.B4,Pin.board.B3)
    nic.ifconfig(('10.32.34.100','255.255.255.0','10.32.34.1','8.8.8.8'))
    while True:
        if (nic.isconnected()):
            break
        await uasyncio.sleep_ms(100)
    print("ntpd: nic reports connected")
    sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.bind(('',123))
    poller = uselect.poll()
    poller.register(sock,uselect.POLLIN)
    print("ntpd: starting loop for packets")
    # buffer for outbound packets
    sendbuf = bytearray(48)
    send_payload = uctypes.struct(uctypes.addressof(sendbuf),ntpstruct,uctypes.BIG_ENDIAN)
    send_payload.mode = _NTP_MODE_SERVER
    send_payload.vn = 4
    send_payload.li = _NTP_LI_NOWARN
    send_payload.root_delay = 0
    send_payload.root_dispersion = 0
    send_payload.poll = 6
    send_payload.precision = -9
    send_payload.reference_id[0] = _NTP_REFID_0
    send_payload.reference_id[1] = _NTP_REFID_1
    send_payload.reference_id[2] = _NTP_REFID_2
    send_payload.reference_id[3] = _NTP_REFID_3
    while True:
        packet = await _get_ntp_packet(poller)
        arrival = clock.now()
        refclk = clock.refclk()
        await uasyncio.sleep(0)
        ntp_payload = uctypes.struct(uctypes.addressof(packet[0]),ntpstruct,uctypes.BIG_ENDIAN)
        if (clock.isLocked()):
            send_payload.poll = ntp_payload.poll
            if (ntp_payload.poll < 6):
                send_payload.poll = 6
            if (ntp_payload.poll > 10):
                send_payload.poll = 10
            send_payload.stratum = _NTP_STRATUM_PRIMARY
            send_payload.reference_timestamp_s = refclk[0]+2208988800
            send_payload.reference_timestamp_frac = refclk[1]
            send_payload.receive_timestamp_s = arrival[0]+2208988800
            send_payload.receive_timestamp_frac = arrival[1]
            send_payload.origin_timestamp_s = ntp_payload.transmit_timestamp_s
            send_payload.origin_timestamp_frac = ntp_payload.transmit_timestamp_frac
            await uasyncio.sleep(0)
            transmit = clock.now()
            send_payload.transmit_timestamp_s = transmit[0]+2208988800
            send_payload.transmit_timestamp_frac = transmit[1]
        else:
            await uasyncio.sleep(0)
            send_payload.stratum = _NTP_STRATUM_UNSYNCHRONISED
            send_payload.reference_timestamp_s = 0
            send_payload.reference_timestamp_frac = 0
            send_payload.receive_timestamp_s = 0
            send_payload.receive_timestamp_frac = 0
            send_payload.origin_timestamp_s = 0
            send_payload.origin_timestamp_frac = 0
            send_payload.transmit_timestamp_s = 0
            send_payload.transmit_timestamp_frac = 0
            await uasyncio.sleep(0)
        # we should poll if it's okay to write, but anyway
        sock.sendto(sendbuf,packet[1])
        await uasyncio.sleep(0)

def _gc():
    while True:
        await uasyncio.sleep(10)
        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())

# simply ensure our main loop is a task and scheduler is running
def start():
    gc.collect()
    loop = uasyncio.get_event_loop()
    loop.create_task(_ntpd())
    loop.create_task(_gc())
    loop.run_forever()
