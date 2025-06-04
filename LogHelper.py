from datetime import datetime
import os

class LogHelper:

  def __init__(self):   
    self.levels = ["ERR", "WRN", "INF", "DBG"]  # More log levels can be added here

  def passLog(self, level: int, message: str):
    if level >= len(self.levels) or level < 0:
      passLog(3, "Index for log level out of bounds. Please report this!")  # Checks if log level exists (happens automatically)
      return

    if not os.path.isdir("./logs"):   # Creates directory if nonexistent
      os.makedirs("./logs")

    with open("./logs/log.log", "a") as f:
      # Writes output like this: "[ERR] [2025-06-04_09-29-09] # THIS IS JUST A TEST"
      f.write("[" + self.levels[level] + "] [" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "] # " + message + "\n")    
