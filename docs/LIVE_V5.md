# V5 — VGGT-SLAM 전용 영상 데모

사용자용 설명서: [쉬운 HTML](USER_GUIDE.html) / [Markdown](USER_GUIDE.md). V5는 V4의 기능을 모두 더 빠르게 실행하는 버전이 아니라, **지도 생성에 필요한 계산에 집중한 별도 버전**이다. 기존 V1~V4와 사용자 데이터·수정·검색 삭제 목록을 보존했다.

## 실행

```sh
.venv/bin/python demo.py live5 --port 8107 --viewer-port 8108
```

<http://localhost:8107>에서 영상을 고른 뒤 추론 해상도를 선택한다. 기본378, 루프1, 서브맵8, 키프레임 이동45, 최대 입력0(끝까지). 내부8108 뷰어는 supervisor가 관리한다. 설명서는 <http://localhost:8107/guide>.

독립 CLI로 소량 실험:

```sh
.venv/bin/python scripts/demo_slam_v5.py \
  --video logs/demo_inputs/kitti_closed_loop_508_1855_20261109/kitti_closed_loop_v2_selected_10fps.mp4 \
  --image_size 378 --max_frames 6 --submap_size 3 --min_disparity 0 --max_loops 1
```

전체 선택 이미지 시험은 max_frames0/submap8/min_disparity0/max_loops1. 새 run을 생성하며 기존 run을 덮어쓰지 않는다. 이 세션의 실제 추론 시험은 앞6프레임 범위이며 전체226장 폐루프 시험은 아직 수행하지 않았다.

## 기능과 최적화

- 깊이·색상 점군, 카메라 자세·궤적, 겹치는 서브맵 연결, 루프 검출과 그래프 보정, PCD/TUM 저장, 3D/RGB/BEV 표시를 유지한다.
- YOLO/SAM3/SegFormer/PE 등 의미 모델 worker를 실행하지 않는다. 지도 생성 중 자동 객체 검색·도로·하늘 분할은 하지 않는다. 생성 완료 후 선택 검색과 객체 마스크·박스 표시는 지원한다. 따라서 BEV ROAD와 마스크 버튼도 숨긴다. 하늘은 남을 수 있다.
- V5에서만 실제 모델 입력 너비224/322/378/518을 선택한다. 높이도14배수로 맞추며 기존 crop·패딩·픽셀 중심 변환을 기록한다. 해상도를 줄이기 위해 업로드 원본을 변경하지 않는다.
- 루프1이면 기존 DINO/SALAD 기반 장소 검색과 VGGT 검증을 유지한다. 루프0이면 장소 검색 모델 자체를 로딩하지 않고 embedding 계산도 생략한다. 루프0을 full loop SLAM으로 표기하지 않는다.
- VGGT 체크포인트는 설치된 로컬 파일을 mmap/weights_only/assign으로 로딩해 불필요한 복사를 줄인다. DINO Torch Hub는 설치된 로컬 저장소를 사용해 매 실행의 GitHub branch HTTP 조회를 피한다. 파일이 없으면 명확한 오류를 낸다. 새 설치를 자동 다운로드하지 않는다.
- CPU 스레드4/OpenCV1로 제한. V5 표시용 preview는 프레임당10000점, 기본 표시200000점, CPU 투영960×540 상한/antialias1.0으로 제한한다. 실제 PCD 저장은 이 표시 상한으로 잘라내지 않는다.
- V5 전용 controller/viewer/panel/HTML을 추가했다. 공용 Solver의 추가 인자와 main_realtime의 최적화 경로는 opt-in이며 V1~V4 기본518 및 로딩 경로는 유지한다.
- 기존 MP4 원본을 RGB 재생에 참조하고 불필요한 재인코딩을 피한다. 모델 입력은 회전 보정된 VideoFileCamera 경로를 유지한다.

## KITTI 영상

`logs/demo_inputs/kitti_closed_loop_508_1855_20261109/`:

