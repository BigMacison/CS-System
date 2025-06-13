import os
import platform
import shutil
import stat
import tempfile
import zipfile
import tarfile
import urllib.request
import json
from .SubprocessHandler import SubprocessHandler
from .LogHelper import LogHelper


class DownloadHandler:
    BASE_DIR = os.path.join(os.getcwd(), "bin")
    HEADERS = {'User-Agent': 'Mozilla/5.0'}

    def __init__(self):
        self.system = platform.system().lower()  # 'windows' or 'linux'
        self.arch = "amd64"  # standard architecture as specified
        self.logger = LogHelper()

    def ensure_binaries(self):
        self.update_rclone()
        self.update_restic()

    def update_rclone(self):
        self.logger.passLog(2, "Checking rclone...")
        version = self._get_latest_github_tag("rclone", "rclone")
        target_dir = os.path.join(self.BASE_DIR, "rclone")
        binary_path = os.path.join(target_dir, "rclone.exe" if self.system == "windows" else "rclone")

        if self._is_up_to_date(binary_path, version):
            self.logger.passLog(2, "rclone is up to date.")
            return

        download_url = self._get_rclone_download_url(version)
        self._download_and_extract(download_url, binary_path, "rclone")

    def update_restic(self):
        self.logger.passLog(2, "Checking restic...")
        version = self._get_latest_github_tag("restic", "restic")
        target_dir = os.path.join(self.BASE_DIR, "restic")
        binary_path = os.path.join(target_dir, "restic.exe" if self.system == "windows" else "restic")

        if self._is_up_to_date(binary_path, version):
            self.logger.passLog(2, "restic is up to date.")
            return

        download_url = self._get_restic_download_url(version)
        self._download_binary(download_url, binary_path)

    def _get_latest_github_tag(self, org, repo) -> str:
        url = f"https://api.github.com/repos/{org}/{repo}/releases/latest"
        req = urllib.request.Request(url, headers=self.HEADERS)
        with urllib.request.urlopen(req) as response:
            data = json.load(response)
        return data["tag_name"].lstrip("v")

    def _is_up_to_date(self, binary_path: str, latest_version: str) -> bool:
        if not os.path.exists(binary_path):
            return False

        try:
            output = SubprocessHandler.run_once([binary_path, "version"])
        except Exception:
            return False

        return latest_version in output

    def _get_rclone_download_url(self, version: str) -> str:
        file_name = f"rclone-v{version}-{self.system}-{self.arch}.zip"
        return f"https://downloads.rclone.org/v{version}/{file_name}"

    def _get_restic_download_url(self, version: str) -> str:
        file_name = f"restic_{version}_{self.system}_{self.arch}.zip" if self.system == "windows" \
            else f"restic_{version}_{self.system}_{self.arch}.bz2"
        return f"https://github.com/restic/restic/releases/download/v{version}/{file_name}"

    def _download_and_extract(self, url: str, output_binary_path: str, binary_name: str):
        self.logger.passLog(2, f"Downloading from {url}")
        with tempfile.TemporaryDirectory() as tmpdir:
            local_zip = os.path.join(tmpdir, "archive.zip")
            urllib.request.urlretrieve(url, local_zip)

            with zipfile.ZipFile(local_zip, 'r') as zip_ref:
                for file in zip_ref.namelist():
                    if file.endswith(binary_name) or file.endswith(f"{binary_name}.exe"):
                        zip_ref.extract(file, tmpdir)
                        extracted_path = os.path.join(tmpdir, file)
                        os.makedirs(os.path.dirname(output_binary_path), exist_ok=True)
                        shutil.copy2(extracted_path, output_binary_path)
                        os.chmod(output_binary_path, os.stat(output_binary_path).st_mode | stat.S_IEXEC)
                        self.logger.passLog(2, f"{binary_name} updated.")
                        break

    def _download_binary(self, url: str, output_binary_path: str):
        self.logger.passLog(2, f"Downloading binary from {url}")
        os.makedirs(os.path.dirname(output_binary_path), exist_ok=True)

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            urllib.request.urlretrieve(url, tmp_file.name)

            if url.endswith(".bz2"):
                import bz2
                with bz2.BZ2File(tmp_file.name) as f_in:
                    with open(output_binary_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            elif url.endswith(".zip"):
                with zipfile.ZipFile(tmp_file.name, 'r') as zip_ref:
                    for file in zip_ref.namelist():
                        if "restic" in file and (file.endswith("exe") or not file.endswith("/")):
                            zip_ref.extract(file, os.path.dirname(output_binary_path))
                            shutil.move(os.path.join(os.path.dirname(output_binary_path), file), output_binary_path)

        os.chmod(output_binary_path, os.stat(output_binary_path).st_mode | stat.S_IEXEC)
        self.logger.passLog(2, "restic updated.")
