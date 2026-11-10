import json
from pathlib import Path

import pytest

from vggt_slam.demo.live_studio import (LiveStudio, committed_events, complete_events,
                                         configuration, snapshot_run)


def test_committed_prefix_excludes_incomplete_records_and_assets(tmp_path):
    run=tmp_path/'source';run.mkdir()
    (run/'manifest.json').write_text(json.dumps({'run_id':'original','assets':{'point_cloud':'unfinished.pcd'}}))
    events=[{'event_type':'frame_selected','source_frame_id':'1'},
            {'event_type':'optimization_finished','payload':{'step':0}},
            {'event_type':'frame_selected','source_frame_id':'2'},
            {'event_type':'optimization_started','payload':{'step':1}}]
    (run/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events)+'{"event_type":')
    (run/'snapshots/0').mkdir(parents=True)
    (run/'snapshots/1').mkdir()
    (run/'submaps').mkdir();(run/'keyframes').mkdir()
    assert len(complete_events(run/'events.jsonl'))==4
    prefix=committed_events(run)
    assert prefix==events[:2]
    assert snapshot_run(run,tmp_path/'mirror',prefix)==0
    assert list((tmp_path/'mirror/snapshots').iterdir())==[tmp_path/'mirror/snapshots/0']
    assert json.loads((tmp_path/'mirror/manifest.json').read_text())['assets']=={'events':'events.jsonl'}
    assert complete_events(tmp_path/'mirror/events.jsonl')==events[:2]
    # Original writer's bytes, identity and unfinished assets are preserved.
    assert (run/'events.jsonl').read_text().endswith('{"event_type":')
    assert json.loads((run/'manifest.json').read_text())['assets']['point_cloud']=='unfinished.pcd'
    with pytest.raises(ValueError):snapshot_run(run,tmp_path/'bad',events)


def test_upload_preserves_files_and_refuses_concurrent_job(tmp_path):
    studio=LiveStudio(jobs_root=tmp_path)
    first=studio.reserve('../../original.mp4',configuration({}))
    assert first.is_relative_to(tmp_path)
    assert studio.job['filename']=='original.mp4'
    first.write_bytes(b'original bytes')
    with pytest.raises(RuntimeError):studio.reserve('second.mp4',configuration({}))
    studio.update(state='completed')
    second=studio.reserve('original.mp4',configuration({}))
    assert first!=second and first.read_bytes()==b'original bytes'
    studio.update(state='failed')
    with pytest.raises(ValueError):studio.reserve('not-video.py',configuration({}))
    assert first.read_bytes()==b'original bytes'


@pytest.mark.parametrize('query',[{'max_frames':['-1']},{'min_disparity':['nan']},
                                  {'submap_size':['1']},{'max_loops':['10']}])
def test_invalid_compute_settings(query):
    with pytest.raises(ValueError):configuration(query)


def test_cancel_stops_only_owned_children_and_keeps_uploaded_evidence(tmp_path):
    class Child:
        def __init__(self):self.running=True;self.signals=[]
        def poll(self):return None if self.running else 0
        def send_signal(self,value):self.signals.append(value)
        def wait(self,timeout):self.running=False
    owned,unrelated=Child(),Child()
    studio=LiveStudio(jobs_root=tmp_path)
    path=studio.reserve('fixture.mp4',configuration({}));path.write_bytes(b'keep')
    studio.children=[owned]
    studio.stop()
    assert owned.signals and not owned.running
    assert unrelated.running and unrelated.signals==[]
    assert studio.job['state']=='cancelled' and path.read_bytes()==b'keep'
    assert json.loads((path.parent/'job.json').read_text())['state']=='cancelled'


def test_cancelled_upload_cannot_be_replaced_until_receiver_finishes(tmp_path):
    studio=LiveStudio(jobs_root=tmp_path)
    studio.reserve('first.mp4',configuration({}))
    studio.upload_active=True
    studio.stop()
    with pytest.raises(RuntimeError):studio.reserve('new.mp4',configuration({}))
    studio.upload_active=False
    assert studio.reserve('new.mp4',configuration({})).exists() is False
