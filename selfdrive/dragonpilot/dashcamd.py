#!/usr/bin/env python3.7
#
# courtesy of pjlao307 (https://github.com/pjlao307/)
# this is just his original implementation but
# in openpilot service form so it's always on
#
# with the highest bit rates, the video is approx. 0.5MB per second
# the default value is set to 2.56Mbps = 0.32MB per second
#
import os
import time
import datetime
import cereal.messaging as messaging
import subprocess
from selfdrive.swaglog import cloudlog
from common.params import Params, put_nonblocking
params = Params()

dashcam_videos_path = '/sdcard/dashcam/'
dashcam_duration = 60 # max is 180
bit_rates = 2560000 # max is 4000000
max_size_per_file = bit_rates/8*dashcam_duration # 2.56Mbps / 8 * 60 = 19.2MB per 60 seconds
freespace_limit = 0.15 # we start cleaning up footage when freespace is below 15%
shock_duration = 60

def main(gctx=None):
  sm = messaging.SubMaster(['dragonConf', 'health', 'thermal'])
  retry = 0
  folder_exists = False
  dashcam_allowed = True
  # make sure dashcam folder exists
  while not folder_exists:
    try:
      if not os.path.exists(dashcam_videos_path):
        os.makedirs(dashcam_videos_path)
      else:
        folder_exists = True
        break
    except OSError:
      pass
    if retry >= 5:
      folder_exists = True
      dashcam_allowed = False

    retry += 1
    time.sleep(5)

  while dashcam_allowed:
    sm.update()
    max_storage = (max_size_per_file/dashcam_duration) * sm['dragonConf'].dpDashcamHoursStored * 60 * 60
    if (sm['health'].ignitionLine or sm['health'].ignitionCan) and sm['dragonConf'].dpDashcam:
      now = datetime.datetime.now()
      file_name = now.strftime("%Y-%m-%d_%H-%M-%S")
      os.system("screenrecord --bit-rate %s --time-limit %s %s%s.mp4 &" % (bit_rates, dashcam_duration, dashcam_videos_path, file_name))
      start_time = time.time()
      try:
        used_spaces = get_used_spaces()
        last_used_spaces = used_spaces

        # we should clean up files here if use too much spaces
        # when used spaces greater than max available storage
        # or when free space is less than 10%
        # get health of board, log this in "thermal"
        if used_spaces >= max_storage or sm['thermal'].freeSpace < freespace_limit:
          # get all the files in the dashcam_videos_path path
          files = [f for f in sorted(os.listdir(dashcam_videos_path)) if os.path.isfile(dashcam_videos_path + f)]
          for file in files:
            sm.update(0)
            # delete file one by one and once it has enough space for 1 video, we stop deleting
            if used_spaces - last_used_spaces < max_size_per_file or sm['thermal'].freeSpace < freespace_limit:
              system("rm -fr %s" % (dashcam_videos_path + file))
              last_used_spaces = get_used_spaces()
            else:
              break
      except os.error as e:
        pass
      time_diff = time.time()-start_time
      # we start the process 1 second before screenrecord ended
      # to make sure there are no missing footage
      sleep_time = dashcam_duration-1-time_diff
      if sleep_time >= 0.:
        time.sleep(sleep_time)
    else:
      time.sleep(5)

def get_used_spaces():
  return sum(os.path.getsize(dashcam_videos_path + f) for f in os.listdir(dashcam_videos_path) if os.path.isfile(dashcam_videos_path + f))

def system(cmd):
  try:
    # cloudlog.info("running %s" % cmd)
    subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
  except subprocess.CalledProcessError as e:
    cloudlog.event("running failed",
                   cmd=e.cmd,
                   output=e.output[-1024:],
                   returncode=e.returncode)

if __name__ == "__main__":
  main()