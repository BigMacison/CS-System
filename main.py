import uvicorn
import webbrowser
import asyncio
import threading
from typing import Dict, Optional
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from libraries.LogHelper import LogHelper
from libraries.DownloadHandler import DownloadHandler
from libraries.ResticManager import ResticManager
from libraries.SubprocessHandler import SubprocessHandler
from libraries.ConfigManager import ConfigManager
from libraries.ServerManager import ServerManager
from libraries.PlayitManager import PlayitManager

app = FastAPI()
logger = LogHelper()
config = ConfigManager()
sm = ServerManager(config.getEndpoint(), config.getServerName())

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

# ---------- WEBSITE ----------
# Serve static files (CSS, JS) from /static
#app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Serve the HTML page at /
@app.get("/", response_class=FileResponse)
async def index():
    return "frontend/index.html"

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
    output_str = await sm.read_total_output()
    await websocket.send_json({"console": output_str.splitlines()})
  except Exception:
    pass

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
  return ResticManager.getEndpointsFromConfig()

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
  await sm.set_endpoint(endpoint)
  await sm.set_server_name(server_name)
  return {"status": "updated"}

# ---------- SERVER ENDPOINTS ----------

@app.post("/server/create")
async def create_server(data: ServerCreateRequest):
  smt = ServerManager(data.endpoint, data.server_name)
  await smt.create_server(
    data.start_cmd_win, data.start_cmd_linux, data.stop_cmd, data.port, data.env
  )
  return {"status": "server_created"}

@app.post("/server/delete")
async def delete_server(data: ServerIdentifier):
  smt = ServerManager(data.endpoint, data.server_name)
  await smt.delete_server()
  return {"status": "server_deleted"}

@app.post("/server/start")
async def start_server():
  if await sm.did_newest_host_upload():
    await sm.start_server(forward_to_websockets)
    return {"status": "server_started"}
  else:
    return {"error": "server_not_uploaded"}

@app.post("/server/stop")
async def stop_server():
  await sm.stop_server(forward_to_websockets)
  return {"status": "server_stopped"}

@app.post("/server/read")
async def read_total_output():
  output_str = await sm.read_total_output()
  return output_str.splitlines()

@app.post("/server/newest_host")
async def get_newest_host():
  host = await sm.get_newest_host()
  return {"newest_host": host}

@app.post("/server/force_set_newest_host")
async def force_set_newest_host():
  await sm.forceset_newest_host_status()
  return {"status": "forced_set"}

@app.post("/server/is_newest")
async def is_client_newest():
  is_newest = await sm.is_client_newest_host()
  return {"is_client_newest": is_newest}

@app.post("/server/did_upload")
async def did_upload():
  uploaded = await sm.did_newest_host_upload()
  return {"did_upload": uploaded}

@app.post("/server/config")
async def get_server_config():
  config = await sm.get_server_config()
  return config

@app.get("/servers")
async def list_servers(endpoint: str):
  smt = ServerManager(endpoint, "")
  servers = await smt.get_servers()
  return servers

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
  DownloadHandler().ensure_binaries_sync()
  threading.Thread(target=open_browser_later, daemon=True).start()
  asyncio.run(logger.passLog(2, "Starting Uvicorn server..."))
  uvicorn.run(app, host="0.0.0.0", port=8000)
  asyncio.run(PlayitManager().run_playit())