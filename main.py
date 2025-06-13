from libraries.DownloadHandler import DownloadHandler
import asyncio


def main():
  DownloadHandler().ensure_binaries()


if __name__ == '__main__':
    main()