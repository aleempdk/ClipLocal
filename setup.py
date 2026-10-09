"""First-run Windows setup using Python and Windows Package Manager."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parent

def install_tool(package):
    if not shutil.which('winget'):
        raise RuntimeError('Windows App Installer is missing. Install FFmpeg and Node.js from their official sites, then rerun setup.')
    print('Installing '+package+' with Windows Package Manager. Review installer prompts.',flush=True)
    subprocess.run(['winget','install','--id',package,'--exact','--source','winget'],check=True)

def setup(skip_gpu=False,check_only=False):
    os.chdir(ROOT)
    from hardware import configure_paths
    configure_paths()
    if check_only:
        print('Setup prerequisites:',dict(python=sys.version.split()[0],ffmpeg=bool(shutil.which('ffmpeg')),ffprobe=bool(shutil.which('ffprobe')),node=bool(shutil.which('node')),winget=bool(shutil.which('winget'))))
        return
    executable=ROOT/'.venv'/'Scripts'/'python.exe'
    if not executable.exists():venv.EnvBuilder(with_pip=True).create(ROOT/'.venv')
    subprocess.run([str(executable),'-m','pip','install','--timeout','120','-r',str(ROOT/'requirements.txt')],check=True)
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        install_tool('Gyan.FFmpeg');configure_paths()
    if not shutil.which('node'):
        install_tool('OpenJS.NodeJS.LTS')
        program_files=os.environ.get('ProgramFiles','C:/Program Files')
        os.environ['PATH']=str(Path(program_files)/'nodejs')+os.pathsep+os.environ.get('PATH','')
    if not skip_gpu and shutil.which('nvidia-smi'):
        smi=subprocess.run(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],capture_output=True)
        if smi.returncode==0:
            print('Installing local NVIDIA speech libraries (over 1 GB on first setup).',flush=True)
            gpu=subprocess.run([str(executable),'-m','pip','install','--timeout','120','--retries','5','-r',str(ROOT/'requirements-gpu.txt')])
            if gpu.returncode:print('GPU speech installation failed. CPU speech is available; rerun setup to retry.')
    subprocess.run([str(executable),str(ROOT/'hardware.py')],check=True)
    print('Setup complete. Open Start ClipLocal.cmd.',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--skip-gpu',action='store_true')
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    try:setup(args.skip_gpu,args.check_only)
    except (OSError,RuntimeError,subprocess.CalledProcessError) as error:
        print('Setup did not finish: '+str(error));sys.exit(1)
