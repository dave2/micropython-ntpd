# Generic class for synced clocks
# this should probably have some GPS handling as well, but eh

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

class SyncedClock():
    def __init__(self, *args, **kwargs):
        self._locked = False

    def isLocked(self):
        return self._locked

    # it should return a tuple of (unix seconds, float subseconds) or None
    # if not locked
    def now(self):
        return None

    # return the unixtime when this clock was last confirmed synced
    def refclk(self):
        return None

    # spawn any threads required and then exit from here
    async def start(self):
        print("start called in syncedclock")
        return
