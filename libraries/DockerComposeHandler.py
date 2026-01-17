import asyncio
import docker
import subprocess
import os
from typing import Callable, List
from docker.errors import APIError, NotFound
import yaml

class DockerComposeHandler:
  def __init__(self, docker_compose_file_dir: str, container_name: str):
    self.cwd = docker_compose_file_dir
    self.listeners: List[Callable[[str], None]] = []
    self.client = docker.from_env()
    self.container_name = container_name
    self.compose_process = None
    self.attach_socket = None
    self.output: List[str] = []
    self.running = False
    self.stopped_intentionally = False

  async def register_listener(self, callback: Callable[[str], None]):
    """Add a function that gets called every time a new line appears."""
    self.listeners.append(callback)

  async def start(self):
    """Start the Docker Compose service and attach to the container."""
    # Start Docker Compose in detached mode
    try:
      self.compose_process = subprocess.Popen(
        ["docker", "compose", "up", "-d"],
        cwd=self.cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # Line buffering
      )
    except subprocess.CalledProcessError as e:
      raise RuntimeError(f"Failed to start Docker Compose: {e.stderr}")

    # Wait for the container to exist and be running
    await self._wait_for_container()

    # Attach to the container
    await self._attach_to_container()

    # Send world selection command to bypass prompt
    await asyncio.sleep(2)  # Wait for server to prompt
    await self.send_input("1")  # Select new world

  async def _attach_to_container(self):
    """Attach or reattach to the container."""
    try:
      container = self.client.containers.get(self.container_name)
      if container.status != "running":
        raise RuntimeError(f"Container {self.container_name} is not running (status: {container.status}).")
      if self.attach_socket:
        try:
          self.attach_socket._sock.close()
        except Exception:
          pass
        self.attach_socket = None
      self.attach_socket = container.attach_socket(params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": True})
      self.attach_socket._sock.settimeout(60)  # Increased timeout for inactivity
      self.running = True
      # Start reading output in the background
      asyncio.create_task(self._read_output())
    except docker.errors.NotFound:
      self.running = False
      raise RuntimeError(f"Container {self.container_name} not found.")

  async def stop(self):
    """Stop the Docker Compose service and clean up."""
    self.stopped_intentionally = True
    self.running = False
    if self.attach_socket:
      try:
        self.attach_socket._sock.close()
      except Exception as e:
        print(f"Error closing socket: {e}")
      self.attach_socket = None
    # Run docker compose down
    try:
      result = subprocess.run(
        ["docker", "compose", "down", "--timeout", "90"],
        cwd=self.cwd,
        check=True,
        capture_output=True,
        text=True
      )
      print(f"Docker Compose down output: {result.stdout}")
    except subprocess.CalledProcessError as e:
      print(f"Error running docker compose down: {e.stderr}")
    # Wait for the compose process to terminate
    if self.compose_process and self.compose_process.poll() is None:
      self.compose_process.terminate()
      try:
        await asyncio.wait_for(
          asyncio.get_event_loop().run_in_executor(None, self.compose_process.wait),
          timeout=5
        )
      except asyncio.TimeoutError:
        self.compose_process.kill()
        print("Forcefully killed compose process.")

  async def send_input(self, text: str):
    """Send input to the container's console."""
    if not self.running or not self.attach_socket:
      # Attempt to reattach if container is still running
      try:
        container = self.client.containers.get(self.container_name)
        if container.status == "running":
          print("Attachment lost, attempting to reattach...")
          await self._attach_to_container()
        else:
          raise RuntimeError(f"Container {self.container_name} is not running (status: {container.status}).")
      except docker.errors.NotFound:
        raise RuntimeError(f"Container {self.container_name} not found.")
    try:
      self.attach_socket._sock.send((text + "\n").encode("utf-8"))
    except Exception as e:
      self.running = False
      raise RuntimeError(f"Failed to send input: {e}")

  async def read_total_output(self):
    """Return all captured output from the container."""
    return "".join(self.output)

  async def wait_until_done(self):
    """Wait for the container to stop."""
    try:
      container = self.client.containers.get(self.container_name)
      while container.status == "running":
        await asyncio.sleep(0.1)
        container.reload()  # Refresh container status
    except docker.errors.NotFound:
      pass  # Container already removed
    # Ensure compose process is done
    if self.compose_process and self.compose_process.poll() is None:
      await asyncio.wait_for(
        asyncio.get_event_loop().run_in_executor(None, self.compose_process.wait),
        timeout=5
      )

  async def _wait_for_container(self, timeout: float = 30):
    """Wait until the container exists and is running."""
    start_time = asyncio.get_event_loop().time()
    while True:
      try:
        container = self.client.containers.get(self.container_name)
        if container.status == "running":
          return
        elif asyncio.get_event_loop().time() - start_time > timeout:
          raise TimeoutError(f"Container {self.container_name} exists but is not running after {timeout} seconds.")
        await asyncio.sleep(1)
      except docker.errors.NotFound:
        if asyncio.get_event_loop().time() - start_time > timeout:
          raise TimeoutError(f"Timed out waiting for container {self.container_name} to exist.")
        await asyncio.sleep(1)

  async def _read_output(self):
    """Read output from the container and call listeners."""
    while self.running and self.attach_socket:
      try:
        data = await asyncio.get_event_loop().run_in_executor(
          None, lambda: self.attach_socket._sock.recv(4096)
        )
        if not data:
          if self.stopped_intentionally:
            print("Container stopped intentionally, ending output reading.")
            break
          try:
            container = self.client.containers.get(self.container_name)
            if container.status == "running":
              print("No data from socket, but container still running, continuing...")
              continue
            else:
              print(f"Container stopped (status: {container.status}), ending output reading.")
              break
          except docker.errors.NotFound:
            print(f"Container {self.container_name} not found, ending output reading.")
            break
        lines = data.decode("utf-8", errors="ignore").splitlines()
        for line in lines:
          if line.strip():
            self.output.append(line + "\n")
            for callback in self.listeners:
              try:
                if asyncio.iscoroutinefunction(callback):
                  await callback(line.strip())
                else:
                  callback(line.strip())
              except Exception as e:
                print(f"Error in listener callback: {e}")
      except Exception as e:
        if self.stopped_intentionally:
          print("Container stopped intentionally, ending output reading.")
          break
        try:
          container = self.client.containers.get(self.container_name)
          if container.status == "running":
            print(f"Error reading output ({e}), attempting to reattach...")
            await self._attach_to_container()
            continue
          else:
            print(f"Container stopped (status: {container.status}), ending output reading.")
            break
        except docker.errors.NotFound:
          print(f"Container {self.container_name} not found, ending output reading.")
          break
      await asyncio.sleep(0.01)
    self.running = False

  async def check_images_exist(self) -> bool:
    """Check if all required images in the docker-compose.yaml file exist locally."""
    try:
      # Read the docker-compose.yaml file
      compose_file = os.path.join(self.cwd, "docker-compose.yaml")
      if not os.path.exists(compose_file):
        raise FileNotFoundError(f"docker-compose.yaml not found in {self.cwd}")

      with open(compose_file, 'r') as f:
        compose_data = yaml.safe_load(f)

      # Get all services and their images
      services = compose_data.get('services', {})
      for service_name, service_config in services.items():
        image = service_config.get('image')
        if image:
          # Check if the image exists locally
          try:
            self.client.images.get(image)
          except docker.errors.ImageNotFound:
            print(f"Image {image} for service {service_name} not found locally.")
            return False
        else:
          # If no image is specified, it likely uses a build context
          build = service_config.get('build')
          if build:
            # Check if the built image exists (using service name as a tag)
            image_name = f"{os.path.basename(self.cwd)}_{service_name}"
            try:
              self.client.images.get(image_name)
            except docker.errors.ImageNotFound:
              print(f"Built image {image_name} for service {service_name} not found locally.")
              return False
      return True
    except Exception as e:
      print(f"Error checking images: {e}")
      return False

  async def prepare_images(self):
    """Pull or build all images in the docker-compose.yaml, removing outdated images."""
    try:
      # Read the docker-compose.yaml file
      compose_file = os.path.join(self.cwd, "docker-compose.yaml")
      if not os.path.exists(compose_file):
        raise FileNotFoundError(f"docker-compose.yaml not found in {self.cwd}")

      with open(compose_file, 'r') as f:
        compose_data = yaml.safe_load(f)

      # Get all services
      services = compose_data.get('services', {})
      for service_name, service_config in services.items():
        image = service_config.get('image')
        if image:
          # Check for outdated images
          try:
            local_image = self.client.images.get(image)
            # Pull the latest image to check if it's up-to-date
            print(f"Checking for updates to image {image}...")
            latest_image = self.client.images.pull(image)
            if local_image.id != latest_image.id:
              print(f"Removing outdated image {image}...")
              self.client.images.remove(image, force=True)
          except docker.errors.ImageNotFound:
            pass  # Image not found locally, will pull it
          except docker.errors.APIError as e:
            print(f"Error checking/removing image {image}: {e}")

          # Pull the image
          print(f"Pulling image {image}...")
          try:
            subprocess.run(
              ["docker", "compose", "pull", service_name],
              cwd=self.cwd,
              check=True,
              capture_output=True,
              text=True
            )
            print(f"Successfully pulled image for service {service_name}.")
          except subprocess.CalledProcessError as e:
            print(f"Failed to pull image for service {service_name}: {e.stderr}")
            raise RuntimeError(f"Failed to pull image for service {service_name}: {e.stderr}")

        else:
          # Handle build context
          build = service_config.get('build')
          if build:
            image_name = f"{os.path.basename(self.cwd)}_{service_name}"
            # Remove old built image if it exists
            try:
              self.client.images.get(image_name)
              print(f"Removing outdated built image {image_name}...")
              self.client.images.remove(image_name, force=True)
            except docker.errors.ImageNotFound:
              pass  # No old image to remove

            # Build the image
            print(f"Building image for service {service_name}...")
            try:
              subprocess.run(
                ["docker", "compose", "build", service_name],
                cwd=self.cwd,
                check=True,
                capture_output=True,
                text=True
              )
              print(f"Successfully built image for service {service_name}.")
            except subprocess.CalledProcessError as e:
              print(f"Failed to build image for service {service_name}: {e.stderr}")
              raise RuntimeError(f"Failed to build image for service {service_name}: {e.stderr}")

    except Exception as e:
      print(f"Error preparing images: {e}")
      raise RuntimeError(f"Error preparing images: {e}")