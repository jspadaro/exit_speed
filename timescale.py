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
"""Timescale interface for exporting data."""

import multiprocessing
from typing import Optional
from typing import Tuple
from absl import flags
from absl import logging
import geohash
import gps_pb2
import psycopg2

FLAGS = flags.FLAGS
flags.DEFINE_string('timescale_db_spec',
                    'postgres://exit_speed:faster@cloud:/exit_speed',
                    'Postgres URI connection string.')

def ConnectToDB() -> psycopg2.extensions.connection:
  return psycopg2.connect(FLAGS.timescale_db_spec)


class Pusher(object):
  """Interface for publishing data to timescale."""

  def __init__(self,
               live_data: bool = True,
               start_process: bool = True):
    self.live_data = live_data
    if start_process:
      self.process = multiprocessing.Process(target=self.Loop, daemon=True)
    self.manager = multiprocessing.Manager()
    self.timescale_conn = None
    self.session_time = None
    self.track = None
    self.session_id = None
    self.lap_number_ids = {}
    self.lap_queue = multiprocessing.Queue()
    self.lap_duration_queue = multiprocessing.Queue()
    self.point_queue = self.manager.list()  # Used as LifoQueue.
    self.lap_id_first_points = {}

  def ExportSession(self, cursor: psycopg2.extensions.cursor):
    if not self.session_id:
      insert_statement = """
      INSERT INTO sessions (time, track, live_data)
      VALUES (%s, %s, %s)
      RETURNING id
      """
      args = (self.session_time.ToJsonString(), self.track, self.live_data)
      cursor.execute(insert_statement, args)
      self.session_id = cursor.fetchone()[0]

  def ExportLap(self, lap: gps_pb2.Lap, cursor: psycopg2.extensions.cursor):
    """Export the lap data to timescale."""
    insert_statement = """
    INSERT INTO laps (session_id, number)
    VALUES (%s, %s)
    RETURNING id
    """
    args = (self.session_id, lap.number)
    cursor.execute(insert_statement, args)
    self.lap_number_ids[lap.number] = cursor.fetchone()[0]

  def UpdateLapDuration(self,
                        lap_number: int,
                        duration: gps_pb2.Lap.duration,
                        cursor: psycopg2.extensions.cursor):
    """Exports lap duration to the Timescale backend."""
    update_statement = """
    UPDATE laps
    SET duration_ms = %s
    WHERE id = %s
    """
    args = (duration.ToMilliseconds(), self.lap_number_ids[lap_number])
    cursor.execute(update_statement, args)

  def GetElapsedTime(self, point: gps_pb2.Point, lap_id: int) -> int:
    if not self.lap_id_first_points.get(lap_id):
      self.lap_id_first_points[lap_id] = point
    first_point = self.lap_id_first_points[lap_id]
    return point.time.ToMilliseconds() - first_point.time.ToMilliseconds()

  def ExportPoint(self,
                  point: gps_pb2.Point,
                  lap_number: int,
                  cursor: psycopg2.extensions.cursor):
    """Exports point data to timescale."""
    insert_statement = """
    INSERT INTO points (time, session_id, lap_id, alt, speed, geohash, elapsed_duration_ms, tps_voltage, water_temp_voltage, oil_pressure_voltage, rpm, afr, fuel_level_voltage)
    VALUES             (%s,   %s,         %s,     %s,  %s,    %s,      %s,                  %s,          %s,                 %s,                   %s,  %s,  %s)
    """
    lap_id = self.lap_number_ids.get(lap_number)
    if lap_id:
      geo_hash = geohash.encode(point.lat, point.lon)
      elapsed_duration_ms = self.GetElapsedTime(point, lap_id)
      args = (point.time.ToJsonString(),
              self.session_id,
              lap_id,
              point.alt,
              point.speed * 2.23694,  # m/s to mph,
              geo_hash,
              elapsed_duration_ms,
              point.tps_voltage,
              point.water_temp_voltage,
              point.oil_pressure_voltage,
              point.rpm,
              point.afr,
              point.fuel_level_voltage)
      cursor.execute(insert_statement, args)
    else:
      # Point arrived on the queue before the lap.  Place it back in the
      # queue and we'll try again.
      self.point_queue.append((point, lap_number))

  def GetLapFromQueue(self) -> Optional[gps_pb2.Lap]:
    if self.lap_queue.qsize() > 0:
      return self.lap_queue.get()

  def GetLapDurationFromQueue(self) -> Optional[Tuple[int, int]]:
    if self.lap_duration_queue.qsize() > 0:
      return self.lap_duration_queue.get()

  def GetPointFromQueue(self) -> Tuple[gps_pb2.Point, int]:
    """Blocks until a point is ready to export."""
    while not self.point_queue:  # Queue is empty.
      pass
    return self.point_queue.pop()

  def Do(self):
    """One iteration of the infinite loop."""
    lap = None
    lap_number_und_duration = None
    point = None
    try:
      if not self.timescale_conn:
        self.timescale_conn = ConnectToDB()
      lap = self.GetLapFromQueue()
      lap_number_und_duration = self.GetLapDurationFromQueue()
      point_und_lap_number = self.GetPointFromQueue()
      with self.timescale_conn.cursor() as cursor:
        self.ExportSession(cursor)
        if lap:
          self.ExportLap(lap, cursor)
        if lap_number_und_duration:
          self.UpdateLapDuration(lap_number_und_duration[0],
                                 lap_number_und_duration[1],
                                 cursor)
        self.ExportPoint(point_und_lap_number[0],
                         point_und_lap_number[1],
                         cursor)
        self.timescale_conn.commit()
    except psycopg2.Error:
      logging.exception('Error writing to timescale database')
      # Repopulate queues on errors.
      if lap:
        self.lap_queue.put(lap)
      if lap_number_und_duration:
        self.lap_duration_queue.put(lap_number_und_duration)
      if point:
        self.point_queue.append(point_und_lap_number)
      self.timescale_conn = None  # Reset connection

  def Loop(self):
    """Tries to export point data to the timescale backend."""
    while True:
      self.Do()

  def Start(self, session_time, track):
    self.session_time = session_time
    self.track = track
    self.process.start()
