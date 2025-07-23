import asyncio
import os
from libraries.DownloadHandler import DownloadHandler
from libraries.PlayitManager import PlayitManager

async def main():
  await DownloadHandler().ensure_binaries()
  await PlayitManager().run_playit()

if __name__ == '__main__':
    asyncio.run(main())