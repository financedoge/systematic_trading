"""Install the pinned official Windows restic binary after SHA-256 verification."""
import hashlib
import io
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.18.1"
SHA256 = "0c1a713440578cb400d2e76208feb24f1b339426b075a21f73b6b2132692515d"


def main():
    url = f"https://github.com/restic/restic/releases/download/v{VERSION}/restic_{VERSION}_windows_amd64.zip"
    with urllib.request.urlopen(url, timeout=90) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Official restic release checksum mismatch")
    target = ROOT / "var/dependencies/restic/restic.exe"
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        target.write_bytes(archive.read(f"restic_{VERSION}_windows_amd64.exe"))
    print(f"Installed verified restic {VERSION}: {target}")


if __name__ == "__main__":
    main()
