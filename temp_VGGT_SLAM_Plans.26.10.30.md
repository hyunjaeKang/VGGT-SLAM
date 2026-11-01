# VGGT-SLAM 전체 기능 데모 구현·실험 계획

작성: 2026-10-30. 작업 루트: `/Users/hyunjae.kang/2026_opensrc/VGGT_SLAM/vggt_slam_map`.
입력 변경: 사용자 요청에 따라 RealSense 필수 실증을 비디오 파일 기반 점진 입력으로 대체한다(2026-10-30). 원래 RealSense 기능은 보존하되 이번 검증 범위에서 제외한다.

상태: **계획만 작성됨. 이번 계획 작성 턴에는 구현·모델 설치·추론·새 서버 실행을 시작하지 않는다. 사용자가 모델을 변경하고 실행 프롬프트를 제출한 뒤 진행한다.**

## 1. 목표와 성공의 정의

사용자가 한 프로그램에서 원본 RGB, 추정 깊이, 색상 점군, 카메라 궤적, 서브맵 연결, 장소 재인식, 그래프 보정, 텍스트 객체 검색 및 카메라 입력을 단계별로 관찰하는 로컬 데모를 만든다. 각 화면은 실제 실행 증거와 연결한다. 기존 SLAM 핵심 알고리즘을 교체하는 프로젝트가 아니다.

주 데모는 자율주행으로 한다. 모든 기능을 억지로 한 데이터셋에 넣지 않고 다음 세 장면을 하나의 Viser 프로그램에서 선택하게 한다.

1. **Drive:** PandaSet 003으로 짧고 재현 가능한 밀집 복원·궤적·서브맵·평가를 보여준다. KITTI-360의 검증된 재방문 구간으로 루프 검출과 보정 과정을 보여준다.
2. **Objects / Indoor:** 실제 물체가 잘 보이는 짧은 실내 RGB 시퀀스로 `chair`, `monitor`, `printer` 등 텍스트 검색→선택 이미지→마스크→3D OBB를 보여준다. 없는 물체를 성공 예제로 만들지 않는다.
3. **Video:** MP4/MOV 등 비디오 파일을 프레임 순서대로 디코딩하여 기존 점진 처리 경로에 공급한다. 입력 영상과 새 지도 생성이 함께 진행되는 모습을 보여준다. RealSense 물리장치 실증은 이번 범위에서 제외한다. 비디오 입력 추론과 저장된 결과 재생은 화면에서 구분한다.

추가 화면은 BEV·표면 높이·표면 등고선이다. 원래 일곱 기능과 구분하여 부가 기능으로 표시한다. 지면 정확도를 검증하지 못하면 지형도라고 부르지 않는다.

**완성 단계 두 가지:**

- 통합 프로그램 완성: 모든 기능의 실행 경로와 오류 처리가 있고, 사용 가능한 데이터·장치에서 실제 실행 검증됨. 미설치·장치 없음은 구체적 상태로 표시됨.
- 일곱 기능 전체 실증 완료: 수정된 F1~F7 모두 실제 모델·비디오 실행 증거로 PASS. F6는 RealSense 대신 비디오 파일 기반 점진 입력으로 대체한다. 따라서 일곱 항목 완료 시에도 원본 RealSense 기능을 검증했다고 주장하지 않는다. SAM3가 실행되지 않으면 전체 실증 완료라고 보고하지 않는다. 모의 데이터 테스트는 별도 기록한다.

## 2. 구현 담당 모델 추천

**주 담당: GPT-6.1 Terra.** 클라이언트에 표시되는 Terra를 선택하고, reasoning은 Medium부터 시작한다. 단계의 회귀·좌표변환·스레드 문제가 남으면 지원되는 High로 높인다. 높은 설정을 항상 사용할 필요는 없다. Luna를 사용한다면 High부터 시작하고 작업 범위를 아래의 한 단계 또는 한 테스트로 제한한다. 계정·클라이언트별 선택 가능 여부는 실제 모델 메뉴에서 확인한다.

| 모델 | 이 프로젝트에서 권하는 역할 | 유의점 |
|---|---|---|
| Terra | 작은 범위의 구현, Viser 화면 통합, 회귀 수정, 실제 화면 확인 | 전체 SLAM 문제를 한 번에 맡기지 말고 단계별 입출력·증거·완료 조건을 제공 |
| Luna | 명시된 스키마 테스트, 로그 추출, 설정 문서, 보고서 갱신 | 좌표계·최적화·스레드 변경을 넓게 묶지 않음 |

이것은 프로젝트 요구에 따른 추천이며 Terra가 Luna보다 항상 더 정확하거나 더 저렴하다는 벤치마크 주장이 아니다. 두 모델의 정확한 파라미터 크기나 이 계정의 비용은 확인하지 않았다. 또한 **코딩 에이전트 모델 변경은 로컬 VGGT-1B·SALAD·PE·SAM3의 크기나 GPU 메모리를 줄이지 않는다.**

공식 문서 확인: OpenAI는 Terra를 시각 이해·컴퓨터 사용·범위가 정해진 코드 수정에, Luna를 효율적인 집중 작업·자동화에 설명한다. 명확한 입력·요구사항·검증 방법을 주라는 지침에 맞춰 이 계획을 나눴다.

