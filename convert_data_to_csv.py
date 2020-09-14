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
"""Converts a data log generated by exit speed to Traqmate's CSV format."""

import logging
import sys
import csv_lib
import replay_data

if __name__ == '__main__':
  logging.basicConfig(stream=sys.stdout, level=logging.INFO)
  assert len(sys.argv) == 2
  file_path = sys.argv[1]
  es = replay_data.ReplayLog(file_path)
  session = es.session()
  new_path = '%s.csv' % file_path
  print('%s > %s' % (file_path, new_path))
  csv_lib.ConvertProtoToTraqmate(session, new_path)
