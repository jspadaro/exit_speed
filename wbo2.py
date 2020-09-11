#!/usr/bin/python3
# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Parser for wbo2.

https://www.wbo2.com/sw/logger.htm Frame and byte info.
"""

import multiprocessing
from typing import Generator
from typing import Text
from absl import app
from absl import flags
import serial

FLAGS = flags.FLAGS
flags.DEFINE_float('stoichiometric', 14.7,
                   'This is used to convert the Lambda_16 bytes into '
                   'an A/F ratio. This should be changed based on fuel.'
                   'Petrol 14.7, LGP 15.5, Methanol 6.4, Diesel 14.5')
# http://techedge.com.au/vehicle/wbo2/wblambda.htm

FRAME_SIZE = 28
# {'frame_type': (slice_left, slice_right)}
# pylint: disable=bad-continuation
# pylint: disable=bad-whitespace
FRAME_FORMAT = {
  'header':         (0, 2),    # Bytes 1 & 2
  'sequence':       (2, 3),    # Byte 3
  'tick':           (3, 5),    # Bytes 4 & 5
  'lambda_16':      (5, 7),    # Bytes 6 & 7
  'ipx':            (7, 9),    # Bytes 8 & 9
  'user_1':         (9, 11),   # Bytes 10 & 11
  'user_2':         (11, 13),  # Bytes 11 & 13
  'user_3':         (13, 15),  # Bytes 13 & 14
  'thermocouple_1': (15, 17),  # Bytes 16 & 17
  'thermocouple_2': (17, 19),  # Bytes 18 & 19
  'thermocouple_3': (19, 21),  # Bytes 20 & 21
  'thermistor':     (21, 23),  # Bytes 22 & 23
  'rpm_count':      (23, 25),  # Bytes 24 & 25
  'status':         (25, 27),  # Bytes 26 & 27
  'crc':            (27, 28),  # Byte 28
}
# pylint: enable=bad-continuation
# pylint: enable=bad-whitespace


def FindFrameStart(ser) -> bytes:
  """Find the frame's header start bytes based on the terminal stream."""
  while True:
    header_byte_1 = None
    header_byte_2 = None
    byte = ser.read()
    if byte[0] == 0x5a:
      header_byte_1 = byte
    if header_byte_1:
      byte = ser.read()
      if byte[0] == 0xa5:
        header_byte_2 = byte
      else:
        header_byte_1 = None  # Reset, perhaps another byte was set to 0x5a.
    if header_byte_1 and header_byte_2:
      return header_byte_1 + header_byte_2 + ser.read(FRAME_SIZE - 2)


def CheckFrame(frame) -> bool:
  return sum(frame) & 0b11111111 == 0xFF


def ReadSerial(ser) -> Generator[bytes, None, None]:
  yield FindFrameStart(ser)
  while True:
    frame = ser.read(FRAME_SIZE)
    if CheckFrame(frame):
      yield frame


def GetBytes(frame: bytes, frame_key: Text) -> float:
  """Converts byte data into something usable."""
  low, high = FRAME_FORMAT[frame_key]
  frame_bytes = frame[low:high]
  if 'lambda_16' == frame_key:
    return Lambda16ToAFR(int.from_bytes(frame_bytes, 'big'))
  if 'rpm_count' == frame_key:
    return RPMCountToRPM(int.from_bytes(frame_bytes, 'big'))
  elif 'user' in frame_key:
    return int.from_bytes(frame_bytes, 'big') / 8184 * 5
  elif 'thermocouple' in frame_key:
    return int.from_bytes(frame_bytes, 'big') / 1023 * 5 / 101
  return int.from_bytes(frame_bytes, 'big')


def Lambda16ToAFR(lambda_16: float) -> float:
  # http://techedge.com.au/vehicle/wbo2/wblambda.htm
  # https://www.wbo2.com/sw/lambda-16.htm
  # 14.7 = Unleaded stoichiometric point.
  return ((lambda_16 / 8192) + 0.5) * FLAGS.stoichiometric


def RPMCountToRPM(rpm_count: float) -> float:
  if rpm_count:
    us_between_pulse = rpm_count * 5
    minute = 60 * 10 ** 6  # 60 seconds > microseconds
    return minute / us_between_pulse / 3  # VR6 3 sparks per revolution.
  return 0


class WBO2(object):
  """Interface for the WBO2 wideband lambda/AFR controller."""

  def __init__(self, config, start_process=True):
    self.config = config
    self.values = {}
    self._AddConfigValues()
    if start_process:
      self.process = multiprocessing.Process(target=self.Loop, daemon=True)
      self.process.start()

  def _AddConfigValues(self):
    if self.config.get('wbo2'):
      for point_value in self.config['wbo2'].values():
        self.values[point_value] = multiprocessing.Value('d', 0.0)

  def Loop(self):
    with serial.Serial('/dev/ttyUSB0', 19200) as ser:
      for frame in ReadSerial(ser):
        for frame_key, point_value in self.config['wbo2'].items():
          self.values[point_value].value = GetBytes(frame, frame_key)


def main(unused_argv):
  with serial.Serial('/dev/ttyUSB0', 19200) as ser:
    for frame in ReadSerial(ser):
      rpm_count = GetBytes(frame, 'rpm_count')
      print(RPMCountToRPM(rpm_count))


if __name__ == '__main__':
  app.run(main)
