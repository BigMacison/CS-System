import threading
import subprocess
import os
from .AbstractProcessRunHandler import AbstractProcessRunHandler
import queue
import inspect
import asyncio

class SubprocessHandler(AbstractProcessRunHandler):
  def __init__(self, command: list, env: dict = None, cwd: str = os.getcwd()):
    super().__init__(command, env, cwd)
    self.listeners = []
    self.process = None
    self._output_thread = None
    self._running = False
    self._input_queue = queue.Queue()
    self.loop = asyncio.get_event_loop()

  def register_listener(self, callback):
    # Add function that gets called every time a new line appears.
    self.listeners.append(callback)

  def _read_output(self):
    # Blocking stdout reader loop running in a separate thread.
    with self.process.stdout:
      for line in iter(self.process.stdout.readline, b''):
        decoded = line.decode().rstrip()
        for listener in self.listeners:
          result = listener(decoded)
          if inspect.isawaitable(result):
            asyncio.run_coroutine_threadsafe(result, self.loop)

  def _write_input(self):
    # Blocking stdin writer loop running in a separate thread.
    while self._running:
      try:
        line = self._input_queue.get(timeout=0.1)
        if self.process and self.process.stdin:
          self.process.stdin.write((line + '\n').encode())
          self.process.stdin.flush()
      except queue.Empty:
        continue

  def start(self):
    # Start the subprocess and background I/O threads.
    if self.process:
      return

    environment = os.environ.copy()
    if self.environment:
      environment.update(self.environment)

    self.process = subprocess.Popen(
      self.command,
      cwd=self.cwd,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      stdin=subprocess.PIPE,
      env=environment
    )

    self._running = True
    self._output_thread = threading.Thread(target=self._read_output, daemon=True)
    self._output_thread.start()

    self._input_thread = threading.Thread(target=self._write_input, daemon=True)
    self._input_thread.start()

  async def send_input(self, text: str):
    # Send input to the subprocess.
    self._input_queue.put(text)

  async def stop(self):
    if self.process:
      self._running = False
      self.process.terminate()
      self.process.wait()
      self.process = None

  async def wait_until_done(self):
    if self.process:
      while self.process.poll() is None:
        await asyncio.sleep(0.1)
      self._running = False
      self.process = None
      
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