| 파일 | 구성 | ffprobe 확인 |
|---|---|---|
| kitti_closed_loop_full_10fps.mp4 | 원본508~1855 전체 |1348프레임/134.8초/1408×376/10fps |
| kitti_closed_loop_v2_selected_10fps.mp4 | V2 selection.json의226장, 원래 선택 순서 |226프레임/22.6초/1408×376/10fps |

`source_manifest.json`은 원본 경로·프레임ID·영상SHA256·시간 가정을 기록한다. 10fps는 데모 재생 가정이며 원본 타임스탬프는 가져오지 않았다. 선택 영상은 원래 주행 시간을 압축한다. 원본 PNG와 V2 결과는 수정하지 않았다.

재생성(출력 폴더는 새 이름으로 지정):

```sh
.venv/bin/python scripts/demo_make_kitti_loop_video.py --output logs/demo_inputs/kitti_closed_loop_NEW
```

## 실제 측정과 한계

`evidence/v5_resolution_20261109_01/model_benchmark.json`: 같은 원본 KITTI4장, 같은 체크포인트, MPS 동기화, 각 너비3회(첫 회 제외한2회 중앙값). 다른 V4 의미 작업이 동시에 실행 중이었다.

| 너비 | 실제 H×W | 패치 토큰/프레임 | warm 모델 추론 중앙값 |
|---|---|---:|---:|
|518|140×518|370|1.979초|
|378|98×378|189|1.252초|
|322|84×322|138|1.559초|
|224|56×224|64|1.206초|

378은 이 소량 모델 비교에서 약1.58배 빨랐다. 322는378보다 느려 단조적 향상을 주장하지 않는다. 모든 깊이 출력은 유한·양수였으나 이는 GT 정확도 검증이 아니다. 낮은 해상도는 점군 밀도·작은 구조·루프 인식에 영향을 줄 수 있다.

실제 영상 업로드→추론→저장→최종 뷰어의 대응 시험:

| 증거 | 같은 선택 영상 앞6프레임 / submap3 / disparity0 / loops1 | 전체 처리시간 |
|---|---|---:|
| evidence/browser_live_v5_20261109_01 |378, 2서브맵,194480점 |21.05초|
| evidence/browser_live_v5_518_20261109_01 |518, 2서브맵 |22.38초|

둘 다 모델 입력 너비, 카메라·뷰어·의미 worker0·JS예외0을 실제 브라우저에서 확인했다. 두 번째 시험은 생성 중3뷰도 확인했다. 첫 번째는 빠른 전환 때문에 생성 중3뷰 검사를 포착하지 못해 완료 화면 검사만 PASS다. 새 루프는 이 짧은 구간에서0개다. 전체 처리시간 향상은 약6%로 모델만의 약1.6배와 구분한다. V4 PandaSet82/266초 결과는 입력이 달라 직접 배수 비교하지 않는다.

전체 회귀 **174 passed /11.46초**, Dash warning1. V5 전용10개와 기존 crop/recording/video controls 검증 포함. 현재6프레임 기능 시험으로 전체226/1348 프레임 품질·루프 성공·실시간30fps를 보증하지 않는다. 다음은 전체 폐루프 ON/OFF 및 해상도별 GT 궤적·연결 검증이다.

## 저장과 보존

작업: `logs/demo_v5_jobs/<id>/job.json`, `command.json`, `timings.json`, `report.json`, `inference.log`, `viewer.log`.

실제 지도: `logs/demo_runs/video_*/`의 manifest/config, submaps/depth/RGB/metadata, 그래프 snapshots, poses.txt, poses_points.pcd, video_summary.json. 표시 화면에서 겹치는 서브맵의 같은 원본 프레임이 다시 등장하는 것은 관측 인덱스 보존에 필요하다. 고유소스6/뷰어관측7을 구분한다.

