# 다음 세션 시작점 — VGGT-SLAM 데모

갱신: **2026-11-09**. 최신 V5·설명서 항목은 아래 및 [LIVE_V5.md](LIVE_V5.md)를 참조하세요. 사용자가 지정한 다음 계획서 이름은 `26.11.09.VGGT_SLAM.Plan.html`이며 조사 기준일은 실제 도구 날짜인 11-08이다. 이 문서가 오래된 계획의 “아직 구현하지 않음”·“S00부터 시작” 설명보다 최신이다. 과거 실험 결과는 해당 실험 시점의 기록으로 보존한다.

## 먼저 할 일

1. `AGENTS.md` → 이 문서 → `CURRENT_STATUS.md` → `DEMO_PROGRESS.md` 마지막 항목 → 루트의 `26.11.09.VGGT_SLAM.Plan.html`을 읽는다.
2. `git status --short`, 현재 V3 `job.json`과 `http://localhost:8103/api/live`를 **읽기만** 하여 실행 중 작업을 확인한다. 진행 중인 서버·추론·검색을 임의로 종료하거나 같은 포트로 재시작하지 않는다. 파일의 state가 종료되지 않았다고 실제 PID까지 살아 있다고 추정하지 않는다.
3. 구현할 심볼은 먼저 `graft ask "..." --source` 또는 `graft grep`, 변경 전에 `graft callers`로 확인한다. 큰 변경 후 `graft build`.
4. V4는 별도 구현되었고 V5 VGGT-SLAM 전용 버전도 추가되었다. 현재 V1~V5와 데이터를 보존한다. [LIVE_V4.md](LIVE_V4.md), [LIVE_V5.md](LIVE_V5.md) 및 최신 진행 항목부터 이어간다. 완료된 S00–S12 실험을 다시 처음부터 수행하지 않는다.

## Git와 보존

- 루트: `/Users/hyunjae.kang/2026_opensrc/VGGT_SLAM/vggt_slam_map`
- 브랜치: `vggt_slam_map`; origin: `git@github.com:hyunjaeKang/VGGT-SLAM.git`.
- 마지막 커밋: `9a0e7ba feat: add versioned Map Studio demos and smooth playback`.
- 이후 GPU 화질·툴바·V3·영상 회전 보정과 이번 문서 변경은 **미커밋**이다. 별도 commit/push 요청은 현재 없다. 단순 문서 인계를 위해 임의 커밋하지 않는다.
- `.DS_Store`, `TerraScene/`는 별도 사용자 변경이다. 수정·삭제·커밋 대상에 섞지 않는다. `graft/`는 로컬 캐시이며 생성 과정에서 TerraScene도 색인할 수 있지만 그 소스는 변경하지 않는다.
- `logs/`, 큰 모델/PCD/미디어, 증거 JSON은 대부분 git ignore 대상이다. 존재하는 로컬 증거가 원격에 자동 저장됐다고 말하지 않는다. 루트 `evidence/`는 현재 untracked 부분도 있으므로 필요한 코드/문서와 대용량 PNG·JSON을 구분해 다음 commit 때 검토한다.
- KITTI `evidence/deleted_queries.json`을 보존한다. 과거 car 결과를 사용자가 목록에서 지웠으므로 “쿼리 복구” 명목으로 되살리지 않는다. 원시 검색 증거는 별도로 남아 있다.

## 버전과 서버

| 주소 | 역할 | 주의 |
|---|---|---|
| 8100 | 버전 선택 | 서버를 시작해주는 서비스가 아니라 링크 선택 화면 |
| 8101 | Classic V1 | 기존 표시 소스 보존 |
| 8102 | Smooth V2 | 기존 run 재생, 원본 RGB+보간 카메라+GPU 점군 |
| 8103 | Live V3 | 디스크 파일 업로드·실제 VGGT/ROAD 생성·완료 후 검색 |
| 8104 | V3 작업 뷰 | V3 supervisor 소유; 별도로 실행/종료하지 않음 |
| 8097 | 이전 영상 데모 | 존재하면 보존; 재사용 전 확인 |

