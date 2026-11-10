"""Deterministic search scope and truthful outcome descriptions."""
import numpy as np


def model_query(query):
    aliases = {'자동차': 'car', '차': 'car', '승용차': 'car', '나무': 'tree', '트럭': 'truck'}
    return aliases.get(query.strip(), query.strip())


def candidate_order(sampled, scores, current=None, limit=5):
    candidates = ([current] if current is not None else []) + [sampled[i] for i in np.argsort(-np.asarray(scores), kind='stable')[:limit]]
    seen, result = set(), []
    for frame in candidates:
        key = str(frame['source_frame_id'])
        if key not in seen:
            result.append(frame)
            seen.add(key)
    return result


def outcome_text(mask_count, valid_boxes, attempted):
    if valid_boxes:
        return f'2D 검출 {mask_count}개 · 유효 3D 박스 {valid_boxes}개'
    if mask_count:
        return f'2D에서 {mask_count}개 검출 · 깊이점 부족/퇴화로 유효 3D 박스 없음'
    return f'검사한 {attempted}개 후보 프레임에서 검출되지 않음 · 영상 전체의 부재를 의미하지 않습니다'


def parse_queries(query, maximum=8):
    import re
    pieces = [part.strip() for part in re.split(r'[,;\n]+', query) if part.strip()]
    unique = {}
    for part in pieces:
        prompt = model_query(' '.join(part.split())).casefold()
        unique.setdefault(prompt, part)
    if not unique or len(unique) > maximum:
        raise ValueError(f'검색어는 1~{maximum}개를 쉼표로 구분해 입력하세요.')
    return [{'label': label, 'prompt': prompt} for prompt, label in unique.items()]


def scope_frames(frames, mode, limit=24, current=None):
    if mode == 'current':
        if current is None:
            raise ValueError('현재 RGB 프레임이 필요합니다.')
        return [current]
    unique = {str(f['source_frame_id']): f for f in frames}
    ordered = list(unique.values())
    if mode == 'all':
        return ordered
    if mode != 'sampled' or limit < 1:
        raise ValueError('invalid search scope')
    return [ordered[i] for i in np.linspace(0, len(ordered)-1, min(limit, len(ordered)), dtype=int)]


def query_model_label(item):
    """Name only recorded model identities; never guess from an opaque hash."""
    import re
    search = item.get('search') or {}
    identity = search.get('backend') or search.get('model') or item.get('backend') or item.get('model')
    if not identity:
        return '모델 미기록'
    value = str(identity).lower()
    for pattern, label in ((r'rf[-_ ]?detr|rf[-_ ]?deter', 'RF-DETR'),
                           (r'yoloe', 'YOLOE'), (r'yolo[-_ ]?26', 'YOLO26'),
                           (r'yolo[-_ ]?11', 'YOLO11'), (r'sam[-_ ]?3', 'SAM3'),
                           (r'segformer', 'SegFormer')):
        if re.search(pattern, value):
            return label
    return str(identity)


def query_label(item):
    valid = sum(bool(d.get('valid')) for d in item.get('detections', []))
    search = item.get('search') or {}
    names = {'all': '전체', 'sampled': '표본', 'current': '현재 RGB',
             'candidate': 'PE 후보', 'live': '생성 중'}
    scope = names.get(search.get('mode'), '범위 미기록')
    count = search.get('inspected_frames')
    if count is not None:
        scope += f' {count}장'
    title=item['query']
    if search.get('all_classes'):
        title=f"전체 객체 {len(search.get('class_counts',{}))}종 · 2D {len(item.get('detections',[]))}건"
    return f"{title} · {query_model_label(item)} · {scope} · 3D관측 {valid}건 · {item['query_id'][-6:]}"