추가실증: V5너비322/루프0/3프레임/1서브맵 run `video_20261109T182600_236195000`,60858점,약12.67초. DINO/SALAD를로딩하지않는경로로완료했다. `evidence/v5_resolution_20261109_01/correspondence_322.json`: 첫프레임19755점을깊이·K·저장투영행렬로재구성해PCD와비교,XYZ최대오차0/RGB불일치0/원본전처리RGB오차0. legacy오프라인검증기의execution_args/카메라행렬파일가정을비디오config/after스냅샷fallback으로확장하고실제검증했다. 최초CLI --run인자착오 및legacy계약오류 후 수정·재실행PASS; GT정확도판정은아니다.


## 루프 품질 우선 — 2026-11-09 후속 검증

V5에 `min_loop_seconds`(기본10)를 추가했다. source video PTS 기준으로 가까운 후보를 검색 전에 제외하며 V1~V4 기본 경로는0으로 유지한다. 선택226장 영상은시간압축되어이10초를원본KITTI10초로해석하면안된다. 유효query timestamp가없으면필터를무시하지않고실패한다.

**다음 생성의 권장 출발점:** UI의 ‘루프 품질 우선 설정’ → 518/서브맵16/이동45/루프1/시간간격10/전체입력. 이미선별된226장비교영상의모든이미지를쓰려면이동0으로바꾼다. 원본전체영상에서무조건이동0으로두는설정은권장하지않는다.

실제선택226장실험: run `video_20261109T193118_668535000`,518/submap16/disparity0/gap10,15단계,13186136점,CLI geometry84.32초. V2와같은재방문쌍1829→508/1855→541을2건검출·검증·제약추가했다. GT217개일치,ProperSim3사후적합ATE RMSE12.56179m(이전실패full영상113.89586m,과거V2선택PNG9.94856m). 입력선택/해상도/서브맵/시간필터가동시에바뀌었으므로시간필터하나의개선효과로주장하지않는다. 전체원본1348장을같은조건으로재검증한결과는아니다. 새226장영상은H264원본PNG와도다르다.

V5완료목록에새작업이즉시등록되지않던문제도보완했다. 기존실패지도와6프레임시험지도는보존했다. 새검증지도는 ‘KITTI selected · loop quality 518.mp4’로 V5에서열수있다. 증거 `evidence/v5_loop_recovery_20261109_01/`.


## Chase View와 RGB 재생 — 2026-11-09

3D상단 **Chase View · 뒤에서 추적** 버튼을추가했다.현재RGB카메라의뒤·위에서진행방향앞을보며재생·프레임이동을따라간다.오른쪽 **Chase 거리 배율**(0.5~8)로뒤로물러나는거리를조절한다. **자유3D탐색**은추적해제, **View Reset**은정확한RGB카메라시점으로복귀한다. 거리의기준은기록카메라간이동의중앙값이며절대미터단위가아니다.임의world-up을가정하지않는다.

V5는서버monotonic시계를기준으로RGB/지도/Chase를동기화한다.기존native video_clock요청은무시해지연디코더나다른탭이전체시계를되감을수없다.RGB는BEV/3D스냅샷다운로드와분리했다. 원본영상을디코딩중일때currentTime을반복지정하지않으며,영상오류/지연에는최신RGB JPEG를표시한다. 분할·검색모델이나새VGGT추론은실행하지않는다.

검증 `evidence/v5_chase_rgb_20261109_03/`: 정지프레임RGB seek/native픽셀변화,재생/끝에서재시작시native시간·픽셀변화,Chaseoffset/이동,오래된video_clock무시,Reset/자유모드,영상오류시JPEG프레임변화,JS예외0 모두PASS. 예:정지1.9초→7.6초의RGB해시변화,반복재생native0.14→1.66초와해시변화. canvasviewport1216×328.64확인. Chase수학6개PASS,전체184개PASS(18.04초);최종재검사결과는진행기록참조.


## 2026-11-09 · 생성 후 선택 검색 복원

후속 요청으로 V5에Search탭/현재RGB기본/전구간·표본·PE검색과객체마스크·박스표시를복원했다. 이전의‘검색 없음’설명은최초V5범위를기록한것이며현재는완료후on-demand검색가능하다. 지도생성중에는여전히상주semantic/ROAD/sky worker를실행하지않는다.

