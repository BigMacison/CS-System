import os
import re
import subprocess

class ResticInterface:
  def __init__(self, keep_hourly: int = 0, keep_daily: int = 0, keep_weekly: int = 0):
    self.keep_hourly = keep_hourly
    self.keep_daily = keep_daily
    self.keep_weekly = keep_weekly
    self.restic_binary_path = "./bin/restic/restic.exe" if os.name == "nt" else "./bin/restic/restic"
    self.rclone_binary_path = "./bin/rclone/rclone.exe" if os.name == "nt" else "./bin/rclone/rclone"
  
  def backupPath(self, endpoint: str, snapshot_id, local_path: str, remote_path: str):
    # Uploads/backups a certain file/folder (specified as path) to remote path
    pass

  def restorePath(self):
    pass

  def getEndpointsFromConfig(self) -> list[str]:
    # Returns all names of the endpoints located in the rclone config and returns them in a list
    with open("./configs/rclone.conf", 'r') as f:
      return re.findall(r'$$([^$$]+)$$', f.text)

  def getSnapshots(self):
    pass

  def readRemoteFile(self):
    pass