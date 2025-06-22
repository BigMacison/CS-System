import uvicorn
import webbrowser
import asyncio
import threading
from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from libraries.LogHelper import LogHelper
from libraries.DownloadHandler import DownloadHandler
from libraries.ResticInterface import ResticInterface
from libraries.SubprocessHandler import SubprocessHandler

app = FastAPI()
logger = LogHelper()
websockets = {}


async def forward_to_websockets(json):
  for ws in list(websockets.values()):
    try:
      await ws.send_json(json)
    except Exception:
      pass


@app.get("/")
async def index():
  return {"message": "Hello World"}

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



@app.get("/test")
async def ping():
  sph = SubprocessHandler(["./ping", "google.com", "-i", "0.1"])
  sph.register_listener(forward_to_websockets)
  sph.start()
  return 1

@app.get("/endpoints")
async def endpoints():
  return ResticInterface.getEndpointsFromConfig()

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