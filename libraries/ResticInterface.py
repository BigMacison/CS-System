import os
import re
import asyncio
from .SubprocessHandler import SubprocessHandler
import json

class ResticInterface:
  def __init__(self, endpoint: str, password: str, keep_hourly: int = 0, keep_daily: int = 0, keep_weekly: int = 0):
    self.endpoint = endpoint
    self.password = password
    self.keep_hourly = keep_hourly
    self.keep_daily = keep_daily
    self.keep_weekly = keep_weekly
    self.process = None
    self.restic_binary_path = "./bin/restic/restic.exe" if os.name == "nt" else "./bin/restic/restic"
    self.rclone_binary_path = "./bin/rclone/rclone.exe" if os.name == "nt" else "./bin/rclone/rclone"
    self.rclone_config_path = os.getcwd() + "/configs/rclone.conf"
    self.env = {"RESTIC_PASSWORD": self.password, "RCLONE_CONFIG": self.rclone_config_path}
  
  async def backupRepo(self, local_path: str, remote_path: str, callback_function=None):
    # Uploads/backups a certain file/folder (specified as path) into a remote repository (can't be used simultaniously with restoreRepo())
    async with self._lock:
      self.process = SubprocessHandler([self.restic_binary_path, "-r", f"rclone:{self.endpoint}:{remote_path}", "--option", f"rclone.program={self.rclone_binary_path}", "--json", "backup", local_path], self.env)
      if callback_function is not None:
        process.register_listener(callback_function)
      await process.start()

  async def restoreRepo(self, remote_path:str, local_path:str, callback_function=None, snapshot:str="latest"):
    # Downloads/restores a certain file/folder (specified as path) from a remote repository (can't be used simultaniously with backupRepo())
    async with self._lock:
      self.process = SubprocessHandler([self.restic_binary_path, "-r", f"rclone:{self.endpoint}:{remote_path}", "--option", f"rclone.program={self.rclone_binary_path}", "--json", "restore", snapshot, "--target", local_path], self.env)
      if callback_function is not None:
        process.register_listener(callback_function)
      await process.start()

  async def wait_until_done(self):
    # use this function in combination with await, to wait till the program is done.
    await self.process.wait_until_done()

  def downloadPath(self, remote_path: str, local_path: str):
    # Downloads remote file/folder that isn't part of a repository.
    SubprocessHandler.run_once([self.rclone_binary_path, "sync", "--checksum", "--size-only", "--no-update-modtime", f"{self.endpoint}:{remote_path}", local_path], self.env)

  def uploadPath(self, local_path: str, remote_path: str):
    # Uploads file/folder to remote path, that isn't part of a repository.
    SubprocessHandler.run_once([self.rclone_binary_path, "sync", "--checksum", "--size-only", "--no-update-modtime", local_path, f"{self.endpoint}:{remote_path}"], self.env)

  @staticmethod
  def getEndpointsFromConfig() -> list[str]:
    # Returns all names of the endpoints located in the rclone config and returns them in a list
    with open("./configs/rclone.conf", 'r') as f:
      return re.findall(r'\[([^\]]+)\]', f.read())

  def getSnapshots(self, remote_path: str) -> list:
    # Gets all snapshots
    return json.loads(SubprocessHandler.run_once([self.restic_binary_path, "-r", f"rclone:{self.endpoint}:{remote_path}", "--option", f"rclone.program={self.rclone_binary_path}", "--json", "snapshots"], self.env))

  def initRepo(self, remote_path: str):
    # creates a repository at the specified path
    SubprocessHandler.run_once([self.restic_binary_path, "-r", f"rclone:{self.endpoint}:{remote_path}", "--option", f"rclone.program={self.rclone_binary_path}", "--json", "init"], self.env)

  def removeOldSnapshots(self, remote_path):
    SubprocessHandler.run_once([self.restic_binary_path, "-r", f"rclone:{self.endpoint}:{remote_path}", "--option", f"rclone.program={self.rclone_binary_path}", "--json", "forget", "--keep-hourly", self.keep_hourly, "--keep-daily", self.keep_daily, "--keep-weekly", self.keep_weekly, "--prune"], self.env)

  def isRepo(self, remote_path: str) -> bool:
    output_str = SubprocessHandler.run_once([self.restic_binary_path, "-r", f"rclone:{self.endpoint}:{remote_path}", "--option", f"rclone.program={self.rclone_binary_path}", "--json", "snapshots"], self.env)
    output_json = json.loads(output_str)
    if output_json["code"] == 10:
      return False
    return True