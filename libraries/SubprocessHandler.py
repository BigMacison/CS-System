import asyncio
from .AbstractProcessRunHandler import AbstractProcessRunHandler
import os
import subprocess
import re

class SubprocessHandler(AbstractProcessRunHandler):
  def __init__(self, command: list, env:dict=None):
    super().__init__(command, env)
    self.listeners = []

  def register_listener(self, callback):
    # Add function that gets called, everytime a new line in the output of the programm appears.
    self.listeners.append(callback)

  async def _read_stream(self, stream):
    while True:
      line = await stream.readline()
      if not line:
        break
      decoded = line.decode().rstrip()
      for listener in self.listeners:
        await listener(decoded)


  async def start(self):
    # start the program
    self.process = await asyncio.create_subprocess_exec(
      *self.command,
      stdout=asyncio.subprocess.PIPE,
      stderr=asyncio.subprocess.STDOUT,
      stdin=asyncio.subprocess.PIPE,
      env=self.environment
      )
    asyncio.create_task(self._read_stream(self.process.stdout))

  async def send_input(self, text: str):
    if self.process:
      self.process.stdin.write((text + '\n').encode())
      await self.process.stdin.drain()

  async def stop(self):
    if self.process:
      self.process.terminate()
      await self.process.wait()

  async def wait_until_done(self):
    # use this function in combination with await, to wait till the program is done.
    if self.process:
      await self.process.wait()

  @staticmethod
  def run_once(command: list[str], env: dict = None) -> str:
    environment = os.environ.copy()
    if env is not None:
      environment.update(env)

    result = subprocess.run(
      command,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      stdin=subprocess.PIPE,
      env=environment,
      text=True  # returns str instead of bytes
    )
    return result.stdout.strip()