현재RGB car실제검색1장:20.62초,2Dmask9/유효3Dbox4. `evidence/v5_search_restore_20261109_01`:Search탭/실제SAM3/결과선택/왼쪽RGBannotatedJPEG/버튼표시/RGB·BEVmask/box토글/Clear/JS예외0 모두PASS. 색칠이나박스가필요한정지검색RGB는native영상대신해당관측이미지를표시한다.Chase상태를선택관측이동에서유지한다.

원본1348장을모두키프레임으로쓰는표준518/16/gap10실험도동시에수행하며결과는진행기록과 `evidence/v5_full1348_quality_20261109_01`을참조한다. 일반요건설명:[CLOSED_LOOP_GUIDE.md](CLOSED_LOOP_GUIDE.md).


## 원본 전체입력 추가실험 결과

| 조건 | 전체입력 | 실제지도키프레임 | 수락장거리루프 | 사후Sim3 ATE | CLI처리 |
|---|---:|---:|---:|---:|---:|
|518/16/시간간격10/이동0|1348|1348|4|59.995m(1276GT매칭)|526.42초|
|518/16/시간간격10/이동80|1348|224|1|11.558m(214GT매칭)|80.06초|

전체영상입력으로실제폐루프연결을확인했다. 모든사진을키프레임으로쓰는경로는여전히정합오차가커서권장하지않는다. 서로다른프레임표본에적합한오차지표이므로동일표본통제실험이나공식KITTI구간drift점수로해석하지않는다. ‘KITTI 폐루프 설정’버튼은이원본영상에검증한518/16/이동80/간격10을적용한다.80은원본1408픽셀너비의광류기준이며다른영상에보편적인임계값이아니다.

작업목록에 `KITTI 전체1348입력 · 키프레임224 · 루프검증.mp4`로등록했다. 전체1348키프레임실험도품질주의표시로보존했다. 증거 `evidence/v5_full1348_quality_20261109_01` 및 `evidence/v5_full_input_keyframes_20261109_01`.


## 2026-11-09 · V5 검색 모델 선택

V5 우측 `검색 · Search` 탭의 Query 위에 `Search model`을 추가했다. SAM3(기본)/YOLOE/YOLO26/YOLO11은 실제 선택 엔진으로 검색한다. RF-DETR은 엔진·가중치 미설치로 `준비 필요` 표시, 선택 후 검색 시 명확하게 안내하고 다른 모델로 대체하지 않는다. 모델을 바꾸면 지원 클래스·자유텍스트 여부·RGB/3D/BEV Mask와Box·Search scope 안내가 바뀐다. YOLO26/11은 COCO 학습클래스만, YOLOE/SAM3은 텍스트 대상 검색이다. Road 전체 표면 처리는 별도이며 일반 YOLO 고정클래스 검색은 road/printer를 지원하지 않는다.

검색 worker는 --backend(기본sam3)로 분기한다. SAM3 의존성은 해당 분기에서만 import하며 기존 V1~V4 호출은 기본 유지. YOLO 계열은 .venv-v4와 로컬 가중치, PersistentDetector CPU를 사용한다. 한 이미지의 여러 검색어는 추론을 공유하며 클래스별 마스크를 분리한다. 캐시 identity에 backend/가중치hash/classes/confidence/size를 넣어 모델 간 캐시 혼용을 막는다. 저장 결과는 실제 backend/model과 scope를 기록하며 기존 query_label에서 표시한다.

실제 같은 KITTI 현재프레임(playback34) car검색:YOLO26/11/YOLOE 모두 completed,각2D1/유효3D1. `evidence/v5_search_models_20261109_01/results.json` 및 모델별log. 전체회귀187passed/31.48초. V5 동일 완료작업을 다시 열어 메뉴 적용; 재추론 없음. RF-DETR 실제추론과 새 모델간 정확도·속도우열은 검증하지 않았다. graft build 갱신.


## 2026-11-09 · RF-DETR-Seg 실제 연결

