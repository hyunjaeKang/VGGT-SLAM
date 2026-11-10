import json
import subprocess
from vggt_slam.demo.search_lifecycle import recover_search_status, search_worker_alive


def test_interrupted_job_recovers_and_preserves_original(tmp_path, monkeypatch):
    progress={'state':'running','worker_pid':123,'message':'frame 20/24'}
    path=tmp_path/'status.json';path.write_text(json.dumps(progress))
    monkeypatch.setattr('vggt_slam.demo.search_lifecycle.os.kill',lambda *_: (_ for _ in ()).throw(ProcessLookupError()))
    result=recover_search_status(path,progress)
    assert result['state']=='failed'
    assert json.loads((tmp_path/'interrupted_status.json').read_text())==progress
    assert recover_search_status(path,result)==result


def test_pid_reuse_is_not_active_search(monkeypatch):
    monkeypatch.setattr('vggt_slam.demo.search_lifecycle.os.kill',lambda *_: None)
    monkeypatch.setattr('vggt_slam.demo.search_lifecycle.subprocess.run',lambda *a,**k: subprocess.CompletedProcess(a,0,'unrelated command',''))
    assert not search_worker_alive({'worker_pid':123},'/tmp/job123')
    monkeypatch.setattr('vggt_slam.demo.search_lifecycle.subprocess.run',lambda *a,**k: subprocess.CompletedProcess(a,0,'python demo_search_cached.py --output /tmp/job123',''))
    assert search_worker_alive({'worker_pid':123},'/tmp/job123')
