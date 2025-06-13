import asyncio
from abc import ABC, abstractmethod
import os

class AbstractProcessRunHandler(ABC):
  def __init__(self, command: list, env:dict=None):
    self.command = command
    self.process = None
    self.environment = os.environ.copy()
    if env is not None:
      self.environment.update(env)

  @abstractmethod
  def register_listener(self, callback):
    pass

  @abstractmethod
  async def start(self):
    pass

  @abstractmethod
  async def send_input(self, text):
    pass

  @abstractmethod
  async def stop(self):
    pass

  @staticmethod
  @abstractmethod
  async def run_once(command):
    pass