서비스가 없고 포트가 비어 있을 때만 각각 별도 터미널에서 실행:

```bash
.venv/bin/python demo.py versions --port 8100
.venv/bin/python demo.py view --run logs/demo_runs/s03_kitti_loop_on_20261031_01 --port 8101 --version classic
.venv/bin/python demo.py view --run logs/demo_runs/s03_kitti_loop_on_20261031_01 --port 8102 --version smooth --source-fps 10
.venv/bin/python demo.py live --port 8103 --viewer-port 8104
```

정적 HTML은 요청마다 읽으므로 UI 수정은 새로고침으로 반영된다. Python worker 변경은 새 프로세스부터 반영된다. 문서 갱신을 위해 실행 중 작업을 재시작하지 않는다. 이전 tool session ID는 다음 세션의 안정적인 관리 수단이 아니므로 실제 포트/PID/로그를 확인한다.

## 지금 진행 중인 사용자 작업 — 스냅샷, 완료 아님

2026-11-08 약20:12 UTC 조회 당시 사용자가 V3에서 새 90초 `clip.mp4` 전체 처리를 시작했다.

- job: `logs/demo_v3_jobs/live_20261108T115826_4ffce9d7/`
- 실제 run: `logs/demo_runs/video_20261108T195829_755817000/`
- 설정: submap8 / max_frames0(전체) / min_disparity10 / max_loops1.
- 당시 `state=inference`, 809 decoded / 713 고유 지도 프레임 / 89 최적화 단계 / ROAD73 검사. **숫자는 계속 바뀐다.** 마지막 정확한 조회값은 `research/handoff_snapshot_20261108.json`과 실제 job.json을 읽는다.
- 과거 11-06 유튜브 실험은 disparity45, source30부터 처리했다. 이번 사용자 실행은 disparity10이며 시작 trim을 지정하지 않았다. 같은 영상이어도 조건과 결과가 다르므로 과거 수치를 재사용하지 않는다.
- 다음 세션 첫 작업은 완료/실패·저장·메모리와 ROAD 잔여량 확인이다. 완료 전에 PASS/처리시간을 확정하지 않는다.

## 환경

- `.venv`: Python3.11, Torch2.3.1, 실제 SLAM은 Apple M2 Max의 MPS. 11-08 샌드박스 밖 `demo.py doctor`: mps=true/cuda=false. 샌드박스 안에서는 mps=false가 나와 하드웨어 부재로 오인할 수 있다.
- `.venv-open-set`: Python3.11 계열, `include-system-site-packages=true`로 로컬 `meta_sam3` 환경을 재사용한다. 기본 .venv의 SAM3 import가 false여도 별도 환경 검색은 동작한다. 독립 배포 환경이 아니다. SAM3는 현재 CPU로 실행한다. 공식 최신 SAM3의 Python/CUDA 요구와 이 로컬 수정 환경을 혼동하지 않는다.
- `.venv-eval`: evo 평가 및 일부 데이터 준비 도구. ffmpeg/ffprobe는 `/opt/homebrew/bin/`.
- VGGT: `~/.cache/torch/hub/checkpoints/model.pt`, sky: `logs/demo_models/skyseg.onnx`. 새 모델·pip 업그레이드·CUDA 설치는 이번 조사에서 하지 않았다. 기존 환경을 직접 업그레이드하지 않는다.

## 핵심 실행·코드 경로

