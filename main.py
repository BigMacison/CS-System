from libraries.DownloadHandler import DownloadHandler
import asyncio


async def main():
  await DownloadHandler().ensure_binaries()


if __name__ == '__main__':
    asyncio.run(main())