# V5 RF-DETR 검색

V5(http://localhost:8107) → **검색 · Search** → **Search model: RF-DETR** → **전체 클래스 검출 ON** → Search scope `현재 RGB` → **Search**. 특정 종류만 원하면 전체 클래스 검출을 OFF로 바꾸고 Query `car`를 입력한다.

RF-DETR-Seg Nano(312×312 모델 입력), COCO 학습 클래스, CPU 추론을 사용한다. `car, person, truck, bus, bicycle` 등을 쉼표로 입력할 수 있다. `자동차`는 기존 검색어 변환으로 `car`가 된다. `printer`, `road` 등 미지원 클래스는 오류 안내하며 SAM3/YOLOE를 사용한다. 지원 여부는 RF-DETR 공식 COCO ID 목록으로 검사한다.

선택 범위: 현재 RGB / 전구간 표본 / 전구간 전수 / PE 후보 찾기. 전수는 저장된 고유 지도 프레임을 모두 검사한다. PE 후보는 별도 이미지·텍스트 모델로 일부 후보를 찾으므로 전수 검색이 아니다. CPU에서 전체 구간은 시간이 걸릴 수 있다.

RGB 마스크·박스, 유효 깊이 기반 3D 마스크·박스와 BEV 표시를 기존 검색 경로와 공유한다. 모델 자체가 3D 박스를 예측하는 것은 아니다. Saved object query에 RF-DETR와 검색 범위가 표시되며 Result frame 선택, Mask/Box 토글, Clear, 선택 삭제를 그대로 사용한다. 관측 수는 고유 객체 수가 아니다.

## 환경 재현

기존 `.venv`, `.venv-v4`, `.venv-open-set`은 변경하지 않는다.

```sh
.venv/bin/python -m venv .venv-rfdetr
.venv-rfdetr/bin/python -m pip install -r evidence/v5_rfdetr_20261109_01/requirements.txt
.venv-rfdetr/bin/python -c "from pathlib import Path; from rfdetr.assets.model_weights import download_pretrain_weights; p=Path('logs/demo_models/rfdetr/rf-detr-seg-nano.pt'); p.parent.mkdir(parents=True,exist_ok=True); download_pretrain_weights(str(p))"
```

가중치 준비는 명시적으로 실행한다. 일반 검색은 로컬 가중치를 사용하며 없으면 실패 안내한다. 모델/버전/가중치 SHA256/선택 클래스/임계값0.3/CPU를 캐시 identity에 포함한다. 같은 RGB의 여러 클래스는 한 추론을 공유한다. 기존 다른 모델 캐시는 그대로 보존한다.

공식 참고: [Segmentation API](https://rfdetr.roboflow.com/latest/learn/run/segmentation/), [RF-DETR 소스](https://github.com/roboflow/rf-detr). 공식 NVIDIA T4 벤치마크를 현재 Mac 속도로 해석하지 않는다.

- RF-DETR 실제 Chrome 최종 PASS: 모델선택/기능안내/새검색/backend=rfdetr/유효3D/저장 RF-DETR·현재RGB범위/결과선택/JS예외0. `evidence/v5_rfdetr_20261109_01/browser_checks.json`, `rfdetr_search.png`. 최초 검증은 SAM3초기값을가정한선택자 및 input값을innerText로검사해실패,현재선택허용·input.value검사로수정후통과(제품검색실패아님).


## 2026-11-09 · 고정 클래스 모델 전체 객체 및 Saved Objects 개선

RF-DETR/YOLO26/YOLO11 선택 시 `전체 클래스 검출` 기본ON,Query입력숨김/미사용. OFF면기존특정클래스Query검색. SAM3/YOLOE는기존텍스트검색유지. 전체클래스는현재RGB/전구간표본/전구간전수지원,텍스트PE후보는이모드에서제외한다. 모든종류를반드시찾는다는뜻이아니며해당모델의학습클래스에서임계값을넘긴검출을모두보여준다.

worker --all-classes는YOLO모델names/RF공식COCO목록을사용하고프레임당단한번추론한후검출된종류만마스크/깊이/3D로저장한다. 80종음성결과를매프레임쓰기않고검출없는프레임은빈관측하나로검사coverage보존. 클래스명은개별detection과관측에저장,RGB마스크/박스에종류명표시. 모델별/클래스별캐시분리,기존car검색은보존하며전체객체로소급변경하지않는다.

Saved Objects 폴더:모델필터/객체명검색/최신순목록/전체객체종수·2D수라벨/선택결과종류별RGB검출·유효3D표/Result frame(2D만있어도선택가능)/선택삭제/Clear. RGB검출은깊이부족으로3D없어도표시한다. 관측수는고유객체수가아니다.

실제동일KITTI표본4장:YOLO26=2종(car8,motorcycle1),2D9/3D7;YOLO11=3종(car10,motorcycle2,potted plant2),2D14/3D12;RF-DETR=4종(car8,motorcycle1,person1,truck2),2D12/3D10. evidence/v5_all_objects_20261109_01/results.json/모델별log. 단순표본으로정확도우열을주장하지않는다. 전체회귀192passed/27.92초(tests.log). 기존완료지도동일작업재열기로적용,원본/사용자검색삭제목록/이전결과보존.
