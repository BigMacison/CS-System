import os
import re
import asyncio
import json
from .SubprocessHandler import SubprocessHandler
from .LogHelper import LogHelper

class ResticManager:
  def __init__(self, endpoint: str, keep_hourly: int = 0, keep_daily: int = 0, keep_weekly: int = 0):
    self.endpoint = endpoint
    self.keep_hourly = keep_hourly
    self.keep_daily = keep_daily
    self.keep_weekly = keep_weekly
    self.process = None
    self._lock = asyncio.Lock()
    self.restic_binary_path = "./bin/restic/restic.exe" if os.name == "nt" else "./bin/restic/restic"
    self.rclone_binary_path = "./bin/rclone/rclone.exe" if os.name == "nt" else "./bin/rclone/rclone"
    self.rclone_config_path = os.getcwd() + "/configs/rclone.conf"
    self.env = {"RCLONE_CONFIG": self.rclone_config_path}
    self.logger = LogHelper()
  
  async def backupRepo(self, local_path: str, remote_path: str, callback_function=None):
    # Uploads/backups a certain file/folder (specified as path) into a remote repository (can't be used simultaniously with restoreRepo())
    await self.logger.passLog(2, f"Starting backup from '{local_path}' to '{remote_path}'")
    async with self._lock:
      self.process = SubprocessHandler([self.restic_binary_path, "-r", f"rclone:{self.endpoint}:{remote_path}", "--insecure-no-password", "--option", f"rclone.program={self.rclone_binary_path}", "--json", "backup", local_path], self.env)
      if callback_function is not None:
        self.process.register_listener(callback_function)
      self.process.start()
      await self.logger.passLog(2, f"Backup process started for '{local_path}'")

  async def restoreRepo(self, remote_path:str, local_path:str, callback_function=None, snapshot:str="latest"):
    # Downloads/restores a certain file/folder (specified as path) from a remote repository (can't be used simultaniously with backupRepo())
    await self.logger.passLog(2, f"Starting restore from '{remote_path}' to '{local_path}', snapshot='{snapshot}'")
    async with self._lock:
      self.process = SubprocessHandler([self.restic_binary_path, "-r", f"rclone:{self.endpoint}:{remote_path}", "--insecure-no-password", "--option", f"rclone.program={self.rclone_binary_path}", "--json", "restore", snapshot, "--target", local_path], self.env)
      if callback_function is not None:
        self.process.register_listener(callback_function)
      self.process.start()
      await self.logger.passLog(2, f"Restore process started for '{remote_path}'")

  async def wait_until_done(self):
    # use this function in combination with await, to wait till the program is done.
    await self.logger.passLog(3, "Waiting for process to complete...")
    await self.process.wait_until_done()
    await self.logger.passLog(2, "Process completed.")

  def createRemoteFolder(self, remote_path: str):
    # Creates a folder on the remote endpoint at the specified path
    asyncio.create_task(self.logger.passLog(2, f"Creating folder at remote path '{remote_path}'"))
    try:
      SubprocessHandler.run_once([self.rclone_binary_path, "mkdir", f"{self.endpoint}:{remote_path}"], self.env)
      asyncio.create_task(self.logger.passLog(2, f"Successfully created folder at '{remote_path}'"))
    except Exception as e:
      asyncio.create_task(self.logger.passLog(0, f"Failed to create remote folder at '{remote_path}': {str(e)}"))

  def downloadPath(self, remote_path: str, local_path: str):
    # Downloads remote file/folder that isn't part of a repository.
    asyncio.create_task(self.logger.passLog(2, f"Downloading path '{remote_path}' to '{local_path}'"))
    SubprocessHandler.run_once([self.rclone_binary_path, "sync", "--checksum", "--size-only", "--no-update-modtime", f"{self.endpoint}:{remote_path}", local_path], self.env)

  def uploadPath(self, local_path: str, remote_path: str):
    # Uploads file/folder to remote path, that isn't part of a repository.
    asyncio.create_task(self.logger.passLog(2, f"Uploading path '{local_path}' to '{remote_path}'"))
    SubprocessHandler.run_once([self.rclone_binary_path, "sync", "--checksum", "--size-only", "--no-update-modtime", local_path, f"{self.endpoint}:{remote_path}"], self.env)

  @staticmethod
  def getEndpointsFromConfig() -> list[str]:
    # Returns all names of the endpoints located in the rclone config and returns them in a list
    try:
      with open("./configs/rclone.conf", 'r') as f:
        return re.findall(r'\[([^\]]+)\]', f.read())
    except FileNotFoundError:
      asyncio.create_task(LogHelper().passLog(0, "Config file not found at './configs/rclone.conf'"))
      return []

  def getSnapshots(self, remote_path: str) -> list:
    # Gets all snapshots
    asyncio.create_task(self.logger.passLog(2, f"Getting snapshots from '{remote_path}'"))
    return json.loads(SubprocessHandler.run_once([self.restic_binary_path, "-r", f"rclone:{self.endpoint}:{remote_path}", "--insecure-no-password", "--option", f"rclone.program={self.rclone_binary_path}", "--json", "snapshots"], self.env))

  def initRepo(self, remote_path: str):
    # creates a repository at the specified path
    asyncio.create_task(self.logger.passLog(2, f"Initializing repository at '{remote_path}'"))
    SubprocessHandler.run_once([self.restic_binary_path, "-r", f"rclone:{self.endpoint}:{remote_path}", "--insecure-no-password", "--option", f"rclone.program={self.rclone_binary_path}", "--json", "init"], self.env)

  def removeOldSnapshots(self, remote_path):
    asyncio.create_task(self.logger.passLog(2, f"Removing old snapshots at '{remote_path}'"))
    SubprocessHandler.run_once([self.restic_binary_path, "-r", f"rclone:{self.endpoint}:{remote_path}", "--insecure-no-password", "--option", f"rclone.program={self.rclone_binary_path}", "--json", "forget", "--keep-hourly", self.keep_hourly, "--keep-daily", self.keep_daily, "--keep-weekly", self.keep_weekly, "--prune"], self.env)

  def isRepo(self, remote_path: str) -> bool:
    try:
      output_str = SubprocessHandler.run_once([self.restic_binary_path, "-r", f"rclone:{self.endpoint}:{remote_path}", "--insecure-no-password", "--option", f"rclone.program={self.rclone_binary_path}", "--json", "snapshots"], self.env)
      output_json = json.loads(output_str)
      is_repo = output_json["code"] != 10
      asyncio.create_task(self.logger.passLog(2, f"Checked repo at '{remote_path}': Exists = {is_repo}"))
      return is_repo
    except Exception as e:
      asyncio.create_task(self.logger.passLog(0, f"Failed to check repo at '{remote_path}': {str(e)}"))
      return False