| 대상 | 파일·심볼 | 연결 |
|---|---|---|
| 실행 명령 | `demo.py:main` | classic/smooth/live/versions |
| V3 supervisor | `vggt_slam/demo/live_studio.py:LiveStudio` | 업로드·고유run·소유 worker·ROAD·최종 view |
| 파일 선택 화면 | `vggt_slam/demo/web/studio_live.html` | 실제 choose button→file.click; 처리 중 선택 허용, 새 생성 잠금 |
| 실제 추론 | `main_realtime.py:run_camera_pipeline` | video_file→VGGT→기록→최적화 |
| 영상 방향 | `vggt_slam/cameras.py:VideoFileCamera` | Display Matrix를 추론 전에90/180/270도 보정, 중복 회전 방지 |
| 쓰기 계약 | `recording.py:Recorder`, `graph_recording.py` | 완성된 optimization_finished까지 공개 |
| 표시 | `viewer_smooth.py:serve` | 선택적 live_control, 생성 중 Search 잠금·최신 프레임 |
| V2 렌더링 | `gpu_scene.py`, `web/gpu_renderer.js`, `smooth_runtime.py` | immutable GPU packet/LOD/full K/Slerp/native RGB |
| HTTP | `smooth_panel.py:SmoothPanel` | frame/smooth/행동/이미지/MP4 range/GPU chunk |
| 검색 | `scripts/demo_search_cached.py:main` | all/current/sampled/candidate, SAM3, 선택적 부분 결과 |
| 도로 | `road.py:RoadLayer` | mask+depth→local support→최신 H→3D/BEV |
| 하늘 | `scripts/demo_prepare_sky.py` | 원본 점군을 바꾸지 않는 표시 필터 |
| 문서 현황 | `CURRENT_STATUS.md`, `DEMO_PROGRESS.md` | 최신 판정과 누적 사건 기록 |

정확한 line span은 코드 변경으로 이동하므로 다음 세션의 graft 결과로 다시 확인한다. Run 드롭다운은 입력 JSON 하나가 아니라 **선택 run의 부모 아래 manifest.json을 가진 폴더들**로 만들어지며 뷰어 시작 시 수집한다. 새 run 발견은 일반 뷰어 재시작 또는 V3 supervisor의 전환 경로를 사용한다.

## 꼭 기억할 수정

- V2 반복 재생: generation으로 과거 clock/ended 이벤트 거부, 끝에서 재생 시0 복귀, 실제 native RGB seek 동기화.
- V2 재생 화질: 노드당1000점 제한 제거, immutable 고밀도 GPU buffers와 draw-count LOD, full intrinsic 투영. 600k map points와 BEV 계산 샘플은 별개다.
- 툴바 깜빡임: mode/status 한 writer, 동일 textContent/aria 값의 불필요한 재할당 금지, 고정 너비/불투명 배경.
- 검색: 전구간은 저장된 고유 키프레임 전체이며 원본 모든 영상 프레임은 아니다. 관측 수는 고유 차량 수가 아니다. Result frame0건 제거·선택 RGB 동기화·선택 쿼리 삭제·Clear mask/box 적용.
- 11-08 MOV 반전: `duke_status.mov` display rotation=-180, OpenCV META180/AUTO0. 원본을 변경하지 않고 **추론 입력 자체를 정상 방향으로 보정**했다. 이미 반전 입력으로 만든 전체 지도는 새 생성이 필요하다. CSS만 뒤집지 않는다.
- 자유 overview: 고정 world up 대신 기록 카메라의 up/forward 기준. V1 표시는 그대로 둔다.
- 파일 선택: 처리 중 disabled 입력과 활성처럼 보이는 label이 원인. 실제 mouse click→fileChooserOpened 테스트로 보완했다. 기존 DOM 강제 파일 지정은 이 문제를 검출하지 못했다.

## 데이터와 증거

