#!/usr/bin/python

import os
import log_files
import gps_pb2
from gps import *

gpsd = gps(mode=WATCH_ENABLE|WATCH_NEWSTYLE)


def PopulatePoint(report):
  point = gps_pb2.Point()
  point.lat = report.lat
  point.lon = report.lon
  point.alt = report.alt
  point.speed = report.speed
  point.time.FromJsonString(report.time)
  return point


class ExitSpeed(object):

  def __init__(self,
	       start_speed=4.5,  # 4.5 ms/ ~ 10 mph
	       ):
    self.start_speed = start_speed

    self.recording = False

    self.session = None
    self.current_lap = None

  def GetLap(self):
    if not self.current_lap:
      session = self.GetSession()
      lap = session.laps.add()
      self.current_lap = lap
    return self.current_lap

  def GetSession(self):
    if not self.session:
      self.session = gps_pb2.Session()
    return self.session

  def ProcessLap(self, point):
    lap = self.GetLap()
    lap.points.append(point)
    # TODO Lap start/finish

  def ProcessSession(self, point):
    session = self.GetSession()
    if point.speed > self.start_speed:
      self.ProcessLap(point)
      self.recording = True
    if point.speed < self.start_speed and self.recording:
      log_files.SaveSessionToDisk(session)

  def ProcessReport(self, report):
    # Mode 1 == no fix, 2 == 2D fix and 3 == 3D fix.
    if report['class'] == 'TPV' and report.mode == 3:
      point = PopulatePoint(report)
      self.ProcessSession(point)

  def Run(self):
    while True:
      report = gpsd.next()
      self.ProcessReport(report)

try:
  while True:
    es = ExitSpeed()
    es.Run()


except (KeyboardInterrupt, SystemExit): #when you press ctrl+c
  print "Done.\nExiting."
  gpsd.close()
