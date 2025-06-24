import asyncio
import os
import json
import time
from typing import Literal

from .ResticManager import ResticManager
from .ConfigManager import ConfigManager as cm
from .SubprocessHandler import SubprocessHandler

class ServerManager:
  
  def __init__(self, endpoint: str, server_name: str = "", keep_hourly: int = 0, keep_daily: int = 0, keep_weekly: int = 0):
    self.restic = ResticManager(endpoint, keep_hourly, keep_daily, keep_weekly)
    self.server_name = server_name
    self.keep_hourly = keep_hourly
    self.keep_daily = keep_daily
    self.keep_weekly = keep_weekly
    self.server_process = None
    self.host_history_file = ""
    os.makedirs("./cache", exist_ok=True)   # Creates directory if nonexistent

  async def _load_host_history(self):
    self.restic.downloadPath(f"/cssystem/{self.server_name}/host_history.json", "./cache/")   # Download existing server list (even if it doesn't exist on remote)
    with open("./cache/host_history.json", "rw") as f:
      if f.read() == "":
        self.host_history_file = []
        f.write("[]")
      else:
        self.host_history_file = json.loads(f.read())

  async def _save_host_history(self):
    with open("./cache/host_history.json", "rw") as f:
      f.write(json.dumps(self.host_history_file))
    self.restic.uploadPath("./cache/host_history.json", f"/cssystem/{self.server_name}/")

  async def _edit_server_list(self, action: Literal["remove", "append"]):
    self.restic.downloadPath("/cssystem/servers.json", "./cache/") # Download existing server list (even if it doesn't exist on remote)
    with open("./cache/servers.json", "rw") as f:
      if f.read() == "":   # if servers.json was newly created
        f_json = []
      else:
        f_json = json.loads(f.read())

      if action == "remove":
        f_json.remove(self.server_name)
      else:
        f_json.append(self.server_name)
      f.write(json.dumps(f_json, indent=4))
    self.restic.uploadPath("./cache/servers.json", f"/cssystem/")

  async def _downloadServer(self, callback_function=None, snapshot: str="latest"):
    os.makedirs(f"./Servers/{self.server_name}", exist_ok=True)
    self.restic.restoreRepo(f"/cssystem/{self.server_name}/repo", f"./Servers/{self.server_name}", callback_function, snapshot)

  async def _uploadServer(self, callback_function=None):
    self.restic.restoreRepo(f"./Servers/{self.server_name}/*", f"/cssystem/{self.server_name}/repo", callback_function, snapshot)

  async def createServer(self, start_command_windows: str, start_command_linux: str, stop_command: str, forward_port: int, env: dict):
    self.restic.createRemoteFolder(f"/cssystem/{self.server_name}/repo")
    self.restic.initRepo(f"/cssystem/{self.server_name}/repo")

    with open("./cache/server_config.json", "w") as f:   # Create temporary server_config.json, fill it, then upload it
      f.write(json.dumps({"start_command_windows": start_command_windows, "start_command_linux": start_command_linux, "stop_command": stop_command, "forward_port": forward_port, "env": env}, indent=4))
    self.restic.uploadPath("./cache/server_config.json", f"/cssystem/{self.server_name}/") 
    await self._edit_server_list(self.server_name, "append")
    
  async def deleteServer(self):
    self.restic.deleteRemotePath(f"/cssystem/{self.server_name}")
    await self._edit_server_list(self.server_name, "remove")
    
  async def getServers(self) -> list:
    self.restic.downloadPath("/cssystem/servers.json", "./cache/")   # Download existing server list (even if it doesn't exist on remote)
    with open("./cache/servers.json", "rw") as f:
      if f.read() == "":
        return []
      else:
        return json.loads(f.read())

  async def getServerConfig(self) -> dict:
    self.restic.downloadPath(f"/cssystem/{self.server_name}/server_config.json", "./cache/")
    with open("./cache/servers.json", "rw") as f:
      return json.loads(f.read())

  async def get_newest_host(self) -> dict:
    self.restic.downloadPath(f"/cssystem/{self.server_name}/host_history.json", "./cache/")   # Download existing server list (even if it doesn't exist on remote)
    with open("./cache/host_history.json", "rw") as f:
      if f.read() == "":
        return {}
      else:
        return json.loads(f.read())[-1]   # get newest element of list

  async def didNewestHostUpload(self) -> bool:
    await self._load_host_history()
    if self.host_history_file == [] or self.host_history_file[-1]["status"] == "uploaded":
      return True
    return False

  async def isClientNewestHost(self):
    await self._load_host_history()
    if self.host_history_file[-1]["client_id"] == cm().getClientId():
      return True
    return False

  async def setNewestHost(self):
    await self._load_host_history()
    if await self.didNewestHostUpload():
      self.host_history_file.append({"client_id": cm().getClientId(),"time": time.time(), "status": "hosting"})
      self._save_host_history()

  async def setNewestHostStatus(self):
    await self._load_host_history()
    if await self.isClientNewestHost:
      self.host_history_file[-1]["status"] = "uploaded"
      await self._save_host_history()

  async def forceSetNewestHostStatus(self):
    await self._load_host_history()
    self.host_history_file[-1]["status"] = "uploaded"
    await self._save_host_history()

  async def startServer(self, callback_function=None):
    await self._downloadServer(self.server_name, callback_function)
    server_config = await self.getServerConfig(self.server_name)
    if await self.didNewestHostUpload:
      await self.setNewestHost(self.server_name)
      start_command = server_config["start_command_windows"] if os.name == "nt" else server_config["start_command_linux"]
      self.server_process = SubprocessHandler(start_command.split(), server_config["env"])
      self.server_process.register_listener(callback_function)
      self.server_process.start()

      # TODO: Tunnel port here when tunneling class is ready

  async def stopServer(self, callback_function=None):
    server_config = await self.getServerConfig(self.server_name)
    await self.server_process.send_input(server_config["stop_command"])
    await self.server_process.wait_until_done()
    result = callback_function({"info": "server stopped"})
    if inspect.isawaitable(result):
      asyncio.run_coroutine_threadsafe(result, asyncio.get_event_loop())

  