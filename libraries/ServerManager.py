import asyncio
import os
import json
import time
import inspect
from typing import Literal

from .ResticManager import ResticManager
from .ConfigManager import ConfigManager as cm
from .SubprocessHandler import SubprocessHandler
from .LogHelper import LogHelper

class ServerManager:
  
  def __init__(self, endpoint: str, server_name: str = "", keep_hourly: int = 0, keep_daily: int = 0, keep_weekly: int = 0):
    self.restic = ResticManager(endpoint, keep_hourly, keep_daily, keep_weekly)
    self.server_name = server_name
    self.keep_hourly = keep_hourly
    self.keep_daily = keep_daily
    self.keep_weekly = keep_weekly
    self.server_process = None
    self.host_history_file = ""
    self.logger = LogHelper()
    os.makedirs("./cache", exist_ok=True)   # Creates directories if nonexistent
    os.makedirs("./Servers", exist_ok=True)

  async def _load_host_history(self):
    await self.logger.passLog(2, f"Downloading host history for server '{self.server_name}'.")
    self.restic.downloadPath(f"/cssystem/{self.server_name}/host_history.json", "./cache/")   # Download existing server list (even if it doesn't exist on remote)
    
    if not os.path.exists("./cache/host_history.json"):
      with open("./cache/host_history.json", 'w') as f:
        self.host_history_file = []
        f.write("[]")
    else:
      with open("./cache/host_history.json", "r") as f:
        self.host_history_file = json.loads(f.read())

  async def _save_host_history(self):
    await self.logger.passLog(2, "Saving host history to disk and uploading.")
    with open("./cache/host_history.json", "w") as f:
      f.write(json.dumps(self.host_history_file))
    self.restic.uploadPath("./cache/host_history.json", f"/cssystem/{self.server_name}/")

  async def _is_in_server_list(self):
    f_json = None
    self.restic.downloadPath("/cssystem/servers.json", "./cache/") # Download existing server list (even if it doesn't exist on remote)
    
    if not os.path.exists("./cache/servers.json"):
      return False

    with open("./cache/servers.json", "r") as f:
      f_json = json.loads(f.read())
      if self.server_name in f_json:
        return True

  async def _edit_server_list(self, action: Literal["remove", "append"]):
    f_json = None
    self.restic.downloadPath("/cssystem/servers.json", "./cache/") # Download existing server list (even if it doesn't exist on remote)
    
    if not os.path.exists("./cache/servers.json"):
      await self.logger.passLog(2, "Creating new server list file.")
      with open("./cache/servers.json", 'w') as f:
        f.write("[]")

    with open("./cache/servers.json", "r") as f:
      f_json = json.loads(f.read())
      if action == "remove":
        if self.server_name in f_json:
          f_json.remove(self.server_name)
          await self.logger.passLog(2, f"Removed '{self.server_name}' from server list.")
        else:
          await self.logger.passLog(3, f"Server '{self.server_name}' not found in list when attempting removal.")
      else:
        if self.server_name not in f_json:
          f_json.append(self.server_name)
          await self.logger.passLog(2, f"Added '{self.server_name}' to server list.")
        else:
          await self.logger.passLog(3, f"Server '{self.server_name}' already in list.")
      open("./cache/servers.json", "w").write(json.dumps(f_json, indent=4))
    self.restic.uploadPath("./cache/servers.json", f"/cssystem/")

  async def _download_server(self, callback_function=None, snapshot: str="latest"):
    await self.logger.passLog(2, f"Downloading server data for '{self.server_name}', snapshot: {snapshot}.")
    os.makedirs(f"./Servers/{self.server_name}", exist_ok=True)

    async def convert(line):
      await callback_function({"restic": json.loads(line)})

    await self.restic.restoreRepo(f"/cssystem/{self.server_name}/repo", ".", convert, f"{os.getcwd()}/Servers/{self.server_name}", snapshot)

  async def _upload_server(self, callback_function=None, snapshot: str="latest"):
    await self.logger.passLog(2, f"Uploading server data for '{self.server_name}'.")

    async def convert(line):
      await callback_function({"restic": json.loads(line)})

    await self.restic.backupRepo(".", f"/cssystem/{self.server_name}/repo", convert, f"{os.getcwd()}/Servers/{self.server_name}")

  async def wait_till_restic_done(self):
    await self.restic.wait_until_done()

  async def set_endpoint(self, endpoint):
    await self.restic.set_endpoint(endpoint)

  async def set_server_name(self, server_name):
    self.server_name = server_name

  async def create_server(self, start_command_windows: str, start_command_linux: str, stop_command: str, forward_port: int, env: dict):
    os.makedirs(f"./Servers/{self.server_name}", exist_ok=True)
    
    if await self._is_in_server_list():
      await self.logger.passLog(1, f"Server '{self.server_name}' already exists in server list. Creation skipped.")
      return
    
    conf_json = {"start_command_windows": start_command_windows, "start_command_linux": start_command_linux, "stop_command": stop_command, "forward_port": forward_port, "env": env}
    await self.logger.passLog(2, f"Creating server with config: {conf_json}")

    self.restic.createRemoteFolder(f"/cssystem/{self.server_name}/repo")
    self.restic.initRepo(f"/cssystem/{self.server_name}/repo")

    with open("./cache/server_config.json", "w") as f:   # Create temporary server_config.json, fill it, then upload it
      f.write(json.dumps(conf_json, indent=4))
    self.restic.uploadPath("./cache/server_config.json", f"/cssystem/{self.server_name}/")
    await self._edit_server_list("append")
    
  async def read_total_output(self):
    return await self.server_process.read_total_output()

  async def delete_server(self):
    await self.logger.passLog(2, f"Deleting server '{self.server_name}'.")
    self.restic.deleteRemotePath(f"/cssystem/{self.server_name}")
    await self._edit_server_list("remove")
    await self.logger.passLog(2, f"Server '{self.server_name}' deletion completed.")

  async def get_servers(self) -> list:
    await self.logger.passLog(2, "Fetching list of servers.")
    self.restic.downloadPath("/cssystem/servers.json", "./cache/")   # Download existing server list (even if it doesn't exist on remote)
    
    if not os.path.exists("./cache/servers.json"):
      await self.logger.passLog(2, "Servers list not found locally, creating empty list.")
      with open("./cache/servers.json", 'w') as f:
        f.write("[]")
    else:
      with open("./cache/servers.json", "r") as f:
        return json.loads(f.read())

  async def get_server_config(self) -> dict:
    self.restic.downloadPath(f"/cssystem/{self.server_name}/server_config.json", "./cache/")
    with open("./cache/server_config.json", "r") as f:
      return json.loads(f.read())

  async def get_newest_host(self) -> dict:
    self.restic.downloadPath(f"/cssystem/{self.server_name}/host_history.json", "./cache/")   # Download existing server list (even if it doesn't exist on remote)
    await self._load_host_history()
    if self.host_history_file == []:
      await self.logger.passLog(2, "Host history is empty.")
      return {}
    return self.host_history_file[-1]   # get newest element of list

  async def did_newest_host_upload(self) -> bool:
    await self._load_host_history()
    if self.host_history_file == [] or self.host_history_file[-1]["status"] == "uploaded":
      return True
    return False

  async def is_client_newest_host(self):
    await self._load_host_history()
    if not self.host_history_file == [] and self.host_history_file[-1]["client_id"] == cm().getClientId():
      return True
    return False

  async def set_newest_host(self):
    await self._load_host_history()
    if await self.did_newest_host_upload():
      self.host_history_file.append({"client_id": cm().getClientId(),"time": time.time(), "status": "hosting"})
      await self._save_host_history()

  async def set_newest_host_status(self):
    await self._load_host_history()
    if await self.is_client_newest_host():
      self.host_history_file[-1]["status"] = "uploaded"
      await self._save_host_history()

  async def forceset_newest_host_status(self):
    await self._load_host_history()
    if not self.host_history_file == []:
      self.host_history_file[-1]["status"] = "uploaded"
      await self._save_host_history()

  async def start_server(self, callback_function=None):
    await self._download_server(callback_function)
    await self.wait_till_restic_done()
    server_config = await self.get_server_config()
    if await self.did_newest_host_upload():
      await self.set_newest_host()
      start_command = server_config["start_command_windows"] if os.name == "nt" else server_config["start_command_linux"]
      self.server_process = SubprocessHandler(start_command.split(), server_config["env"])

      async def convert(line):
        await callback_function({"console": line})

      self.server_process.register_listener(convert)
      self.server_process.start()

      # TODO: Tunnel port here when tunneling class is ready

  async def stop_server(self, callback_function=None):
    server_config = await self.get_server_config()
    try:
      if server_config["stop_command"] == "":
        await self.server_process.stop()
      else:
        await self.server_process.send_input(server_config["stop_command"])
        await self.server_process.wait_until_done()
    except Exception:
      await self.logger.passLog(0, "Process stop exception")
    self.server_process = None
    result = callback_function({"info": "server stopped"})

    if inspect.isawaitable(result):
      asyncio.run_coroutine_threadsafe(result, asyncio.get_event_loop())

    await self._upload_server(callback_function)
    await self.wait_till_restic_done()

    await self.set_newest_host_status()

    # TODO: Stop tunneling port

  