- 유튜브90초: `logs/demo_inputs/youtube_2t1i5LYoZXo_90s_20261106/clip.mp4` (약43MiB,1280×720/30fps).
- PandaSet33 fixture: `logs/demo_fixtures/pandaset33_1fps_20261105/clip.mp4`.
- 사용자 MOV 보존본: `logs/demo_v3_jobs/live_20261108T101000_7836a2fd/input.mov`.
- KITTI 루프: `s03_kitti_loop_on_20261031_01`, 2개 실제 loop. TUM: `s10_tum_xyz33_20261105_01`,33매 fitted Sim(3) ATE0.023689819m.
- V2 GPU/툴바 증거는 해당 KITTI run의 `evidence/browser_gpu_quality_live_20261108_01/`, `browser_toolbar_stability_20261108_01/`.
- V3 생성/검색/복원: 루트 `evidence/browser_live_v3_20261108_01/`.
- MOV 보정 재추론: `video_20261108T184700_282397000`, 앞6프레임만 검증,233500점/2서브맵/약94.07초. `evidence/browser_live_v3_rotation_20261108_01/`.
- 실제 chooser/방향: `evidence/v3_picker_orientation_20261108_01/`.
- 11-08 첫 개발 job의 map7/steps3/road0은 당시 표시 카운트 버그 기록이다. 실제6고유프레임/2서브맵/ROAD6이며 job.json 숫자만 믿지 말고 이벤트/결과를 대조한다.

## 검증과 다음 작업

최신 기존 코드 검증: **149 passed/30.25초**, Dash deprecation warning1. 이번 세션은 문서·조사만 변경하므로 장시간 사용자 추론과 경합하는 전체 추론/테스트를 반복하지 않았다. 문서 링크·HTML·스크립트·브라우저 검증은 별도 수행한다.

V4 시작 순서: R0(단계별 latency·현재 run 정리) → R1(상주 semantic worker+새 완료 프레임만) → R2(고정 클래스 경량 검출/YOLOE benchmark) → R3(2D 추적·local anchor·3D 승격) → R4(ROAD/sky 분리·UI/증거) → R5(30/90초·루프·부재·동적 객체 평가). 엄격한 실시간 요구가 로컬 Mac 목표를 넘으면 별도 CUDA worker 또는 streaming geometry adapter를 비교한다. **현재 사용자 요청은 계획 정리까지이며 V4 구현·모델 설치는 아직 시작하지 않았다.**

복사 가능한 재개 요청:

```text
AGENTS.md, docs/SESSION_HANDOFF.md, docs/CURRENT_STATUS.md,
26.11.09.VGGT_SLAM.Plan.html과 docs/DEMO_PROGRESS.md의 최신 항목을 읽어줘.
먼저 실행 중인 V3 작업의 상태·로그·완료 증거를 읽고 기존 작업을 보존해줘.
이후 계획의 R0부터 실제 측정과 소량 구현을 순서대로 진행해줘.
V1/V2/V3, 사용자 수정·삭제 목록·원본·결과는 유지하고 V4는 별도 경로로 만들어줘.
연구 자료의 논문 성능을 이 Mac의 측정값으로 쓰지 말고 각 단계 증거를 기록해줘.
```

최종 문서 조회 스냅샷: 2026-11-08T20:31:32.781252+00:00 / `live_20261108T115826_4ffce9d7` / state=`inference` / decoded=1938 / 고유지도=1497 / 단계=187 / ROAD검사=172. 실행 중 수치는 최종 결과가 아니며 다음 세션에 다시 읽는다.


## 2026-11-09 Live V4 구현

계획 기반 독립 V4를 추가했다. 실행: `.venv/bin/python demo.py live4 --port 8105 --viewer-port 8106`. 상주 객체 검출·ByteTrack·도로/하늘 분할·정확한 깊이 프레임 결합·생성 중 검색·증분 지도 뷰어를 제공한다. 상세 구현, 증거 및 미달성 목표: [LIVE_V4.md](LIVE_V4.md). 기존 사용자 수정과 run은 보존했다. R5 장시간/GT 및 R6 조건부 엔진 전환은 미완료다.


## 2026-11-09 V5 및 쉬운 설명서