- [OpenAI model selection](https://developers.openai.com/api/docs/guides/model-selection)
- [ChatGPT Work / Codex models and switching](https://learn.chatgpt.com/docs/models)

CLI 사용 시 공식 문서상 `codex -m gpt-6.1-terra`이며 Terra에는 Codex CLI 0.159.0 이상이 필요하다. 이미 사용하는 앱에서는 모델 메뉴를 쓰면 된다. 지금 모델을 자동 변경하거나 CLI를 업그레이드하지 않는다.

## 3. 확인한 현재 상태와 보존할 결과

### 3.1 코드 기준점

다음은 작성 시점의 graft 코드 위치다. 구현 시 파일 변경으로 줄 번호가 달라질 수 있으므로 심볼로 다시 조회한다.

| 기능 / 책임 | 현재 위치 | 이번에 필요한 연결 |
|---|---|---|
| 오프라인 실행·결과 저장 | `main.py:44–244` | 실행 이벤트·데모 출력, headless와 run_os 충돌 보존 |
| 깊이·자세 추론 / 루프 후보 검증 | `vggt_slam/solver.py:304–398`, `Solver.run_predictions` | RGB·depth·confidence·후보와 검증 결과 저장 |
| 점군·서브맵·연결 제약 | `vggt_slam/solver.py:124–293`, `add_edge`, `add_points` | 서브맵별 관측 자료, 실제 그래프 edge 의미 기록 |
| 최적화 | `vggt_slam/graph.py:80–127`, `PoseGraph.optimize` | 초기/최종 graph error, 전후 카메라·점군 변환 snapshot |
| 객체 검색 UI | `vggt_slam/viewer.py:176–238`, `Viewer.add_object_query_gui` | 결과 구조화·저장·박스 수명 관리·무효점 처리 |
| 카메라 추상화 | `vggt_slam/cameras.py:9–53`, `Camera`, `RealSenseCamera` | 비디오 디코딩·RGB 리플레이 backend, EOF·종료 정책 |
| 라이브 루프 | `main_realtime.py:153–332` | EOF, bounded queue, 종료·오류·지연 계측 |
| 전체 점군 I/O | `vggt_slam/pcd_io.py`, `Map.write_points_to_file` | 기존 스트리밍 / memmap 재사용 |
| 저장 결과 뷰어 | `scripts/view_saved_map.py:13–90` | 제한된 점 수 / Fit 동작 재사용 |
| 평가 | `scripts/evaluate_pandaset.py`, `scripts/evaluate_kitti360.py`, `evals/eval_tum.sh`, `evals/process_logs_tum.py` | 데이터셋별 정확한 대응·평가 출처 표시 |
| 부가 지도 | `scripts/export_bev_maps.py:73–284` | surface_only와 결측값·클립 기록 재사용 |

`--overlapping_window_size`는 현재 1만 지원, `--max_loops`는 0 또는 1만 지원한다. `--headless`와 `--run_os`는 함께 사용할 수 없다. `--lc_thres`의 증감 의미는 도움말만 믿지 말고 실제 `ImageRetrieval.find_loop_closures` 비교식을 조회한다. 기본값을 임의로 바꾸지 않는다.

현재 객체 검색은 PE 이미지 임베딩으로 프레임 하나를 고르고 SAM3로 그 프레임을 분할한 뒤 지도점에서 OBB를 계산한다. 전 지도 모든 객체를 exhaustive 검색하거나 객체를 장기간 추적하는 기능이 아니다. 데모도 이 범위를 정확히 설명한다.

### 3.2 로컬 데이터와 결과

- PandaSet 003 RGB: `/Users/hyunjae.kang/9000_Data/9002_ExpData/pandaset/003/camera/front_camera`, 80장. 기존 기록은 `docs/PANDASET003_TEST.md`.
- KITTI-360 RGB: `/Users/hyunjae.kang/Downloads/2013_05_28_drive_0000_sync/image_00/data_rect`, 11,518장. 기존 기록은 `docs/KITTI360_0000_RUN.md`.
- KITTI 기준 카메라 자세: `logs/kitti360_0000_reference/cam0_to_world.txt`. 루프 체크: `logs/kitti360_0000_loop_reference_checks.json`.
- KITTI 전체 기존 점군: `logs/kitti360_0000_poses_points.pcd`, 212,204,997점, 약 3.16GiB. 궤적 RMSE 321.266m: 실패 분석 사례로만 사용한다.
- PandaSet 기존 정렬 ATE: 루프 OFF 0.290m, ON 0.558m. 기존 제약은 전진 주행의 근접 프레임 쌍이므로 실제 재방문 성공 사례로 세지 않는다.
- 기존 브라우저 포트는 8080/8081/8082를 썼다. 실제 점유 상태를 확인하고 새 통합 데모 기본 포트는 8090, 점유 시 오류와 다른 포트 지정법을 표시한다. 다른 프로세스를 임의 종료하지 않는다.
- 확인 시 `.venv` 배포 메타데이터에 `sam3`, `pyrealsense2`, `evo`가 없고 `examples/`도 없다. editable 경로·실제 import 가능 여부는 다음 실행자가 별도 확인해야 한다. RealSense 실물 연결 여부는 아직 확인하지 않았다.
- 기존 핵심 회귀 47개 통과 기록: `logs/large_map_tests.txt`. 구현 시작 시 현재 상태를 확인하되 비싼 추론을 반복하지 않는다.

### 3.3 작업 규칙

1. 사용자 원본 데이터·기존 logs·기존 수정은 보존한다. `git reset/clean`, 덮어쓰기, 임의 commit 금지.
2. 모든 새 실행은 `logs/demo_runs/<run_id>/`를 새로 만들고 실행 식별자를 기록한다. 동일 run_id가 있으면 기본 거부한다.
3. AGENTS.md에 따라 graft를 먼저 사용한다. 심볼을 바꾸기 전 `graft callers <symbol> --depth all`. 그래프가 가리킨 필요한 범위만 읽는다. 큰 변경 뒤 `graft build`.
4. 문서의 계획 명령과 실제 존재하는 명령을 구분한다. 아래 `demo.py`, `scripts/demo_*`는 **신규 구현 대상**이며 현재 실행할 수 있다고 주장하지 않는다.
5. 단계 하나를 구현→관련 테스트→실데이터 소량 확인→진행 기록 갱신 순으로 처리한다. 실패 시 다음 대규모 실험으로 넘어가지 않는다.
6. 자동 하위 에이전트·외부 유료 GPU·외부 서비스 업로드는 이 계획에 포함하지 않는다. 한 실행자가 순차 진행한다.

## 4. 관객이 볼 화면과 시연 순서

Viser 기반 한 로컬 프로그램을 우선한다. 별도 React·클라우드 사이트·외부 LLM API 없이 구현한다. 처리 파이프라인과 뷰어는 분리해 저장 산출물만으로 재생할 수 있게 한다.

| 화면 | 사용자의 행동 | 실제로 보여줄 증거 |
|---|---|---|
| 장면·실행 선택 | Drive / Loop / Indoor / Video 선택 | 데이터 출처, 비디오 입력 추론/이미지 replay/캐시 배지, 지원 상태 |
| 프레임 탐색 | 타임라인 / 재생 / 정지 | 원본 RGB, 같은 프레임의 depth·confidence, 선택 카메라 frustum |
| 3D 재구성 | 점 수·confidence·서브맵 색 전환 | 점군, 카메라 궤적, 서브맵 경계, 원본점 수와 표시점 수 |
| 서브맵·그래프 | 연결 edge 선택 | 겹침 프레임, 실제 제약 종류, 노드와 edge, 미연결 상태 |
| 루프 검사 | 검출 이벤트 선택 | query/후보 이미지, 검증값, 수락·거절 이유, 실제 재방문 검증 |
| 보정 비교 | Before / After / Loops OFF 토글 | 같은 시점의 전후 점군·궤적, 내부 목적함수, GT 기반 ATE 별도 |
| 객체 검색 | 텍스트 입력·Search·Clear | 선택 RGB, 마스크, score 종류, 3D OBB, 미검출 이유 |
| Video | 파일 선택·Start·Pause·Step·Stop | RGB 입력, 영상 시간, 디코딩/추론 FPS, backlog·drop, 새 서브맵 반영 |
| 평가·저장 | 결과 열기·보고서 보기 | 프레임 대응수·정렬법·ATE, PCD/TUM/JSON 위치 |
| 부가 지도 | BEV / 표면 높이 전환 | 축척 출처·미지 셀·표면/지면 구분 |

8~10분 시연안: ① PandaSet 원본→depth→3D (2분), ② 서브맵 순차 연결 (1분), ③ 실제 재방문·최적화 전후 및 정량 비교 (2분), ④ 객체 검색과 미검출 (2분), ⑤ 비디오 파일 입력과 점진 지도 생성 (1분), ⑥ 평가·저장·한계 (1분). 재생 속도와 실제 추론 처리량을 별도로 표시한다.

## 5. 데이터 선정과 실험 설계

### D0 — 빠른 개발 데이터

PandaSet 003의 정렬된 80장 중 처음 17~33장으로 1~2개 서브맵 smoke test. 전체 80장 결과는 기존 파일을 먼저 활용한다. 원본 이름을 보존한 목록/심볼릭 링크로 subset을 만들고 무작위 프레임을 섞지 않는다. 키프레임을 미리 고르면 `--min_disparity 0`으로 동일 목록을 두 비교군에 준다.

### D1 — 주행 복원·평가

PandaSet 003 전체 80장, `submap_size=16`, overlap=1, confidence=25, loops OFF/ON. 기존 결과를 read-only로 등록하고, 새 이벤트가 필요할 때만 같은 조건으로 새 run_id에 재실행한다. 단일 전방 RGB로 처리하며 LiDAR·다중 카메라 융합으로 부르지 않는다.

### D2 — 실제 루프 재방문

KITTI-360에서 기존에 기준 위치로 확인한 쌍 `508↔1826`을 **초기 후보**로 한다. 시간상 연속인 508~1855 범위를 살펴서 출발 근처와 재방문을 포함하는 구간을 선정한다. 최종 범위는 접촉 시트·기준 경로로 확인 후 고정한다. 508과 1826 두 이미지만 붙인 것을 연속 주행 지도 실험으로 쓰지 않는다.

- 기준 pose가 있는지, endpoint 근접도와 중간 최대 이동거리·경로 길이를 기록한다.
- 연속 구간의 광류 기반 keyframe 80~200장을 우선 목표로 한다. 단순 고정 간격으로 줄여 overlap이 깨지지 않도록 시각적으로 확인한다. 원본 구간·선택 목록·임계값·제외 이유를 남긴다.
- 같은 keyframe 목록으로 loops=0, loops=1 비교. 루프 후보 수, 수락 수, 실제 GT 근접도, 전후 objective, 정렬 ATE를 기록한다.
- 루프 미검출이면 먼저 목록이 재방문과 중간 경로를 담는지·검색 제외 규칙을 확인한다. 알고리즘 비교식을 읽고 임계값 조정 한 번만 수행한다. 여전히 실패하면 실패를 기록하고 실내 루프 장면을 보충한다.
- 개선 여부는 측정 결과대로 보고한다. 적어도 하나의 실제 루프 수락과 실제 before/after 변화는 기능 실증 목표다. **ATE 개선 실증은 ON이 OFF보다 낮을 때만 PASS**다. 내부 graph error 감소만으로 외부 정확도가 개선됐다고 하지 않는다.
- 8.4km 전체를 또 재실행하지 않는다. 기존 전체 결과는 실패 비교 화면으로 남긴다.

### D3 — 실내 객체·TUM 평가 보충

로컬 데이터를 먼저 확인한다. README 기본 `examples/kitchen`은 현재 없다. 없으면 공식 TUM RGB-D 중 `freiburg1_desk`를 객체·정량평가 후보, `freiburg1_360` 또는 `freiburg1_room`을 루프 후보로 검토한다. 이는 **후보이며 이번 턴에 다운로드·적합성 확인하지 않았다.** 다운로드가 필요하면 실행 시 공식 출처·라이선스·용량·timestamp·groundtruth를 확인한다. 한 번에 전체 9개 평가 시퀀스를 받지 않는다.

대안은 휴대전화·일반 카메라로 고정 물체가 있는 방을 천천히 돌아 같은 장소로 오는 30~60초 비디오를 녹화하는 것이다. 흔들림·모션 블러·빠른 회전·줌·장면 전환이 적고 시점 간 중첩이 충분한 영상을 사용한다. 이 경우 GT가 없으면 ATE는 N/A다. RGB-D 데이터라도 추론에는 RGB만 사용하고 groundtruth는 평가에만 쓴다.

검색 쿼리는 접촉 시트에 실제 존재하는 물체 3개와 존재하지 않는 대조 1개를 확정한다. 자율주행 데이터에서도 `car` 등을 보조 시연하되 움직이는 물체의 점군과 가림 때문에 3D box가 불안정할 수 있음을 결과에 기록한다. 데이터에 없는 `printer`를 필수 성공 항목으로 삼지 않는다.

### D4 — 입력 모드

Video: OpenCV VideoCapture 등을 이용해 파일을 순차 디코딩하고 BGR uint8 프레임·원본 frame index·presentation timestamp(PTS)를 전달한다. VFR은 유효한 PTS를 우선하고, 사용할 수 없으면 명시된 CFR 가정 frame_index/FPS로 시간을 계산해 approximate라고 기록한다. 잘못된 FPS·뒤로 가는 timestamp·디코딩 실패를 검사한다. MP4/MOV는 컨테이너이므로 실제 codec 지원은 열기와 여러 프레임 디코딩으로 확인한다. 필요하면 실행 시 지원 코덱으로 변환하되 원본을 보존하고 변환 정보를 기록한다.

이미지 Replay: PandaSet/실내 이미지 시퀀스를 timestamp 순으로 공급한다. 원본 timestamp가 없으면 synthetic 시간임을 명시한다. 비디오가 아직 없으면 이 이미지들을 무손실 또는 고품질 MP4로 만드는 테스트 fixture를 사용하고 원본 이미지/GT 대응 sidecar를 남긴다. 이미지 직접 입력과 MP4 디코딩 경로를 모두 확인한다.

두 실행 정책을 분리한다. 기본 offline-paced 모드는 추론에 맞춰 입력을 늦추고 프레임을 처리해 파일 재현성을 우선한다. realtime-paced 모드는 영상 시각에 맞춰 공급하고 bounded backlog/drop 정책을 사용한다. 입력 FPS·디코딩 FPS·처리 FPS·표시 FPS를 따로 기록한다. 단순 영상 seek로 기존 SLAM 상태를 되감지 않는다. 점진 추론 세션에서 임의 seek는 금지하거나 새 세션으로 reset하고, 자유로운 seek는 캐시 결과 뷰어에서 제공한다.

## 6. 신규 구조와 산출물 계약

권장 파일(구현 중 필요하면 최소 범위로 합칠 수 있으나 책임은 유지):

```text
demo.py                         # 신규 CLI: doctor / prepare / run / view / evaluate
vggt_slam/demo/
  schema.py                     # 설정·manifest·event 검증, 무거운 모델 import 없음
  recording.py                  # JSONL 이벤트·자산 저장, 원자적 manifest
  pipeline.py                   # 기존 Solver 연결, 중복 추론 엔진 만들지 않음
  viewer.py                     # Viser 데모 UI, 캐시 재생
  semantic.py                   # 기존 검색 흐름의 공통 서비스·검색 결과 저장
  replay.py                     # Camera 규약 준수 이미지 replay·비디오 파일 입력
scripts/demo_select_data.py      # 연속 구간·키프레임 목록 생성
scripts/demo_report.py           # evidence/metrics를 사람이 읽을 보고서로 변환
configs/demo/*.json              # 의존성을 줄이기 위해 JSON 사용
requirements-demo-open-set.txt  # 필요 시 별도 환경용, 실제 호환 검증 후 작성
# 비디오 입력은 기존 OpenCV 우선 재사용; codec/PTS가 부족할 때만 별도 선택 의존성 기록
logs/demo_runs/<run_id>/
  config.json, manifest.json, events.jsonl, stdout.log, status.json
  selection.json, frames.jsonl
  frames/<frame_id>/rgb.jpg, depth.npz, depth.png, confidence.png
  submaps/<id>/preview.npz
  snapshots/<step>/{before,after}_cameras.npz
  snapshots/<step>/{before,after}_transforms.npz
  loops/<event_id>/query.jpg, candidate.jpg, decision.json
  queries/<query_id>/result.json, selected.jpg, masks.npz, overlay.png, boxes.json
  poses.txt, camera_matrices.npz, points.pcd
  evaluation/metrics.json, frame_errors.csv, trajectory.png
  evidence/coverage.json, browser.json, screenshots/
  report.md
```

### 계약의 필수 내용

- manifest: `schema_version`, run_id, 데이터 경로/목록 checksum, 설정, 코드 HEAD 및 dirty 여부, 장치·패키지·모델/checkpoint 식별자, source_mode (`offline_compute`, `cached_playback`, `rgb_replay`, `video_file`), 시간, 상태, 산출물 상대경로, 기능별 상태. 토큰·인증키 저장 금지.
- frames: 고유 frame_id, 원본 파일명, 원본 timestamp/유형, 처리 순서, 서브맵 소속과 overlap 여부, RGB/깊이 해상도·매핑·intrinsics. TUM의 첫 열이 frame ID인지 실제 timestamp인지 명확하게 구분.
- event 공통: schema_version, 단조 증가 seq, run_id, event_type, 발생 wall time, source_frame_id, submap_id, asset_paths, payload. 연결관계는 실제 ID로 참조.
- event 종류: frame_selected, submap_created, overlap_edge_added, loop_candidate, loop_validation, loop_constraint_added, optimization_started/finished, query_started/finished/failed, camera_started/stopped, input_dropped, run_completed/failed.
- loop 후보와 기하 검증 수락·제약 삽입을 분리한다. 실제 코드의 `image_match_ratio`와 검색 score·거리의 종류 및 임계값을 함께 기록한다. 서로 다른 score를 하나의 확률처럼 표시하지 않는다.
- 최적화: 초기/최종 error, time, 실제 제약 수, 변환 전후 snapshot. 중간 그래프에 미래 노드를 붙여서 과거 최적화처럼 보여주지 않는다.
- 좌표: 재구성 world·local submap·camera·정답 world를 구분. projective homography는 일반 SE(3)라고 부르지 않는다. 카메라 quaternion만으로 점군 변환을 대체하지 않는다.
- 검색 결과: query, 선택 frame/submap, 모델 식별자, retrieval score 의미, SAM score, 마스크 크기, 대응 valid 3D점 수, box center/extent/rotation의 좌표계, 검출 상태, 소요시간. 부족·퇴화 점군은 box 미생성 사유 저장.
- coverage: `PASS`, `FAIL`, `BLOCKED`, `NOT_RUN`, `N/A`와 evidence 상대경로·사유. mock 통과와 실제 실증은 다른 필드.

**캐시 한계:** 기존 PCD/TUM만으로 깊이·프레임 embedding·픽셀별 3D 대응·최적화 중간 상태를 복원할 수 없다. 기존 파일 등록 시 제공 가능한 기능만 활성화한다. 동적 semantic 검색은 필요한 프레임/임베딩/매핑을 가진 캐시를 새로 생성해야 한다. 녹화된 검색 결과 재생은 “저장 결과”로 표시하고 live 검색으로 부르지 않는다.

## 7. 실행 단계 — Terra가 순차 수행할 작업

각 단계 완료 시 `docs/DEMO_PROGRESS.md`에 목표·수정 파일·명령·결과·다음 작업을 갱신한다. 파일 1~3개 또는 하나의 수직 기능 단위로 작게 변경한다. 단계 완료마다 작업을 무조건 멈출 필요는 없지만 선행조건을 무시하고 넘어가지 않는다.

### S00. 현황 고정 / 진단만

입력: 본 계획, AGENTS.md, 기존 실행 보고서.

1. `pwd`, `git status --short`, graft map/필요 심볼 확인. 모델명은 UI에서 사용자가 선택하며 코드로 바꾸지 않는다.
2. 기존 결과·데이터·사용 포트·디스크 여유·MPS·CUDA·배포 패키지·체크포인트 cache 경로를 조사한다. 장치 연결 확인은 무거운 VGGT 로드 전에 한다.
3. 기존 테스트 47개 기준을 현재 테스트 결과와 비교한다. 차이를 기록한다.
4. `docs/DEMO_PROGRESS.md`, 기능 F1~F7의 초기 상태표를 만든다.

완료: 경로/의존성/하드웨어 지원표와 보존해야 하는 사용자 변경 목록이 있다. 원본 실행·패키지 변경은 아직 없다.

### S01. 데이터·run 디렉터리와 manifest

1. 가벼운 schema·설정 로딩·run 생성 기능부터 작성한다.
2. 파일명 숫자 정렬, 연속 범위, subset 원본 ID·timestamp 보존, 중복·결측·깨진 이미지 처리를 구현한다.
3. PandaSet 기존 결과 read-only 등록, KITTI 실패 예제 read-only 등록을 구현한다.
4. 신규 `demo.py doctor`, `prepare --config ...`가 실제 지원하는 옵션을 help에 명시한다. 이미지 manifest만 만들고 prepare에서 추론을 시작하지 않는다.

검증: 겹치는 run_id 거부, 경로에 공백, 깨진 RGB, sparse frame ID, timestamp 없는 입력을 검증한다. 기존 3GiB PCD 복사·재저장 없이 등록되는지 확인한다.
완료: 결정적인 selection.json/manifest와 실패 상태를 얻는다.

### S02. 이벤트와 깊이·신뢰도 저장

수정 전 `graft callers run_predictions --depth all`과 `add_points` 영향 확인.

1. 기존 inference 반환값에서 원본/전처리 frame ID 대응을 보존한다.
2. RGB, 원시 float depth, confidence, 시각화 depth 범위·결측 마스크를 저장한다. depth를 미터로 검증하기 전 “상대 깊이”로 표시한다.
3. JSONL recorder를 선택적으로 연결한다. 비활성 기본 경로는 기존 결과와 같아야 한다. CPU float로 이동한 배열을 저장하고 GPU tensor를 recorder에 오래 붙잡지 않는다.
4. frame_selected/submap_created 및 overlap 정보를 실제 처리 지점에 기록한다.

검증: 합성 프레임의 픽셀 매핑·해상도, 이벤트의 ID 참조, recorder 비활성 동작을 테스트. D0 한 서브맵 실제 모델 실행.
완료: 같은 프레임의 RGB/depth/confidence와 이벤트가 열린다.

### S03. 루프·그래프 및 before/after 기록

1. `PoseGraph.optimize`, `Solver.add_edge`, retrieval callers를 조회한다.
2. 후보·거절·수락·실제 edge 삽입 이벤트를 각각 기록한다. 기존 match ratio 0.95 등 의미는 코드 그대로 보존한다.
3. optimize 호출 직전·직후 같은 노드 집합의 투영카메라·homography를 저장한다. graph 내부 error와 time을 반환/이벤트로 노출한다. 기존 무기록 실행의 호출 호환성을 유지한다.
4. 작은 서브맵 local point preview를 저장하고 전후 homography로 정확히 재투영한다. 매 optimize마다 전체 dense PCD를 복제하지 않는다.
5. 그래프 UI에서 “카메라 노드와 서브맵 묶음”을 구분한다. 임의의 서브맵 중심선은 실제 constraint가 아니라 시각 요약임을 표시한다.

검증: 작은 synthetic graph에서 before와 after가 바뀌고 error가 유한함을 확인. error 감소를 강제로 조작하지 않는다. 기록하지 않은 기존 알고리즘과 수치 동작이 달라지면 원인을 해결한다.
완료: 실제 루프 이벤트→제약→최적화 결과의 trace가 한 ID 체계로 이어진다.

### S04. 먼저 동작하는 캐시 뷰어

1. Viser viewer에 dataset/run 선택, 타임라인, RGB/depth, 점군·궤적·frustum, 서브맵 색상을 붙인다.
2. 표시점 기본 300,000, 최대 2,000,000. 모든 프레임·서브맵을 균등하게 대표하도록 결정적으로 샘플링한다. 핸들을 교체·제거해 누적 메모리를 막는다.
3. 원본점 수·표시점 수·결측 자산·좌표 단위를 표시한다. 큰 PCD는 memmap을 유지한다.
4. Before/After는 같은 좌표계/시점에서 토글. loops OFF와 ON은 독립 run임을 표시한다. 비교를 위한 GT 정렬은 선택적인 사후 표시라고 명시한다.
5. 플레이 시간과 계산 시간, source_mode 배지를 계속 표시한다.

검증: Chrome 실제 WebSocket 연결, 타임라인 끝·되감기·점 수 변경·Fit·run 전환. PNG만 생성하고 UI 검증했다고 하지 않는다.
완료: 모델 로드 없이 기존 PandaSet와 KITTI 실패 예제를 탐색할 수 있다. 깊이 없는 기존 run은 명확히 비활성.

### S05. 통제된 주행·루프 비교 실험

1. D1 기존 결과를 활용하고 S02/S03 자산이 필요한 경우 새 run으로 80장 재실행한다.
2. D2 후보의 접촉 시트·기준 경로를 확인하고 연속 keyframe 목록을 고정한다.
3. 정확히 같은 목록·checkpoint·submap·confidence로 OFF와 ON 2회 실행한다. 가능한 seed와 비결정성도 기록한다. GT를 추론·threshold 선택에 주입하지 않는다.
4. 전체 대응 프레임의 Sim(3) ATE·median·max, 대응수, 실행시간, raw point 수, loop 후보/수락/GT 간격을 저장한다. 전후 snapshot 비교와 OFF/ON 비교를 구분한다.
5. ATE 개선·미개선 모두 보여준다. 결과가 나빠지면 실패를 숨기거나 전체 결과에서 쉬운 구간만 사후 선택하지 않는다.

완료: 실제 루프 증거가 있거나, 정해진 시도 내 실패 및 보충 데이터 필요가 명확하다. 장거리 알고리즘 연구로 범위를 확대하지 않는다.

### S06. Open-set 환경 호환성의 작은 실험

1. SAM3/PE 저장소·현재 setup 옵션·checkpoint 접근·torch/torchvision 요구·MPS 연산을 확인한다. 라이선스 동의나 접근 token이 필요하면 사용자에게 실제 필요한 항목만 알리고 다른 독립 작업을 진행한다. 자동 동의·토큰 우회 금지.
2. 기존 `.venv` torch 2.3.1 기반 복원을 깨지 않도록 필요하면 `.venv-demo-open-set` 별도 환경을 만든다. 핵심 환경을 일괄 upgrade하지 않는다.
3. 실내 RGB 한 장으로 PE 이미지·텍스트 embedding과 SAM3 text mask를 독립 실행한다. 각 모델의 실제 device를 확인한다. `build_sam3_image_model()`의 device 인자를 확인해 기본 CUDA 가정을 점검한다.
4. MPS 미지원이면 작은 입력 CPU fallback을 시험하고 실제 시간을 기록한다. 이것도 실패하면 ERROR/BLOCKED로 남긴다. 외부 GPU 비용을 발생시키지 않는다.

완료: 한 장의 실제 embedding·mask가 저장되거나 정확한 호환 오류·환경 재현법이 남는다. 이 단계가 실패해도 F1~F4와 UI 작업은 계속 가능하다.

### S07. 객체 검색의 실제 3D 결과

1. `Viewer.add_object_query_gui`와 두 main의 중복 검색 흐름 callers를 확인하고 공통 결과 서비스를 작게 추출한다. 단순 검색 UI 복사로 세 번째 구현을 만들지 않는다.
2. 검색 인덱스에 선택 frame·embedding·RGB·intrinsics·픽셀 depth/validity·서브맵 local 좌표와 graph homography를 보존한다. cache 버전·필수 항목을 검사한다.
3. SAM mask 좌표를 모델 전처리 좌표와 맞추고 confidence/finite/depth mask를 적용해 world 점을 얻는다. 점 수 부족·중복·일직선·평면 등 OBB 퇴화를 처리한다.
4. 박스 회전은 proper rotation, extent는 양수·유한값인지 검사한다. projective 변환을 OBB 회전에 그대로 곱하지 않는다. 변환된 점에서 box를 다시 계산한다.
5. query 결과마다 retrieval/mask/점/box 증거를 저장한다. Search 중 중복 요청은 막고 map snapshot과 결과 version을 맞춘다. Clear는 기존 query 박스·마스크를 실제로 제거한다.
6. 대표 실내 존재 쿼리 3개와 부재 1개를 수동 검토한다. 적어도 두 실제 객체에서 RGB mask와 3D 대응이 설득력 있어야 PASS. 부재 쿼리의 오탐도 결과대로 기록한다.

완료: 실제 모델로 query→선택 프레임→mask→3D box가 연결되고, 저장 결과를 다시 열 수 있다. 캐시 없는 PCD에 가짜 box를 그려 시연하지 않는다.

### S08. 비디오·이미지 Replay 입력과 정상 종료

1. `Camera` 규약을 지키는 이미지 replay와 비디오 파일 입력 backend를 추가한다. 파일 경로·범위·FPS/PTS·회전 metadata 적용 정책을 검증한다. `None=일시적 무프레임`과 EOF를 구분한다. EOF에서 무한 reconnect하지 않는다.
2. source timestamp·wall time, pause/step, max_frames·duration, stop_event·bounded open/read timeout을 구현한다. offline-paced와 realtime-paced 모드를 제공한다. 비디오 EOF는 정상 종료이고 파일 오류는 제한된 실패 처리로 끝내며 카메라 재연결 루프로 보내지 않는다. 기존 실카메라 코드는 호환성을 보존하되 실증 대상에서 제외한다.
3. solver worker는 하나, 대기 입력은 bounded. 처리 지연 시 보존할 overlap anchor와 drop 정책을 명시한다. drop frame 수와 queue 길이를 기록한다.
4. 정지 시 capture 해제→진행 중 worker 완료→남은 유효 프레임 flush→점군/카메라 백업/poses 저장→상태 완료 순으로 정리한다. worker 예외는 부모/UI로 전달한다.
5. 라이브 경로의 결과 저장도 오프라인처럼 복구 가능한 순서를 적용한다. Ctrl+C와 UI Stop을 같은 종료 절차로 연결한다.

검증: EOF, 첫 프레임 timeout, 일시적 None, 강제 worker 오류, 17장보다 짧은 입력, backlog, Stop. mock 카메라 테스트 후 33~80장 실제 RGB replay.
완료: 비디오 파일과 이미지 replay 입력이 실제 SLAM을 점진 실행한다. 저장 캐시를 재생하는 기능과 다른 배지를 쓴다.

### S09. 실제 비디오 파일 실증

1. 30~60초의 연속 주행 또는 실내 비디오를 선택한다. 경로·checksum·컨테이너·codec·해상도·회전·duration·FPS/PTS 정책을 기록한다. 파일이 없으면 D4의 이미지 기반 MP4 fixture를 만들되 합성 재포장 자료임을 명시한다.
2. 모델 없이 처음·중간·끝 프레임 디코딩, timestamp 단조성, EOF·빈 파일·손상된 파일 오류를 확인한다. 디코딩 불가를 장치 미연결로 표시하지 않는다.
3. 실제 모델로 짧은 범위를 실행한 뒤 30~60초로 확대한다. 입력 모드는 video_file, 실제 pacing과 source/처리 시간·drop·latency p50/p95를 저장한다.
4. 새 서브맵 두 개 이상이 점진 뷰에 반영되고 Pause/Step/Stop 및 EOF 후 잔여 프레임 flush·저장·재열기를 확인한다. EOF 이후 자동 처음부터 반복하여 지도를 오염시키지 않는다.
5. offline-paced와 realtime-paced를 각각 확인한다. 기본은 offline-paced로 하고, 원속도 처리가 안 되면 실제 처리량과 drop을 그대로 보여준다. 기존 이미지 기반 GT를 사용한 MP4 fixture는 frame/timestamp sidecar로 정확히 대응한다. 일반 MP4에 GT가 없으면 ATE N/A다.

완료: 파일을 실제 디코딩해 점진 추론·지도 반영·종료 저장까지 확인했다. 저장된 지도만 재생하거나 미리 추출한 이미지만 읽고 비디오 디코딩 실증 PASS로 하지 않는다. RealSense 하드웨어와 pyrealsense2 설치는 이 단계에 필요하지 않다.

### S10. 평가·TUM·부가 지도 통합

1. PandaSet/KITTI 평가는 기존 helper를 재사용하고 match count·제외 프레임·Sim(3)·참조 정보와 ATE의 한계를 표시한다.
2. TUM 데이터가 확보되면 한 시퀀스부터 RGB timestamp filename과 groundtruth 시간 대응을 검증한다. 임의 frame index를 초로 해석하지 않는다. 공식 groundtruth는 평가에만 쓴다.
3. `evo_ape tum <GT> <EST> -as`를 한 시퀀스에 적용하고 결과·실행환경을 보관한다. 기존 `evals/eval_tum.sh`는 9개 전체를 기대하므로 한 시퀀스 검증에 그대로 실행하지 않는다. `process_logs_tum.py`는 요약기이며 평가 엔진이 아니다.
4. GT가 없으면 ATE N/A. file format 지원과 실제 TUM 평가 완료를 구분한다.
5. BEV는 기존 exporter 재사용. sample/clip·축척 출처, surface vs ground를 명확히 표시한다. 회색 도로 proxy 지지가 없으면 surface_only, 미지 셀 NaN 유지.

완료: 결과 파일이 UI·보고서에서 같은 run ID로 연결된다. 지면 등고선 성공이나 정확도 개선을 근거 없이 주장하지 않는다.

### S11. 통합·브라우저·실패 경로 검증

1. 선택 장면마다 최소 한 실제 실행 자산을 연결한다. 무거운 모델을 view 모드에서 import/다운로드하지 않는다.
2. 한 GPU 추론 작업만 허용하고 UI 상태는 Idle/Preparing/Running/Stopping/Completed/Failed/Blocked로 보여준다. 진행상황은 실제 이벤트 기준이다.
3. 표시점 예산·run 전환·박스 Clear·타임라인을 반복해 핸들과 메모리 누적을 확인한다. 30만 점 화면이 15초 이내 연결되는 것을 목표로 하되 실제 측정값을 남긴다.
4. Browser console/pageerror·WebSocket·주요 버튼·스크린샷을 저장한다. 환경상 브라우저 불가면 그 사실을 별도 기록한다.
5. `pytest` 관련 검사 후 전체 회귀, `uvx ruff check --select E9,F63,F7,F82 ...`, `git diff --check`, `graft build`. 실제 설치 도구가 다르면 대체 명령을 기록한다.

완료: 작은 재생/종료/실패는 자동 검증, 실제 AI 결과·비디오 입력 추론은 사람이 볼 증거로 검증된다. 동일한 비싼 전체 추론을 테스트마다 돌리지 않는다.

### S12. 인수·시연 자료

1. `docs/DEMO_GUIDE.md`: 설치 환경, 명령, 데이터 준비, 실행/정지/복구, 화면 순서, 비디오 준비, 모델별 제약.
2. `docs/DEMO_RESULTS.md`: 실험 조건·수치·PASS/FAIL/BLOCKED·증거 링크·한계. 실험 전에는 결과 칸을 예상 수치로 채우지 않는다.
3. `docs/DEMO_PROGRESS.md`: 완료 단계·남은 작업·중단 후 재시작 위치.
4. `scripts/demo_report.py`로 run manifest와 evidence를 이용해 보고서를 생성한다. 큰 checkpoint/PCD를 git에 넣지 않는다.
5. 구현 모델의 최종 응답은 로컬 실행법, 실제 확인 범위, 미검증 기능, 필요한 입력/권한을 짧게 보고한다. 전체 일곱 기능 PASS와 프로그램 경로 구현 완료를 구분한다.

## 8. 기능별 합격 기준

| ID | 필수 실제 증거 | PASS 조건 | 부족할 때 |
|---|---|---|---|
| F1 밀집 재구성 | RGB/depth/confidence + finite RGB PCD | 같은 frame의 픽셀·깊이·3D 대응, 저장·재열기 | 깊이 미기록 기존 PCD는 부분 지원 |
| F2 카메라 자세 | 프레임 ID·정상 quaternion·궤적·frustum | 누락/중복 정책 명확, 시점 전환, 파일 저장 | GT 없으면 정확도 N/A |
| F3 서브맵 연결 | 서브맵 2개 이상·overlap·실제 edge·변환 | 분리/연결과 해당 근거 화면 확인 | 색상만 나누고 연결 증거 없으면 미통과 |
| F4 루프/최적화 | 재방문 pair, 검증값, 제약, before/after, objective | 실제 루프 수락과 보정 trace 확인 | ATE 개선은 별도 결과; 미개선도 보고 |
| F5 객체 검색 | 실제 PE/SAM3 결과·mask·3D 대응점·OBB | 대표 존재 객체 2개 이상 확인·부재 대조 기록 | 모델 미설치/호환 실패는 BLOCKED |
| F6 비디오 점진 입력 | 실제 비디오 디코딩 프레임·timestamp·새 submap event | 파일 입력→점진 지도→EOF/Stop·재열기, 두 pacing 정책 확인 | RealSense 실증은 이번 범위 제외·NOT_RUN |
| F7 시각화·평가 | 실제 브라우저 검사·PCD/TUM·평가 JSON | 관측가능 UI·저장·정확한 GT 대응 및 평가 | TUM 미실행은 TUM 하위항목 NOT_RUN |

F4의 “루프 수락”, “목적함수 감소”, “정렬 ATE 개선”은 세 개의 서로 다른 결과다. F7도 “파일 저장”, “PandaSet/KITTI 평가”, “실제 TUM 평가”를 나눠 기록한다. 본래 기능과 추가 BEV는 다른 coverage 항목으로 둔다.

## 9. 자원·실패 대응·비용 절감

- 기본 환경: 현재 Apple Silicon / MPS / 64GB 기록을 시작 시 재확인. CPU fallback은 실제 실행 속도를 보고하고 30fps라고 약속하지 않는다.
- 먼저 기존 산출물 캐시→17~33장 smoke→80장→선정 루프 80~200장 순으로 확대. 모델 설치와 추론을 동시에 병렬 실행하지 않는다.
- 한 번의 추론에서 depth·confidence·submap preview·graph snapshot을 함께 저장해 UI 수정 때 재추론하지 않는다. 전체 3GiB PCD는 그대로 두고 preview cache만 생성한다.
- 새로운 full dense 복사본은 필요할 때만 만든다. 저장 전 예상 용량·여유 공간을 점검한다. per-optimize dense snapshot은 금지하고 local preview+transform으로 재생한다.
- 한 설정의 smoke가 10분을 넘으면 진행 로그·메모리·입력 상태를 점검한다. 멈춤이면 원인을 진단하고 같은 명령을 무작정 재시작하지 않는다. 이미 완료한 기존 실행을 임의 종료하지 않는다.
- 루프 검출/보정이 실패하면 동일 오류 수정 2회 또는 정해진 임계값 조정 1회 안에서 진단한다. 해결 안 되는 알고리즘 품질은 결과에 남기고 나머지 기능 구현은 계속한다.
- SAM3/PE가 현재 torch와 충돌하면 별도 환경. MPS 연산 실패는 단일 이미지 CPU 검증 후 지원표에 기록. 가짜 segmentation이나 검증 없는 box로 대체하지 않는다.
- 처리량 목표는 측정한다. input FPS, inference FPS, presentation FPS는 서로 다른 숫자다. 재생 속도를 줄여 계산이 실시간인 것처럼 보이게 하지 않는다.
- 비디오 파일·승인된 checkpoint 접근·데이터 라이선스 등 외부 조건이 필요하면 정확한 요청을 남긴다. 다른 독립 단계를 진행한 뒤 그 조건만 미완료로 보고한다.

## 10. 다음 모델의 최초 행동과 인계 요약

다음 실행자는 짝 문서 `temp_VGGT_SLAM_Prompt.26.10.30.md`의 시작 프롬프트를 따른다. 우선 S00으로 현황을 확인한 뒤 S01부터 작은 기능 단위로 구현한다. 현재 계획 작성자가 실제로 실행한 것은 코드·공식 문서·기존 결과·배포 메타데이터 조회 및 두 계획 문서 작성뿐이다. 새 데모 코드, 새 모델 설치, 새 추론·실험, 새 서버는 시작하지 않았다.

모든 항목을 한 답변에서 성급히 완성하려 하지 말고 지속 가능한 진행 기록을 남긴다. 단계가 바뀔 때 “확인한 사실 / 변경 / 검증 / 다음 단계”를 짧게 사용자에게 알린다. 계획 수립 완료 뒤 모델 변경 시간을 달라는 사용자 요청을 지키며, 본 문서 작성이 끝나면 지금은 멈춘다.
