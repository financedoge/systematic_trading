"""Provision a pinned LEAN build into a new directory; validation is separate."""
import argparse
from hashlib import file_digest
import os
from pathlib import Path
import subprocess
import urllib.request
import zipfile

from systematic_trading.lean.contracts import sha256,write_json

ROOT=Path(__file__).resolve().parents[1]
COMMIT='f49bb9623a3e8782bf22bbd2cb51f691058cfdc3'
SDK='10.0.402'
SDK_SHA512='ae4fd528cb7e9f6af6aaf7de36715a69f761f183744f1bb3025d19f5a92447090ec561410e46266c1d10a63781ed6f3de771760bc76c876d87daabc367b898cd'


def install(root):
    root=root.resolve()
    if root.exists():raise FileExistsError('Installation requires a new dedicated directory: '+str(root))
    root.mkdir(parents=True)
    environment=dict(os.environ,DOTNET_CLI_TELEMETRY_OPTOUT='1',NUGET_PACKAGES=str(root/'nuget'))
    def run(args,cwd=root):
        subprocess.run(list(map(str,args)),cwd=cwd,env=environment,check=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
    archive=root/'dotnet-sdk.zip'
    urllib.request.urlretrieve(f'https://builds.dotnet.microsoft.com/dotnet/Sdk/{SDK}/dotnet-sdk-{SDK}-win-x64.zip',archive)
    with archive.open('rb') as stream:
        if file_digest(stream,'sha512').hexdigest()!=SDK_SHA512:raise ValueError('SDK archive checksum mismatch')
    with zipfile.ZipFile(archive) as z:z.extractall(root/'dotnet')
    # The official Windows Python install manager verifies its signed index and
    # distribution before installation; this is the last PSF 3.11 Windows build.
    run(['py','install','--target='+str(root/'python311'),'3.11.9','-y'])
    run([root/'python311/python.exe','-m','pip','install','--disable-pip-version-check','-r',ROOT/'deploy/lean/python311-requirements.txt'])
    source=root/'lean-18130'
    run(['git','clone','--filter=blob:none','--no-checkout','https://github.com/QuantConnect/Lean.git',source])
    run(['git','sparse-checkout','init','--no-cone'],source)
    run(['git','sparse-checkout','set','/*','!/Data/*','/Data/market-hours/','/Data/symbol-properties/',
         '!/Tests/','!/TestsCommon/','!/Algorithm.Python/'],source)
    run(['git','checkout',COMMIT],source)
    patch=ROOT/'deploy/lean/windows-python-shutdown.patch'
    run(['git','apply','--check',patch],source);run(['git','apply',patch],source)
    run([root/'dotnet/dotnet.exe','build','Launcher/QuantConnect.Lean.Launcher.csproj','-c','Release','-m:2',
         '-p:RunAnalyzers=false','-p:GenerateDocumentationFile=false','-p:RestoreSources=https://api.nuget.org/v3/index.json'],source)
    engine=source/'Launcher/bin/Release'
    files={str(p.resolve()):sha256(p) for folder in (engine,source/'Data',root/'python311',root/'dotnet')
        for p in sorted(folder.rglob('*')) if p.is_file()}
    manifest=root/'lean-runtime-manifest.json'
    write_json(manifest,dict(source_commit=COMMIT,source_tag='18130',dotnet_sdk=SDK,python='3.11.9',
        patches={'deploy/lean/windows-python-shutdown.patch':sha256(patch)},files=files))
    candidate=dict(accepted=False,engine_root=str(engine),data_root=str(source/'Data'),
        python_root=str(root/'python311'),dotnet_root=str(root/'dotnet'),manifest=str(manifest),manifest_sha256=sha256(manifest))
    write_json(root/'runtime-candidate.json',candidate)
    print('Prepared candidate:',root/'runtime-candidate.json')
    print('Run fixture and retained-strategy parity before selecting this runtime in config/native-runtime.json.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path);parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    if args.verify:
        from systematic_trading.lean.native_runner import runtime
        config,provenance=runtime(require_acceptance=False);print('Verified runtime files and source',provenance['source_commit'])
    elif args.root:install(args.root)
    else:parser.error('Use --root NEW_DIRECTORY or --verify')