- 설명서: [USER_GUIDE.html](USER_GUIDE.html) / [USER_GUIDE.md](USER_GUIDE.md) / [USER_GUIDE.pdf](USER_GUIDE.pdf), 실행 중 http://localhost:8107/guide. eli5 스킬 적용, 다섯 버전 목적·실행·사용·테스트영상·속도/화질 정리.
- V5: `.venv/bin/python demo.py live5 --port 8107 --viewer-port 8108`. 별도 jobs_root logs/demo_v5_jobs. 기본너비378/루프1/서브맵8/이동45/입력0. SEM/ROAD/sky worker없음. 기술/조건/증거는 LIVE_V5 참조.
- KITTI 전체1348장134.8초와 V2선택226장22.6초 MP4 생성: logs/demo_inputs/kitti_closed_loop_508_1855_20261109/. 10fps 가정, 원본timestamp미사용, 선택영상은 시간압축. 원본·V2결과 보존.
- 실제같은6프레임/루프1/서브맵3:378=21.05초,518=22.38초. 378run video_20261109T173559_890644000,194480점,2서브맵. 두 브라우저검사PASS;두번째 생성중3뷰도확인. 전체폐루프는 아직시험안함.
- 전체회귀174 passed/11.46초. V5 해상도/픽셀변환/518upstream동등성/루프OFF모델미로딩 등10개 포함.
- 다음: 전체226장 또는1348장 루프ON/OFF·해상도별 궤적/연결 GT평가. V4 지연목표와 최신 E2E 미완료를 완료로 바꾸지 않는다.
- 세션초 read-only조회: V3 사용자90초 작업 completed/2196고유프레임/ROAD2196. V4새 사용자job live_20261109T064641_2c2d4557은 당시 semantic/지도485/도로330으로 진행중. 변경·중지하지 않았다. 최신실행상태는다시읽는다.
- 버전선택8100은 V5/설명서 링크 반영을 위해 해당 서버만 재시작했다. V3/V4에는 종료 신호를 보내지 않았다.


### 2026-11-09 후속 · 루프 품질 복구

V5에min_loop_seconds기본10초(PTS기준검색전제외),품질설정버튼518/16/45/gap10추가. 선택226장통제시이동0. 새run video_20261109T193118_668535000:루프2개(과거V2동일쌍),GT217매칭ATE12.56m,CLI84.32초. 현재V5새품질job live_20261109T113118_loop_quality 등록·열기,이전실패1348장/6프레임결과보존. V5런타임history등록버그수정. 실패전체378run의ATE113.90m와비교하되조건동시변경·H264입력이므로원인단독효과를주장하지않는다. 다음은선택226장동일조건loopOFF,그후원본전체1348장키프레임선택/표준해상도/시간필터실험. 새미검증결과를기존PASS에포함하지않는다.


### 2026-11-09 · V5 Chase/RGB

V5상단Chase View버튼/오른쪽거리배율추가,RGB카메라뒤·위에서따라감. Reset=정확한RGB/free=추적해제. world-up고정없이회전·상대스케일유지,local점크기/nearclipping. V5서버시계하나로RGB/지도동기화,video_clock무시,디코딩중반복seek금지,RGB JPEG fallback과BEV다운로드분리. V1~V4불변. `evidence/v5_chase_rgb_20261109_03` 실제native픽셀변화/재시작/Chase이동/오류fallback/JS예외0 PASS. 01결과저장numpy bool오류와02세대대기누락실패증거는보존. `docs/LIVE_V5.md` 최신사용법참조.


### 2026-11-09 · 전체 영상 비교와 V5 검색 복원

V5생성후on-demand검색탭/current기본/전구간·표본·PE검색/RGB·3D·BEV마스크·박스/Clear복원. 지도생성중SAM3등미실행은유지. 이전V4preset재사용분기를제거해같은query라도새scope/frame검색을수행한다. annotatedRGB는정지검색오버레이필요시native대신JPEG. Chase유지. 실제SAM3 car 1장20.62초/마스크9/유효3D4,브라우저02에서새프레임검색·실제표시픽셀일치·토글/Clear/JS예외0확인.

