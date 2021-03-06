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
"""Common libaries."""

import gps
import gps_pb2


def PointDelta(point_a: gps_pb2.Point, point_b: gps_pb2.Point) -> float:
  """Returns the distance between two points."""
  return gps.EarthDistanceSmall((point_a.lat, point_a.lon),
                                (point_b.lat, point_b.lon))
