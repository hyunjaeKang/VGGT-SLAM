"""Readable saved-search summaries without changing persisted evidence."""
from collections import Counter
from vggt_slam.demo.search_policy import query_model_label, query_label


def saved_summary(query):
    if not query:
        return '저장 결과를 선택하면 모델·범위·종류별 검출 수가 표시됩니다. 기존 car 검색은 car만 포함합니다. 전체 객체는 새로 검색하세요.'
    search=query.get('search',{})
    detections=query.get('detections',[])
    counts=Counter(d.get('query',query.get('query','객체')) for d in detections)
    valid=Counter(d.get('query',query.get('query','객체')) for d in detections if d.get('valid'))
    scopes={'all':'전구간 전수','current':'현재 RGB','sampled':'전구간 표본','candidate':'PE 후보','live':'생성 중'}
    title='전체 클래스' if search.get('all_classes') else query.get('query','검색')
    lines=[f"**{query_model_label(query)} · {title}**",f"{scopes.get(search.get('mode'),'범위 미기록')} · 검사 {search.get('inspected_frames','?')}장 · 검출 {len(counts)}종",'프레임별 관측 수입니다. 같은 객체가 여러 번 포함될 수 있습니다.', '', '| 종류 | RGB 검출 | 유효 3D |','|---|---:|---:|']
    lines += [f'| {name} | {count} | {valid[name]} |' for name,count in counts.most_common()]
    if not counts:lines.append('| 미검출 | 0 | 0 |')
    return '\n\n'.join(lines[:3])+'\n\n'+'\n'.join(lines[3:])


def saved_labels(run, model='전체', text=''):
    needle=text.strip().casefold()
    items=[]
    for item in reversed(run.object_queries):
        if model!='전체' and query_model_label(item)!=model:continue
        names=' '.join(d.get('query','') for d in item.get('detections',[]))
        if needle and needle not in (item.get('query','')+' '+names).casefold():continue
        items.append(item)
    return {query_label(item):item['query_id'] for item in items}
