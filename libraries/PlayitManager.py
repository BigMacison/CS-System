import os
import re
import asyncio
import json
import os
import pty
import subprocess
from .SubprocessHandler import SubprocessHandler
from .LogHelper import LogHelper

class PlayitManager:
  def __init__(self):
    self.process = None
    self._lock = asyncio.Lock()
    self.playit_binary_path = f"{os.getcwd()}/bin/playit/playit.exe" if os.name == "nt" else "./bin/playit/playit"
    self.playit_secret_path = f"{os.getcwd()}/configs/playit_secret.txt"
    self.playit_log_path = f"{os.getcwd()}/logs/playit.log"
    self.logger = LogHelper()
  
  async def startPlayit(self):
    await self.logger.passLog(2, f"Starting Playit-agent, check /logs/playit.log for details")
    async with self._lock:
      self.process = SubprocessHandler([self.playit_binary_path, "--secret_path", self.playit_secret_path, "--log_path", self.playit_log_path])
      async def forward(line):
        print(line)
      self.process.register_listener(forward)
      self.process.start()

  # def setupPlayit(self): 

  async def stopPlayit(self):
    await self.logger.passLog(2, f"Stopping Playit-agent")
    self.process.stop()

  async def resetPlayit(self):
    await self.logger.passLog(2, f"Resetting Playit-agent, restart playit to bring changes into effect")
    os.remove(self.playit_secret_path)

  async def run_playit(self):
    # Create a pseudo-terminal
    master_fd, slave_fd = pty.openpty()

    # Run the process using the PTY
    process = subprocess.Popen(
        [
            self.playit_binary_path,
            "--secret_path", self.playit_secret_path,
            "--log_path", self.playit_log_path
        ],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        start_new_session=True  # isolates it from terminal/ctrl signals
    )

    os.close(slave_fd)  # Close the slave side in the parent

    try:
        while True:
            await asyncio.sleep(0)  # Yield control to the event loop
            try:
                output = os.read(master_fd, 1024)
                if not output:
                    break
                print(output.decode(errors='ignore'), end='')
            except OSError:
                break
    finally:
        os.close(master_fd)
        process.wait()


## MASSIVE TODO: STOP PLAYIT, SETUP PLAYIT
## ADD LOCK TO START PLAYIT + CALLBACK FUNCTION FOR SETUP PLAYIT

  