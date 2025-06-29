import uvicorn
import webbrowser
import asyncio
import threading
from typing import Dict, Optional
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


from libraries.LogHelper import LogHelper
from libraries.DownloadHandler import DownloadHandler
from libraries.ResticInterface import ResticInterface
from libraries.SubprocessHandler import SubprocessHandler
from libraries.ConfigManager import ConfigManager
from libraries.ServerManager import ServerManager


app = FastAPI()
logger = LogHelper()

# ---------- WEBSITE ----------

@app.get("/")
async def index():
  return {"message": "Placeholder"}

# ---------- WEBSOCKETS ----------

websockets = {}

async def forward_to_websockets(json):
  for ws in list(websockets.values()):
    try:
      await ws.send_json(json)
    except Exception:
      pass

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
  await websocket.accept()
  ws_id = id(websocket)
  websockets[ws_id] = websocket

  try:
    while True:
      try:
        await asyncio.wait_for(websocket.receive_text(), timeout=30)
      except asyncio.TimeoutError:
        continue
  except Exception:
    if ws_id in websockets:
      del websockets[ws_id]
      print("Disconnected and removed!")

@app.get("/endpoints")
async def endpoints():
  return ResticInterface.getEndpointsFromConfig()

# ---------- MODELS ----------

class ServerCreateRequest(BaseModel):
  server_name: str
  endpoint: str
  start_cmd_win: Optional[str] = ""
  start_cmd_linux: Optional[str] = "./ping google.com"
  stop_cmd: Optional[str] = ""
  port: int = 8080
  env: Dict[str, str] = {}

class ServerIdentifier(BaseModel):
  server_name: str
  endpoint: str

# ---------- CONFIG ENDPOINTS ----------

@app.get("/config")
async def get_config():
  cm = ConfigManager()
  return {
    "client_id": cm.getClientId(),
    "endpoint": cm.getEndpoint(),
    "server_name": cm.getServerName()
  }

@app.post("/config")
async def update_config(client_id: str, endpoint: str, server_name: str):
  cm = ConfigManager()
  cm.setClientId(client_id)
  cm.setEndpoint(endpoint)
  cm.setServerName(server_name)
  return {"status": "updated"}

# ---------- SERVER ENDPOINTS ----------

@app.post("/server/create")
async def create_server(data: ServerCreateRequest):
  sm = ServerManager(data.endpoint, data.server_name)
  await sm.create_server(
    data.start_cmd_win, data.start_cmd_linux, data.stop_cmd, data.port, data.env
  )
  return {"status": "server_created"}

@app.post("/server/delete")
async def delete_server(data: ServerIdentifier):
  sm = ServerManager(data.endpoint, data.server_name)
  await sm.delete_server()
  return {"status": "server_deleted"}

@app.post("/server/start")
async def start_server(data: ServerIdentifier):
  sm = ServerManager(data.endpoint, data.server_name)
  
  async def forward(msg):
    print(msg)

  await sm.start_server(forward)
  return {"status": "server_started"}

@app.post("/server/stop")
async def stop_server(data: ServerIdentifier):
  sm = ServerManager(data.endpoint, data.server_name)
  
  async def forward(msg):
    print(msg)

  await sm.stop_server(forward)
  return {"status": "server_stopped"}

@app.post("/server/newest_host")
async def get_newest_host(data: ServerIdentifier):
  sm = ServerManager(data.endpoint, data.server_name)
  host = await sm.get_newest_host()
  return {"newest_host": host}

@app.post("/server/set_newest_host")
async def set_newest_host(data: ServerIdentifier):
  sm = ServerManager(data.endpoint, data.server_name)
  await sm.set_newest_host_status()
  return {"status": "set"}

@app.post("/server/force_set_newest_host")
async def force_set_newest_host(data: ServerIdentifier):
  sm = ServerManager(data.endpoint, data.server_name)
  await sm.forceset_newest_host_status()
  return {"status": "forced_set"}

@app.post("/server/is_newest")
async def is_client_newest(data: ServerIdentifier):
  sm = ServerManager(data.endpoint, data.server_name)
  is_newest = await sm.is_client_newest_host()
  return {"is_client_newest": is_newest}

@app.post("/server/did_upload")
async def did_upload(data: ServerIdentifier):
  sm = ServerManager(data.endpoint, data.server_name)
  uploaded = await sm.did_newest_host_upload()
  return {"did_upload": uploaded}

@app.post("/server/config")
async def get_server_config(data: ServerIdentifier):
  sm = ServerManager(data.endpoint, data.server_name)
  config = await sm.get_server_config()
  return config

@app.get("/servers")
async def list_servers(endpoint: str, server_name: str):
  sm = ServerManager(endpoint, server_name)
  servers = await sm.get_servers()
  return {"servers": servers}

# ---------- OPEN BROWSER ----------

def open_browser_later():
  asyncio.run(_wait_and_open())

async def _wait_and_open():
  import aiohttp
  while True:
    try:
      async with aiohttp.ClientSession() as session:
        async with session.get("http://127.0.0.1:8000/") as resp:
          if resp.status == 200:
            await logger.passLog(2, "Uvicorn finished starting")
            break
    except:
      pass
    await asyncio.sleep(0.2)
  await logger.passLog(2, "opening browser..")
  webbrowser.open("http://127.0.0.1:8000/")



if __name__ == "__main__":
  threading.Thread(target=open_browser_later, daemon=True).start()
  asyncio.run(logger.passLog(2, "Starting Uvicorn server..."))
  DownloadHandler().ensure_binaries_sync()
  uvicorn.run(app, host="127.0.0.1", port=8000)