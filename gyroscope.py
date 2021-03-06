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
"""FXAS21002C gyroscope."""

from typing import Tuple
import math
import time
from absl import app
import board
import busio
import adafruit_fxas21002c


class Gyroscope(object):
  """Measures rotational rate."""

  def __init__(self):
    self.i2c = busio.I2C(board.SCL, board.SDA)
    self.sensor = adafruit_fxas21002c.FXAS21002C(self.i2c)

  def GetRotationalValues(self) -> Tuple[float, float, float]:
    """Returns Gyroscope values in degrees."""
    gyro_x, gyro_y, gyro_z = self.sensor.gyroscope
    return (math.degrees(gyro_x),
            math.degrees(gyro_y),
            math.degrees(gyro_z))


def main(unused_argv):
  gyro = Gyroscope()
  while True:
    x, y, z = gyro.GetRotationalValues()
    print('%.2f %.2f %.2f' % (x, y, z))
    time.sleep(1)


if __name__ == '__main__':
  app.run(main)
