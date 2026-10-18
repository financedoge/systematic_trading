"""Install pinned official Windows NATS binaries, verifying release checksums."""
from hashlib import sha256
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = json.loads((ROOT / 'config/native-runtime.json').read_text())
    destination = ROOT / 'var/dependencies/nats'
    destination.mkdir(parents=True, exist_ok=True)
    packages = [
        ('nats-io/nats-server', config['nats_version'], 'nats-server-v{v}-windows-amd64.zip', 'nats-server.exe', config['nats_archive_sha256']),
        ('nats-io/natscli', config['nats_cli_version'], 'nats-{v}-windows-amd64.zip', 'nats.exe', config['nats_cli_archive_sha256']),
    ]
    receipts = []
    for repo, version, template, executable, expected in packages:
        name = template.format(v=version)
        url = f'https://github.com/{repo}/releases/download/v{version}/{name}'
        archive = destination / name
        if not archive.exists():
            urllib.request.urlretrieve(url, archive)
        if sha256(archive.read_bytes()).hexdigest() != expected:
            raise ValueError('Official release archive checksum mismatch: ' + name)
        with zipfile.ZipFile(archive) as z:
            names = [n for n in z.namelist() if n.endswith('/' + executable)]
            if len(names) != 1:
                raise ValueError('Unexpected executable inventory in release')
            data = z.read(names[0])
            target = destination / executable
            if not target.exists() or target.read_bytes() != data:
                target.write_bytes(data)
        receipts.append(dict(url=url, archive_sha256=expected, executable=executable, executable_sha256=sha256(data).hexdigest()))
    (destination / 'provenance.json').write_text(json.dumps(receipts, indent=2), encoding='utf8')
    print('Verified native NATS server and CLI packages.')


if __name__ == '__main__':
    main()
