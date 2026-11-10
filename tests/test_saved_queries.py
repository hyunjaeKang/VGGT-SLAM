from types import SimpleNamespace
from vggt_slam.demo.saved_queries import saved_labels,saved_summary


def test_saved_models_species_and_counts():
    q={'query':'전체 객체','query_id':'query_123456','search':{'backend':'yolo26','mode':'all','all_classes':True,'inspected_frames':4,'class_counts':{'person':1,'car':1}},'detections':[{'query':'person','valid':False},{'query':'car','valid':True}]}
    run=SimpleNamespace(object_queries=[q])
    assert len(saved_labels(run,'YOLO26','person'))==1
    assert not saved_labels(run,'RF-DETR')
    summary=saved_summary(q)
    assert '| person | 1 | 0 |' in summary and '| car | 1 | 1 |' in summary
    assert '2종' in next(iter(saved_labels(run)))