V5 Search model의 RF-DETR 준비필요 상태를 실제 RF-DETR-Seg Nano 검색으로 대체했다. 별도 `.venv-rfdetr`/rfdetr1.12.0/Torch2.15.0 환경, 공식 COCO Seg Nano 가중치(134545398bytes,공식MD5통과),CPU/312입력/threshold0.3. 기존 SLAM/YOLO/SAM3 환경은 변경하지 않았다. 선택기능:현재/표본/전수/PE후보,RGB마스크·박스,깊이기반3D/BEV,저장모델명·scope,Clear/선택삭제. 공식COCO클래스ID로 car/person 등을구분하고 printer/road등미지원은모델로딩전안내. 다중검색어는프레임추론공유,모델버전/가중치hash/클래스/임계값을캐시identity에포함한다.

실제 KITTI playback34/source256 car검색:2D마스크2/유효3D1,worker기록6.657초(패키지설치·다운로드제외). 전체회귀188passed/25.27초. 증거 evidence/v5_rfdetr_20261109_01의requirements.txt/model_identity.json/search_status.json/inference.log. 사용법·설치재현 docs/RFDETR_SEARCH.md. 기존현재완료run을/api/open으로재열기,지도재추론없음. 전체구간정확도·고유3D객체수·다른모델대비우열·실시간성은미검증.


## 2026-11-09 · YOLO26 RGB 표시 누락 수정

사용자 실제 YOLO26 전수결과 search_1794270417840836000은224개고유프레임/2D639관측이있었다. 마지막playback236은검출0,235는검출1. (1) V5브라우저가재생중에는선택검색/RGB토글을무시하고원본MP4만표시하던조건을수정했다. 이제선택검색+RGB Mask또는Box ON이면재생중에도주석JPEG를표시한다. 이는지도키프레임갱신속도이며모든원본비디오프레임을새분할하지않는다. 두RGB토글OFF또는Clear이면원본영상표시로복귀한다. (2) 저장검색선택/전체관측복귀시검출없는마지막사진대신마스크있는마지막관측을연다. 전체관측의3D표시범위는유지한다. 현재프레임에검출이없는경우RGB는비어있으며다른사진의마스크를겹치지않는다.

전체회귀188passed/27.07초,JS문법검사PASS. 기존사용자전수검색·삭제목록·지도보존. V5같은완료작업재열기로새코드적용,지도재계산없음.


## 2026-11-09 · 고정 클래스 모델 전체 객체 및 Saved Objects 개선

RF-DETR/YOLO26/YOLO11 선택 시 `전체 클래스 검출` 기본ON,Query입력숨김/미사용. OFF면기존특정클래스Query검색. SAM3/YOLOE는기존텍스트검색유지. 전체클래스는현재RGB/전구간표본/전구간전수지원,텍스트PE후보는이모드에서제외한다. 모든종류를반드시찾는다는뜻이아니며해당모델의학습클래스에서임계값을넘긴검출을모두보여준다.

worker --all-classes는YOLO모델names/RF공식COCO목록을사용하고프레임당단한번추론한후검출된종류만마스크/깊이/3D로저장한다. 80종음성결과를매프레임쓰기않고검출없는프레임은빈관측하나로검사coverage보존. 클래스명은개별detection과관측에저장,RGB마스크/박스에종류명표시. 모델별/클래스별캐시분리,기존car검색은보존하며전체객체로소급변경하지않는다.

Saved Objects 폴더:모델필터/객체명검색/최신순목록/전체객체종수·2D수라벨/선택결과종류별RGB검출·유효3D표/Result frame(2D만있어도선택가능)/선택삭제/Clear. RGB검출은깊이부족으로3D없어도표시한다. 관측수는고유객체수가아니다.

실제동일KITTI표본4장:YOLO26=2종(car8,motorcycle1),2D9/3D7;YOLO11=3종(car10,motorcycle2,potted plant2),2D14/3D12;RF-DETR=4종(car8,motorcycle1,person1,truck2),2D12/3D10. evidence/v5_all_objects_20261109_01/results.json/모델별log. 단순표본으로정확도우열을주장하지않는다. 전체회귀192passed/27.92초(tests.log). 기존완료지도동일작업재열기로적용,원본/사용자검색삭제목록/이전결과보존.


