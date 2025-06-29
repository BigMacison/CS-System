import os
import random
import json

class ConfigManager:
  
  def __init__(self):
    self.config_path = "./configs/client_config.json"
    os.makedirs("./configs", exist_ok=True)   # Creates directory if nonexistent

    if not os.path.isfile("./configs/client_config.json"):
      with open("./configs/client_config.json", "w") as f:
        random_number_string = ''.join(random.choices('0123456789', k=30))
        f.write(json.dumps({"client_id": random_number_string, "endpoint": "", "server_name": ""}))

    config_json = json.loads(open("./configs/client_config.json", "r").read())
    self.client_id = config_json["client_id"]
    self.endpoint = config_json["endpoint"]
    self.server_name = config_json["server_name"]

  def _save_config(self):
    with open("./configs/client_config.json", "w") as f:
      f.write(json.dumps({"client_id": self.client_id, "endpoint": self.endpoint, "server_name": self.server_name}))

  def getClientId(self):
    return self.client_id

  def getEndpoint(self):
    return self.endpoint

  def getServerName(self):
    return self.server_name

  def setClientId(self, client_id):
    self.client_id = client_id
    self._save_config()

  def setEndpoint(self, endpoint):
    self.endpoint = endpoint
    self._save_config()

  def setServerName(self, server_name):
    self.server_name = server_name
    self._save_config()