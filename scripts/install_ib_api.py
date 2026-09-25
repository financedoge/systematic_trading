"""Install the pinned official IB SDK; PyPI's 9.81 SDK lacks current FX support."""
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from urllib.request import urlopen
from zipfile import ZipFile

URL = "https://interactivebrokers.github.io/downloads/twsapi_macunix.1045.01.zip"
SHA256 = "56ea048911052e86d6621ab712957c790fce6d547bc2a55900136ae4f6835941"


def main():
    root = Path(__file__).resolve().parents[1] / "var" / "dependencies"
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "twsapi_macunix.1045.01.zip"
    if not archive.exists():
        with urlopen(URL, timeout=60) as response:
            archive.write_bytes(response.read())
    if sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError("Official SDK archive checksum mismatch; no code was installed.")
    destination = (root / "ibapi-10.45").resolve()
    with ZipFile(archive) as package:
        for name in package.namelist():
            if "/pythonclient/" not in name or name.endswith("/"):
                continue
            target = (destination / name.split("/pythonclient/", 1)[1]).resolve()
            if not target.is_relative_to(destination):
                raise ValueError("Unsafe SDK archive member.")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(package.read(name))
    subprocess.run([sys.executable, "-m", "pip", "install", str(destination)], check=True)
    print("Installed official IB API 10.45.1. Restart broker-connected services after validation.")


if __name__ == "__main__":
    main()