전체1348키프레임518/16/gap10/이동0은4루프526.42초지만ATE60.00m. 전체1348입력+이동80자동선택224키프레임은1루프80.06초/GT214매칭ATE11.56m. 새run video_20261109T213652_654365000, V5job live_20261109T133652_full_keyframes를열었다. 모든기존결과보존. 일반요건/원논문과입력vs키프레임설명CLOSED_LOOP_GUIDE. 10초/80픽셀은보편조건아님.


## 2026-11-09 · Saved Object 모델 및 Search scope 표시

- 공통 query_label에 실제 저장된 모델명(SAM3 / RF-DETR / YOLOE / YOLO26 / YOLO11)과 Search scope(전체 / 현재 RGB / 표본 / PE 후보 / 생성 중), 검사 프레임 수, 유효 3D 관측 수를 함께 표시한다. 예: `car · SAM3 · 전체 224장 · 3D관측 18건 · 123456`.
- SAM3 기존 search.model 문자열도 인식한다. 모델/범위 기록 없는 과거 결과는 `모델 미기록` / `범위 미기록`으로 표시하며 추측하지 않는다. 기존 저장 파일·삭제 목록은 수정하지 않았다.
- 새 SAM3 검색과 V4 resident 검색은 backend를 명시 저장한다. Road는 SegFormer로 구분한다. RF-DETR 표시는 메타데이터 지원이며 RF-DETR 엔진 설치/연결을 뜻하지 않는다.
- 검증: 5모델×5범위 25조합 및 과거 SAM3/메타데이터 누락 확인 PASS. `tests/test_demo_camera_search.py tests/test_live4_semantics.py`:23passed. 공통 함수를 사용하는 V1/V2/V4/V5 목록에 다음 뷰어 시작 시 반영된다. 실행 중 V5는 동일 완료작업 live_20261109T133652_full_keyframes를 /api/open으로 다시 열어 새 코드 적용을 요청했다(지도 재추론 없음).


## 2026-11-09 · V5 검색 모델 선택

V5 우측 `검색 · Search` 탭의 Query 위에 `Search model`을 추가했다. SAM3(기본)/YOLOE/YOLO26/YOLO11은 실제 선택 엔진으로 검색한다. RF-DETR은 엔진·가중치 미설치로 `준비 필요` 표시, 선택 후 검색 시 명확하게 안내하고 다른 모델로 대체하지 않는다. 모델을 바꾸면 지원 클래스·자유텍스트 여부·RGB/3D/BEV Mask와Box·Search scope 안내가 바뀐다. YOLO26/11은 COCO 학습클래스만, YOLOE/SAM3은 텍스트 대상 검색이다. Road 전체 표면 처리는 별도이며 일반 YOLO 고정클래스 검색은 road/printer를 지원하지 않는다.

검색 worker는 --backend(기본sam3)로 분기한다. SAM3 의존성은 해당 분기에서만 import하며 기존 V1~V4 호출은 기본 유지. YOLO 계열은 .venv-v4와 로컬 가중치, PersistentDetector CPU를 사용한다. 한 이미지의 여러 검색어는 추론을 공유하며 클래스별 마스크를 분리한다. 캐시 identity에 backend/가중치hash/classes/confidence/size를 넣어 모델 간 캐시 혼용을 막는다. 저장 결과는 실제 backend/model과 scope를 기록하며 기존 query_label에서 표시한다.

실제 같은 KITTI 현재프레임(playback34) car검색:YOLO26/11/YOLOE 모두 completed,각2D1/유효3D1. `evidence/v5_search_models_20261109_01/results.json` 및 모델별log. 전체회귀187passed/31.48초. V5 동일 완료작업을 다시 열어 메뉴 적용; 재추론 없음. RF-DETR 실제추론과 새 모델간 정확도·속도우열은 검증하지 않았다. graft build 갱신.


## 2026-11-09 · RF-DETR-Seg 실제 연결

