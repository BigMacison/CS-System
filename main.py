import uvicorn
import webbrowser
import asyncio
import threading
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from libraries.LogHelper import LogHelper
from libraries.DownloadHandler import DownloadHandler

app = FastAPI()
logger = LogHelper()
DownloadHandler().ensure_binaries()

@app.get("/")
async def index():
  return {"message": "Hello World"} 

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
  uvicorn.run(app, host="127.0.0.1", port=8000)