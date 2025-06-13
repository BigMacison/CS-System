from datetime import datetime
import os
import aiofiles
import asyncio

class LogHelper:

  def __init__(self):   
    self.levels = ["ERR", "WRN", "INF", "DBG"]  # More log levels can be added here
    os.makedirs("./logs", exist_ok=True)   # Creates directory if nonexistent

  async def passLog(self, level: int, message: str):
    if level >= len(self.levels) or level < 0:
      await self.passLog(3, "Index for log level out of bounds. Please report this!")  # Checks if log level exists (happens automatically)
      return

    # Writes output like this: "[ERR] [2025-06-04_09-29-09] # THIS IS JUST A TEST"
    log_entry = f"[{self.levels[level]}] [{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}] # {message}\n"

    async with aiofiles.open("./logs/log.log", "a") as f:
      await f.write(log_entry)