V5 Search model의 RF-DETR 준비필요 상태를 실제 RF-DETR-Seg Nano 검색으로 대체했다. 별도 `.venv-rfdetr`/rfdetr1.12.0/Torch2.15.0 환경, 공식 COCO Seg Nano 가중치(134545398bytes,공식MD5통과),CPU/312입력/threshold0.3. 기존 SLAM/YOLO/SAM3 환경은 변경하지 않았다. 선택기능:현재/표본/전수/PE후보,RGB마스크·박스,깊이기반3D/BEV,저장모델명·scope,Clear/선택삭제. 공식COCO클래스ID로 car/person 등을구분하고 printer/road등미지원은모델로딩전안내. 다중검색어는프레임추론공유,모델버전/가중치hash/클래스/임계값을캐시identity에포함한다.

실제 KITTI playback34/source256 car검색:2D마스크2/유효3D1,worker기록6.657초(패키지설치·다운로드제외). 전체회귀188passed/25.27초. 증거 evidence/v5_rfdetr_20261109_01의requirements.txt/model_identity.json/search_status.json/inference.log. 사용법·설치재현 docs/RFDETR_SEARCH.md. 기존현재완료run을/api/open으로재열기,지도재추론없음. 전체구간정확도·고유3D객체수·다른모델대비우열·실시간성은미검증.

- RF-DETR 실제 Chrome 최종 PASS: 모델선택/기능안내/새검색/backend=rfdetr/유효3D/저장 RF-DETR·현재RGB범위/결과선택/JS예외0. `evidence/v5_rfdetr_20261109_01/browser_checks.json`, `rfdetr_search.png`. 최초 검증은 SAM3초기값을가정한선택자 및 input값을innerText로검사해실패,현재선택허용·input.value검사로수정후통과(제품검색실패아님).


## 2026-11-09 · YOLO26 RGB 표시 누락 수정

사용자 실제 YOLO26 전수결과 search_1794270417840836000은224개고유프레임/2D639관측이있었다. 마지막playback236은검출0,235는검출1. (1) V5브라우저가재생중에는선택검색/RGB토글을무시하고원본MP4만표시하던조건을수정했다. 이제선택검색+RGB Mask또는Box ON이면재생중에도주석JPEG를표시한다. 이는지도키프레임갱신속도이며모든원본비디오프레임을새분할하지않는다. 두RGB토글OFF또는Clear이면원본영상표시로복귀한다. (2) 저장검색선택/전체관측복귀시검출없는마지막사진대신마스크있는마지막관측을연다. 전체관측의3D표시범위는유지한다. 현재프레임에검출이없는경우RGB는비어있으며다른사진의마스크를겹치지않는다.

전체회귀188passed/27.07초,JS문법검사PASS. 기존사용자전수검색·삭제목록·지도보존. V5같은완료작업재열기로새코드적용,지도재계산없음.

- 추가원인:전수검색은서브맵overlap을제외하지만타임라인은중복프레임을포함한다. 실제source256은관측index33에저장되고현재index34도동일사진이었다. RGB오버레이가index만비교해표시를놓침. V5는현재source_frame_id도전달해같은원본관측을재사용하고다른원본에는적용하지않도록수정. 중복동일사진/다른사진미적용회귀추가,query_display5passed.

- 최종전체189passed/25.98초. 실제Chrome검증PASS:사용자YOLO26전체결과선택시검출있는235프레임열기/RGB토글에따른실제JPEG픽셀변화/재생중annotatedRGB모드/프레임갱신/JS예외0. evidence/v5_yolo_rgb_20261109_01/browser_checks.json 및 yolo_playing_rgb.png. 초기브라우저검증은전수에서제외된overlap34사진과고정대기시간을사용해실패했고,동일source재사용회귀및상태대기후최종PASS. 기존검색을재사용했으며재검색·지도재생성없음.


## 2026-11-09 · Search 비활성화 고착 복구

실제 현재완료지도에서RF-DETR검색 search_1794270739076919000은20/24프레임에서KeyboardInterrupt로중단됐지만status.running/worker_pid80927이남았다. ps로PID부재확인. V5는시작시running상태만으로검색을재개감시하고프로세스없음을확인하지않아Search가영구잠겼다.