## 2026-11-09 · RGB/3D/BEV 종류별 Mask 색상 및 Legend

object_colors.py의공통팔레트로같은객체종류는모델/프레임/뷰와무관하게같은색사용(car하늘색/person노랑/truck주황/motorcycle보라/plant초록,다른종류는이름기반결정적색). 개별인스턴스ID색이아닌클래스색이다. RGB는종류별반투명마스크/박스/이름표,3D는RoadLayer.world_colored의정확한깊이점+현재snapshot변환,BEV는동일점색의투영. RGB시점CPU래스터/재생GPU/자유3D의Viser점군모두의미점색을받는다. 모델자체의가짜3D를만들지않고유효깊이만표시한다.

세뷰에반투명Legend를추가하고선택검색에서검출된종류/색/관측수를표시한다. Clear/검색선택해제시Legend도제거된다. 3D/RGB/BEV Mask토글유지. GPU의미packet키에점색도포함하여색만바뀌어도캐시갱신. BEV의mask_colors는선택인자로기존V1~V4호출보존;레거시이름없는박스는이전빨강유지.

회귀194passed/25.40초(final_tests.log). RGB두클래스픽셀/Legend팔레트/BEV색혼합/GPU실제packet색/색변경캐시갱신검사추가. 실제3모델전체클래스표본검사는이전항목참조. 새코드로동일V5완료지도재열기,지도재생성없음.

- 최종Chrome PASS:고정모델전체클래스기본ON/YOLO26새검색24장5종/유효3D/저장모델·scope/세뷰Legend·종류별다른색/3D마스크점·BEV마스크/저장필터·종류표/완료후Search재활성/JS예외0. evidence/v5_all_objects_20261109_01/browser_checks.json,all_objects.png. 초기브라우저검증은Legend도착대기·이전scope·이전선택결과를고려하지않아실패했고,선택결과ID와실DOM도착을기다려최종PASS. selected_query_id메타데이터추가,저장필터변경은render_lock으로직렬화. V1~V4 RGB기존색상은opt-in class_colors=False로보존하고V5만종류색활성.


## 2026-11-09 · V5 3D Mask / 3D Box 독립 토글

3D상단에3D Box ON버튼추가,Mask/Box는별도상태·기본ON. 기존mask_3d가3D박스까지숨기던조건을box_3d로분리. 오른쪽지도탭체크박스/API액션/렌더signature/상태라벨동기화. CPU RGB시점래스터/GPU/자유Viser박스는같은projected_boxes목록으로독립제어. 기존모델검색·저장데이터보존,같은완료지도재열기로적용.


## 2026-11-10 · V5 상단 메뉴 숨기기/보이기

3D뷰상단메뉴를숨기고복원하는독립버튼추가. 메뉴전체(ViewReset/Chase/자유탐색/Mask·Box/재생·프레임/뷰크기등)를숨겨도왼쪽위의복원버튼은남는다. 오른쪽패널숨김과독립,RGB/BEV영역유지,localStorage(vggt-v5-top-menu-hidden)에선택상태보존. aria-controls/expanded 및 hidden스타일적용. HTML은요청시파일을읽으므로서버재시작/지도재생성없으며브라우저새로고침으로반영.


## 2026-11-10 · 영상 선택/지도 생성 영역 숨기기

8107컨트롤러헤더에영상설정숨기기/보이기버튼추가. 스크린샷의영상선택·생성/중지·이전지도·해상도·처리설정과상세상태행을함께접는다. 접힌상태에도헤더에간단한단계/경과시간과복원버튼유지. flex레이아웃으로줄어든영역만큼지도workspace높이확장,localStorage(vggt-v5-generation-hidden)상태보존. 3D뷰자체상단메뉴/오른쪽패널토글과독립적이며실행작업/선택파일/입력값은숨김으로변경하지않는다. HTML파일요청시읽기,서버재시작없음.
