"""Recover interrupted search workers without deleting evidence or killing jobs."""
import os
import subprocess
from pathlib import Path


def search_worker_alive(progress, job):
    pid = progress.get('worker_pid')
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # Lack of permission is not evidence of termination.
    try:
        result = subprocess.run(['ps', '-p', str(pid), '-o', 'command='],
                                capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            return 'demo_search_cached.py' in result.stdout and Path(job).name in result.stdout
        if result.returncode == 1 and not result.stderr.strip():
            return False
    except (OSError, subprocess.TimeoutExpired):
        pass
    return True


def recover_search_status(path, progress):
    if progress.get('state') != 'running' or search_worker_alive(progress, Path(path).parent):
        return progress
    from vggt_slam.demo.status import write_json_atomic
    path = Path(path)
    backup = path.with_name('interrupted_status.json')
    if not backup.exists():
        write_json_atomic(backup, progress)
    recovered = dict(progress, state='failed', error_type='InterruptedWorker',
                     message='이전 검색 프로세스가 종료되었습니다. 결과와 로그는 보존했습니다. 다시 검색할 수 있습니다.')
    write_json_atomic(path, recovered)
    return recovered