search_lifecycle를추가해저장된workerPID생존과명령/작업폴더일치(PID재사용방지)를확인한다. 종료작업은원본interrupted_status.json을보존하고failed/InterruptedWorker로전환한다. 재연결watcher에도검사,직접시작한worker는status가있어도process.poll로종료감지한다. 권한부족은종료로단정하지않는다. 감시종료버튼조건은allow_search도존중한다. 기존query결과/로그/지도/삭제목록보존,실행프로세스종료신호없음.

동일완료V5지도를재열어복구했고실제Chrome에서Search활성/새RF-DETR검색완료/유효3D/저장모델·범위/완료후Search재활성/JS예외0 PASS. evidence/v5_search_unlock_20261109_01/browser_checks.json,rfdetr_search.png,original_status.json. 회귀추가:종료PID복구·원본보존·PID재사용·정상실행작업유지. 최초전체테스트185passed/6failed는Macsubprocess비정상종료로관련항목재검사중이며전체성공을주장하지않는다.

- 종료검색복구 및 최초실패항목대상재검사26passed/21.89초. 실제RF-DETR브라우저검색정상완료후버튼다시활성확인. 전체회귀재실행결과는full_tests.log확인.

- 전체회귀재실행: 191 passed, 1 warning in 25.56s (evidence/v5_search_unlock_20261109_01/full_tests.log).


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

- 전체회귀194passed/25.50초. 초기실제버튼검사에서Box액션이panel_live5허용목록에빠져400을반환함을발견해box_3d추가수정. 수정후V5/색상관련17passed/17.89초. 두표시의기본ON및독립토글은브라우저checks.json에서검증한다.

- 최종실제Chrome PASS:두버튼기본ON/마스크점과박스모두표시/Mask OFF에도Box유지/Box OFF에도Mask유지/JS예외0. 검증후둘다ON복원. evidence/v5_3d_toggles_20261109_01/checks.json 및 3d_toggles.png. 기존저장검색재사용,새검색·지도재생성없음.


## 2026-11-10 · V5 상단 메뉴 숨기기/보이기

3D뷰상단메뉴를숨기고복원하는독립버튼추가. 메뉴전체(ViewReset/Chase/자유탐색/Mask·Box/재생·프레임/뷰크기등)를숨겨도왼쪽위의복원버튼은남는다. 오른쪽패널숨김과독립,RGB/BEV영역유지,localStorage(vggt-v5-top-menu-hidden)에선택상태보존. aria-controls/expanded 및 hidden스타일적용. HTML은요청시파일을읽으므로서버재시작/지도재생성없으며브라우저새로고침으로반영.

- 실제Chrome PASS:초기표시/메뉴숨김/복원버튼계속표시/RGB·BEV유지/새로고침후숨김유지/다시표시/JS예외0. evidence/v5_top_menu_20261110_01/checks.json 및 menu_hidden.png/menu_shown.png.


## 2026-11-10 · 영상 선택/지도 생성 영역 숨기기

8107컨트롤러헤더에영상설정숨기기/보이기버튼추가. 스크린샷의영상선택·생성/중지·이전지도·해상도·처리설정과상세상태행을함께접는다. 접힌상태에도헤더에간단한단계/경과시간과복원버튼유지. flex레이아웃으로줄어든영역만큼지도workspace높이확장,localStorage(vggt-v5-generation-hidden)상태보존. 3D뷰자체상단메뉴/오른쪽패널토글과독립적이며실행작업/선택파일/입력값은숨김으로변경하지않는다. HTML파일요청시읽기,서버재시작없음.

- 실제Chrome PASS:초기표시/전체영역숨김/복원버튼유지/지도높이확장/간단한상태유지/새로고침상태보존/복원/JS예외0. evidence/v5_generation_menu_20261110_01/checks.json,generation_hidden.png,generation_shown.png.
