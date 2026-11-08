# 데모 진행 기록

## S00 — 진단 (2026-10-30)

- 기존 `docs/DEMO_PROGRESS.md` 없음. HEAD `35327ac28b7d193df9ccc39ba6346052bb6f1207`; 기존 사용자 수정 다수: `git status --short`에 표시되는 README, main, solver 등 수정 및 docs/scripts/tests 등의 미추적 파일을 보존했다.
- PandaSet 003 front_camera와 KITTI-360 data_rect, 기존 `docs/PANDASET003_TEST.md`, `docs/KITTI360_0000_RUN.md` 존재. 기존 결과는 수정하지 않았다.
- 디스크 여유 `df -h .`: 185 GiB. macOS arm64, torch 2.3.1, 현재 프로세스에서 MPS 및 CUDA 사용 불가. `sysctl hw.memsize`는 샌드박스에서 거부되어 메모리 미확인. 실제 호스트의 MPS 가용성은 별도 확인 필요.
- cv2/viser 설치, sam3/pyrealsense2/evo 미설치. `~/.cache/torch/hub/checkpoints`에 model.pt 4.7G, dino_salad.ckpt 336M 및 dinov2 checkpoint 존재. 체크포인트 로드 검증은 하지 않았다.
- `lsof -nP -iTCP -sTCP:LISTEN`: 8080, 8081, 8082, 8765, 8766 사용 중. 기존 프로세스를 건드리지 않았다.
- `.venv/bin/python -m pytest -q`: 47 passed, 1 warning, 24.18초. 기존 기준과 일치.

## S01 — 진행 중

- `demo.py`, `vggt_slam/demo/prepare.py`, `tests/test_demo_prepare.py` 추가. doctor 및 추론 없는 이미지 selection/run 생성 구현. 숫자 ID 정렬, 누락 ID 기록, 손상 이미지와 중복 ID 거부, 기존 run 충돌 거부. 원본 timestamp 부재는 null로 표시.
- `.venv/bin/python -m pytest -q tests/test_demo_prepare.py`: 2 passed. 공백 경로, sparse ID, timestamp 부재, 중복·손상·충돌 검사.
- `.venv/bin/python demo.py prepare --config /private/tmp/vggt_demo_s01_config.json`: PandaSet 00~16, `logs/demo_runs/s01_pandaset_17_20261030/selection.json` 및 manifest 생성. 실제 이미지 검증만 수행했으며 모델 추론은 하지 않았다.
- 2026-10-30 후속: `configs/demo/pandaset003_cached.json`, `configs/demo/kitti360_cached.json`과 `prepare`의 `cached_playback` 경로를 추가했다. `.venv/bin/python demo.py prepare --config configs/demo/pandaset003_cached.json` 및 같은 명령의 `kitti360_cached.json`으로 각각 `logs/demo_runs/pandaset003_existing_20261030/manifest.json`, `logs/demo_runs/kitti360_existing_20261030/manifest.json` 생성. 원본 파일의 절대 경로·크기와 read-only 참조를 기록하고 pose 첫 열을 frame ID로 명시했다. 두 run은 각각 8 KiB이며 원본 153 MiB/3.2 GiB PCD를 복사하지 않았다. 기존 결과 평가 JSON은 각각 80개/3598개 대응, 정렬 ATE 0.558m/321.266m를 기록한다. 후자는 전역 정합 실패 사례다.
- `.venv/bin/python -m pytest -q tests/test_demo_prepare.py`: 3 passed. 캐시 원본 보존, 누락 자산 및 run 충돌도 확인했다. manifest에 환경·패키지 버전, 비어 있는 장치/모델 정보 및 기능 상태 사유를 추가했다. 파일 작성 실패 시 `FAILED` 마커를 남긴다.
- 전체 회귀 `.venv/bin/python -m pytest -q`: 50 passed, 1 warning, 23.03초. `git diff --check` 및 `graft build` 성공.
- 후속: 새 run ID를 먼저 예약하고 준비 실패 시 `status.json`에 단계·오류 종류·사유를 기록한다. `vggt_slam/demo/status.py`에 원자적 JSON 쓰기와 단일 작업자 상태 전환을 추가했다. running 전환은 장치와 모델/checkpoint 식별자를 요구한다. 준비된 PandaSet 17장 재검증: `logs/demo_runs/s01_status_pandaset_17_20261030/`의 selection, manifest, status. 이전 run은 변경하지 않았다.
- S01 잔여: 실행기에서 상태 전환을 실제로 호출하고 전체 manifest 계약을 채우는 작업. selection checksum은 파일 내용이 아닌 선택 목록 checksum이다. 기존 run은 이전 형식이므로 status.json이 없을 수 있다. S01 전체 완료로 표시하지 않는다.

## S02 — 기반 구현, 미완료

- `vggt_slam/demo/recording.py`에 CPU 배열 기반 submap 이벤트와 전처리 RGB·float depth·confidence·유효 마스크·intrinsics 저장 기능을 추가했다. 중복 submap/이벤트 파일을 덮어쓰지 않는다. 깊이 단위는 검증되지 않은 상대값이다.
- `.venv/bin/python -m pytest -q tests/test_demo_prepare.py tests/test_demo_recording.py`: 5 passed. 합성 2프레임의 픽셀 대응·비유효 깊이·겹침·이벤트 순서를 검사했다. 이는 실제 모델 실증이 아니다.
- 전체 회귀 `.venv/bin/python -m pytest -q`: 52 passed, 1 warning, 23.24초. `git diff --check` 및 `graft build` 성공.
- 후속: `main.py --demo_run <prepared-run> --headless`로 기존 오프라인 Solver와 recorder 및 실행 상태를 연결했다. selection checksum을 검사하고, 선택된 원본 ID·경로·timestamp 상태를 프레임 메타데이터에 기록한다. 전처리 RGB와 depth는 같은 픽셀 격자이며 원본에서 전처리까지의 정확한 매핑은 아직 기록하지 않는다. depth/confidence PNG 미리보기를 추가했다.
- 실제 실험: 호스트에서 MPS available 확인. `.venv/bin/python -u main.py --headless --device mps --demo_run logs/demo_runs/s02_pandaset17_mps_20261030_01 --submap_size 16 --max_loops 0 --min_disparity 0` 완료. PandaSet 00~16, 1 submap, VGGT 29.21초, 처리 루프 31.33초, 1,941,722점. `logs/demo_runs/s02_pandaset17_mps_20261030_01/manifest.json`, `events.jsonl`, `submaps/0/frames/`, `poses.txt`, `poses_points.pcd`가 증거다. 완료 후 manifest 자산 경로를 보강했다. events 19개(서브맵 1, 프레임 17, 완료 1), 첫 프레임 깊이 294×518, 유효 152,292픽셀 확인. 원본 stdout 파일은 저장하지 못했다. 이 실행은 루프 OFF이며 실제 루프/최적화 비교 증거가 아니다.
- `.venv/bin/python -m pytest -q`: 54 passed, 1 warning. 진입점의 성공·실패 lifecycle은 mock pipeline 테스트이며 실제 실험과 구분한다. `git diff --check`, `graft build` 성공.
- 다음: 원본→전처리 좌표 매핑과 frame/timestamp 보강, 실제 RGB/depth/3D 대응과 저장/재열기 검증을 완료한 뒤 S03 그래프 이벤트로 진행한다. 여러 submap overlap과 예외 종료도 실제 경로에서 추가 확인한다. S02 전체 완료 및 F1 PASS로 아직 표시하지 않는다.
- 후속: VGGT crop 전처리의 실제 리사이즈·세로 crop·배치 padding과 픽셀 중심 좌표변환을 `image_mapping.py`로 기록한다. 서로 다른 종횡비의 실제 전처리 결과와 합성 테스트로 비교했다. `timestamp_file`은 frame ID 인덱스와 명시된 초 단위 유형을 사용하며 단조성을 검증한다.
- 실제 기존 17장 run에 대해 `.venv/bin/python -m scripts.demo_validate_correspondence logs/demo_runs/s02_pandaset17_mps_20261030_01 --output logs/demo_runs/s02_pandaset17_mps_20261030_01/evidence/correspondence_first_frame_v2.json` 실행: 첫 프레임의 confidence 통과 113,252점, 재구성 3D와 PCD 최대 차이 0, 색상 불일치 0, 원본에서 재생성한 RGB 최대 차이 0. PCD 재열기 포함. 현재 전처리 코드와 원본이 당시와 같다는 가정에 따른 사후 검증이며 GT 깊이 정확도는 아니다.
- 새 실제 실험: `logs/demo_runs/s02_pandaset33_mps_20261030_01/`에서 33장, MPS, loops=0, 2 submap, 3,883,444점; 처리 루프 27.22초. `stdout.log`, manifest, event 및 `evidence/overlap_frame_16.json` 기록. 프레임 16이 양쪽 submap에서 같은 원본·timestamp 1557539982.050642·좌표 변환으로 기록되고 두 번째에서 overlap=true다. 연결 그래프의 실제 제약 이벤트나 화면 확인은 아직 없다.
- 전체 회귀 `.venv/bin/python -m pytest -q`: 56 passed, 1 warning, 25.70초. `git diff --check`, `graft build` 성공.
- 다음: S02의 기록 경로와 실제 데이터 검증은 확보했다. S03에서 실제 edge/루프 후보·수락·최적화 전후 homography와 objective를 기록하고, 이후 UI에서 3D 대응 및 연결을 확인한다. F1 전체 PASS 및 F3 PASS는 UI 확인 전 미완료다.

## S03 — 진행 중 (2026-10-31)

- `solver.py`에 선택적 기록기를 연결해 실제 overlap/loop 보조/loop 제약 삽입, 검색 후보와 기하 검증 결과를 각각 기록한다. retrieval 값은 L2 거리이며 작을수록 유사하다. 검증은 기존 match ratio 0.95 비교식을 유지한다. 기록기를 사용하지 않는 기본 경로는 그대로다.
- `vggt_slam/demo/graph_recording.py`에서 최적화 직전·직후 같은 노드 ID의 실제 4×4 homography 및 projection matrix, graph error, factor 수, 소요 시간을 저장한다. 카메라 로컬 점 미리보기는 프레임마다 최대 1,000점과 실제 노드 ID를 보존한다. 전체 PCD의 최적화별 복사본은 만들지 않는다.
- 합성 SL4 그래프 테스트에서 2개 노드의 동일 집합, 실제 행렬 변화 및 목적함수 감소를 확인했다. 이는 실제 루프 실증이 아니다.
- 실제 `logs/demo_runs/s03_pandaset33_mps_20261031_01/` 실행: PandaSet 33장, MPS, loops=0. `events.jsonl`에 노드 16→17의 overlap factor, scale 0.9064096305 기록. 두 번째 최적화 전후 모두 34개 노드와 34개 factor, error 8.6904e-26→8.0116e-26, homography 최대 변화 3.0e-15. 이미 일관된 루프 OFF 그래프의 수치 수준 변화이며 보정이나 ATE 개선 증거가 아니다. `snapshots/2/before.npz`, `after.npz`, `stdout.log` 보존. 이 실행은 미리보기 코드 추가 전에 시작했다.
- 실제 `logs/demo_runs/s03_preview5_mps_20261031_01/` 실행: 5프레임, loops=0. `submaps/0/preview.npz`의 5,000개 유한 camera-local 점과 노드 ID 0~4가 최적화 snapshot의 노드와 일치했다.
- 전체 회귀 `.venv/bin/python -m pytest -q`: 58 passed, 1 warning, 27.81초. `git diff --check` 및 `graft build` 성공.
- 남음: 실제 재방문 loop 후보 이미지·검증값·삽입 제약의 연결된 증거와 전후 변화, 루프 후보/검증 이벤트의 실제 검증, preview를 homography로 재투영하는 UI. S03 완료나 F4 PASS로 표시하지 않는다. 다음은 KITTI-360 재방문 연속 구간과 keyframe 선정 및 loop 실험 또는 S04의 cache viewer 연결이다.
- 2026-10-31 후속: `scripts/demo_select_data.py`로 KITTI 508–1855 연속 1,348장에 기존 광류 선택을 적용. 기준 경로는 사후 진단으로만 사용: 508↔1826 0.324m, 구간 경로 약 939m, 최대 이격 약 283m. 150px 결과 31장은 간격이 커 제외, 90px 결과 167장은 재방문 최단 선택점이 시작에서 약 7.23m. 80px 결과 226장은 목표 200장보다 많지만 선택 재방문 1829가 508에서 약 2.37m, 최대 프레임 간격 29이며 4개 인접 쌍을 시각 검토했다. 근거 `logs/demo_selections/kitti360_508_1855_flow80_20261031_01/selection_report.json`, `contact_sheet.jpg`, `adjacent_pairs.jpg`. 선택점의 전체 겹침을 보증하지는 않는다.
- `frame_ids_file`과 `--use_all_selected_frames`를 추가해 두 비교군에 같은 원본 ID 목록을 두 번째 광류 필터 없이 제공한다. 루프 후보 이미지와 match_id를 저장하고 후보→검증→실제 제약 이벤트 연결을 보강했다. synthetic 테스트와 실제 실험을 구분한다.
- 실제 ON/OFF 완료: `logs/demo_runs/s03_kitti_loop_on_20261031_01/` 및 `s03_kitti_loop_off_20261031_01/`, `--headless --device mps --submap_size 16 --use_all_selected_frames`와 각각 `--max_loops 1`/`0`. 동일 selection 226장, 실제 poses의 프레임 ID도 일치. 각 실행의 `stdout.log`, `events.jsonl`, snapshots, 점군과 poses를 보존했다.
- ON에서 1829↔508, 1855↔541 두 후보가 각각 match ratio 1.0402, 1.0512로 수락되어 실제 SL4 factor가 삽입됐다. 검증값은 확률이 아니다. 원본 첫 쌍 이미지를 대조했고 기준 위치 간격은 각 2.367m, 4.701m. 후보·검증·제약의 match_id, 이미지, 전후 node set 및 행렬은 ON의 `evidence/loop_trace.json`에서 연결된다. 첫 루프 최적화 objective 115.3916→0.1773, 같은 240개 노드 homography 최대 원소 변화 1.3652. objective 감소와 외부 정확도는 별도다.
- `.venv/bin/python -m scripts.evaluate_kitti360 --estimated_poses <run>/poses.txt --reference_poses logs/kitti360_0000_reference/cam0_to_world.txt --output_dir <run>/evaluation`을 두 run에 실행. 동일한 217개 대응 프레임, 누락 기준 프레임 9개 제외, 각 궤적에 별도 전체 구간 Sim(3) 정렬: ON ATE RMSE 9.9486m, OFF 16.1635m, 차이 6.2150m. 이 한 구간에서 ON이 낮았으며 독립 정렬이나 공식 KITTI segment drift는 아니다. 증거 ON의 `evidence/ate_comparison.json`과 양쪽 `evaluation/trajectory_metrics.json`.
- 전체 회귀 `.venv/bin/python -m pytest -q`: 60 passed, 1 warning, 30.64초. 실제 이미지 및 loop trace 검증과 합성 테스트를 구분한다. `git diff --check` 성공.
- 다음: S03 기록·재방문 소량 실험 완료 범위를 바탕으로 S04 cache viewer를 구현하고 실제 브라우저에서 동일 노드의 최적화 전후, 서브맵 및 루프 후보를 확인한다. loop 후보/제약 trace는 검증했지만 통합 UI 검증 전 F4 전체 PASS는 보류한다.

## S04 — 캐시 뷰어 진행 중 (2026-10-31)

- `demo.py view --run <run_dir> --port 8090` 추가. `vggt_slam/demo/cache.py`, `viewer.py`: run 전환, 프레임 타임라인·재생, RGB/상대 깊이, 루프 후보 이미지, 실제 snapshot 단계 및 before/after, 서브맵 색상, 점 예산과 Fit을 제공한다. VGGT/SAM3 import 또는 checkpoint 다운로드 없이 캐시만 읽는다. 좌표는 미검증 reconstruction 단위, frustum은 projective camera의 시각적 분해, 루프 후보 화면은 전체 run 기준임을 명시한다.
- preview는 camera-local 점을 해당 시점 실제 4×4 homography로 재투영한다. 선택 snapshot에 없는 미래 노드는 표시하지 않는다. 첫 루프의 step 14 전후 `render(... budget=50000)` 검사에서 노드 집합 동일, 같은 점 50,000개의 최대 좌표 변화 0.8754 reconstruction units, 이후 노드 제외. 독립 run ON/OFF는 각각 선택한다.
- 기존 KITTI 전체 점군은 `numpy.memmap`으로 212,204,997점을 읽고 30만 점만 전송한다. 캐시가 없는 기존 결과의 깊이·타임라인은 제공 불가로 표시한다. 선택된 프레임이 snapshot에 없으면 안내한다.
- 격리된 실제 Chrome + 소프트웨어 WebGL 검사: `logs/demo_runs/s03_kitti_loop_on_20261031_01/evidence/browser_s04_final/browser.json`, `initial.png`, `after_controls.png`. WebSocket worker connected, JS exception 0, 되감기·재생/정지·끝 이동·점 수 50,000 변경·before/after·Fit·PandaSet run 전환·기존 KITTI run 전환·30만 점 표시 성공. 소프트웨어 WebGL ReadPixels 성능 경고가 있었고, 최초 `--disable-gpu` 시도는 WebGL 컨텍스트 오류로 실패해 별도 `browser_s04_probe/`에 남겼다. 30만 점 연결 시간을 정밀 계측하지 않았다.
- `.venv/bin/python -m pytest -q`: 61 passed, 1 warning. 합성 projective transform 테스트에서 동차 나눗셈과 미래 노드 제외를 검증했다. 실제 viewer module import 시 VGGT/SAM3가 import되지 않음을 확인했다.
- 남음: 이미지별 confidence 표시, 프레임별 frustum 전체 표시·submap/edge 전용 가시화, 루프 단계와 타임라인 동기화, 비교·평가 패널, 반복 조작 메모리/성능 정량 검증. S04 전체 완료나 F7 PASS로 표시하지 않는다. 다음은 이 빠진 시각화 및 테스트를 보강한다.

## 실제 기능 실증 상태

| 기능 | 상태 | 근거 |
|---|---|---|
| F1 RGB/depth/점군 | PASS (targeted) | PandaSet 대응 검증: 113,252 points, RGB/XYZ error 0, 33-frame PCD |
| F2 자세 | PASS (targeted) | KITTI-360 ON/OFF, 217 GT matches, fitted Sim(3) metrics saved |
| F3 서브맵 | PASS (targeted) | PandaSet overlap frame 16; video run graph edge and two submaps |
| F4 루프/최적화 | PASS (targeted) | KITTI-360 two accepted constraints; `loop_trace.json`; ON/OFF ATE 9.949/16.164 m |
| F5 PE/SAM3 검색 | PASS (targeted, CPU) | 같은 live 세션의 car17/tree3/elephant0, 검색 중 캡처·Stop 대기·Clear·snapshot 기반 cache 재열기 확인. 객체 절대 정확도 미평가; car #1/#5 극단값 민감 판정 보류 |
| F6 비디오 점진 입력 | PASS (targeted) | BDD 900프레임·실제 Viser 제어/안전 종료·실제 VFR fixture 및 명시적 timestamp fallback 검사. RealSense 미검증 |
| F7 시각화/평가 | PASS (targeted) | Viser 브라우저 조작·PCD/PTS TUM 저장·실제 TUM xyz 33프레임 evo 평가(0.02369m fitted Sim3). 전체 benchmark 미실행 |

## S04 후속 — 캐시 뷰어 통합 (2026-11-04)

- `CachedRun`이 프레임별 confidence 이미지, 기록된 overlap/loop graph edge, run 안의 trajectory metric JSON을 읽고 표시한다. Loop candidate 선택은 후보 query frame으로 타임라인을 이동한다. 이전에 완료된 KITTI/PandaSet 브라우저 검증을 유지한다.
- 최종 Chrome 검사 `logs/demo_runs/video_20261105T004239_058560000/evidence/browser_video_v2/`: Viser WebSocket worker 연결, frame 0–9, optimization step 2, confidence/RGB/depth 패널, before→after, Fit, point limit, PandaSet run 전환. 브라우저 JS exception 없음. software SwiftShader는 WebGL `ReadPixels` 성능 경고를 기록했다.
- 일반화한 브라우저 검사기는 초기 300k 표시, 사용자 조작 후 50k 표시 모두 성공했다. `browser.json`의 첫 렌더는 8.0초.

## S08–S09 — 비디오 파일 증분 입력 (2026-11-04)

- `VideoFileCamera`를 추가했다. 시작/끝 frame index, `offline`/`realtime` pacing, PTS, 반복 가능한 EOF 예외를 제공한다. `main_realtime.py --camera video_file --video ...`는 EOF/max_frames에서 종료하고 남은 keyframe을 flush한다. 디스플레이 입력은 P/Space pause, N single-step, Q stop을 받는다. `--headless`는 비디오 경로에서만 허용한다.
- 각 비디오 추론은 새 `logs/demo_runs/video_<id>/` manifest/run ID를 만들며 영상 SHA-256, `video_frames.jsonl`, keyframe/drop sidecar, frame별 RGB·depth·confidence, graph snapshots, poses, PCD, video summary를 보존한다. 오래된 run/keyframes를 재사용하거나 덮어쓰지 않는다. view 명령으로 결과를 모델 없이 연다.
- fixture: 기존 PandaSet 실험에서 기록한 RGB 9장을 `/private/tmp/vggt_pandaset_fixture9.mp4`로 재인코딩했다. 실제 카메라 촬영 영상이 아니며 timestamp-aligned GT가 없어 ATE는 N/A다. 최종 run `video_20261105T004239_058560000`: MPS, 9 decoded, 9 selected, 0 backlog drop, 2 submaps(각 5 frame, 1 overlap), 2 optimization snapshots, 1,142,156 PCD points, 9 pose rows. CachedRun은 프레임 asset 10개(중첩 1 포함), graph edge 1개를 읽었다.
- 관련 회귀 10개 통과: 비디오 범위/EOF/realtime pacing/손상 경로/run lifecycle/cache graph edge/evaluation/report/Realsense mock flush/worker error. 이후 전체 회귀·정적 검사를 실행한다.
- 아직 확인 안 된 항목: 30–60초 원본 비디오, 실제 GUI pause/step 조작, backlog 발생/드롭, worker 강제 오류, video 실행 평가 GT 연결. 현재 9-frame `--headless` 실험으로 이 조건들을 PASS 처리하지 않는다.

## S06–S07 및 S10–S12 현재 제약

- `demo.py doctor`: torch 2.3.1, cv2/viser 설치, SAM3/evo 없음. 샌드박스 안 MPS false이지만 승인된 호스트 실행에서 MPS inference는 성공했다. SAM3/PE 모델과 체크포인트의 설치/라이선스 조건을 확인하지 않았으므로 자동 설치하지 않았고, 실제 객체 검색은 BLOCKED다.
- `vggt_slam/demo/object_query.py`를 양쪽 검색 경로와 Viser 검색 UI에 연결했다. 마스크가 depth 격자와 다르면 nearest resize, confidence·유한 점 필터, 부족 점 사유, proper rotation/양수 extent를 적용한다. Query RGB/mask/3D OBB/retrieval evidence를 run에 저장하고 cache viewer에서 다시 열며 live OBB를 Clear한다. 합성 geometry/persistence 및 concurrent Recorder event sequencing 검사 통과; SAM3 absent라 printer/chair/missing-object 실증은 아직 BLOCKED다.
- TUM 데이터 및 `evo`는 현재 확보되지 않았다. PandaSet/KITTI 기존 평가는 개별 보고서로 존재하고, 데모 UI는 run 내부 evaluation JSON을 표시한다. 새 비디오 fixture에는 GT 매핑이 없어 수치 ATE를 만들지 않는다.
- 최종 video run `video_20261105T004239_058560000`: 프레임당 preview cap 50,000, before와 after 각각 300,000 points 렌더. `evidence/browser_video_v2/browser.json`: worker WebSocket connected, JS exceptions 0, rewind/play-pause/end/point-limit/before/after/Fit/PandaSet run switch 모두 true. 첫 렌더 8.0 s (기준 15 s 이내). software SwiftShader `ReadPixels` 경고는 지속.
- `docs/DEMO_GUIDE.md`, `docs/DEMO_RESULTS.md`, `scripts/demo_report.py`를 추가했다. 보고서는 run manifest/evidence를 읽어 생성한다. 전체 회귀 `.venv/bin/python -m pytest -q`: **68 passed**, 1 기존 Dash 경고. `uvx --offline ruff check --select E9,F63,F7,F82 ...`: **All checks passed**. `compileall`과 `git diff --check`도 통과했다.
- 다음 작업은 SAM3/PE 환경과 모델 자산이 제공되면 S06–S07 실제 객체 검증, 원본 30–60초 주행 비디오와 timestamp-aligned GT가 제공되면 S09/S10 평가 확장이다. 현재 판정: F1–F4 targeted PASS, F5 BLOCKED, F6/F7 PARTIAL; 전체 일곱 기능 통합 PASS라고 주장하지 않는다.

## S11/S12 후속 검증 — 2026-11-05 UTC

- 최신 객체 검색 geometry/persistence 및 Recorder 동시 이벤트 변경을 포함한 전체 회귀: `.venv/bin/python -m pytest -q` → **72 passed**, 기존 Dash warning 1개, 23.36초.
- 변경 코드에 `uvx --offline ruff check --select E9,F63,F7,F82 ...` → All checks passed. uv cache 읽기 제한 때문에 호스트 권한으로 실행했다. `compileall`, `git diff --check`, `graft build` 성공.
- 기존 최신 실제 Chrome 증거 `evidence/browser_video_v3/browser.json`을 재검토했다. 첫 렌더 8.003초, WebSocket worker connected, JavaScript exceptions 0, 기록된 모든 interaction true. 이번에는 새 브라우저 실행이나 모델 추론을 수행하지 않았다.
- 검증 요약: `logs/demo_runs/video_20261105T004239_058560000/evidence/verification_20261105.json`. `.venv/bin/python scripts/demo_report.py --force`로 14개 run의 결과 보고서를 재생성했다.
- 실행 서버 확인 정정: 8091은 이 프로젝트의 cached Viser demo다. 8767의 `serve_rgb_object_search.py --run_os car`는 `/Users/hyunjae.kang/2026_HyunJae_Git/26_Study/3dgs/3dgs_maps`에서 실행 중인 별도 프로젝트이며 이 프로젝트의 F5 실증 근거가 아니다. 기존 프로세스는 유지했다.
- doctor 재확인: 기본 .venv torch 2.3.1, SAM3/evo 미설치. F5 실제 검색과 TUM 평가 제약은 그대로다. 다음 단계 S06/S07: 공식 SAM3/PE 요구사항·체크포인트 접근 조건을 확인하고 기본 .venv를 보존한 별도 환경에서 실제 단일 이미지 검색부터 검증한다. 이후 S09 긴 비디오/pacing/GUI 종료 검증을 진행한다. 전체 일곱 기능 PASS는 아직 아니다.

## S06 환경 실증 — SAM3/PE 분리 환경 (2026-11-05)

- 공식 소스를 `third_party/sam3`와 `third_party/perception_models`에 clone했다. SAM3 commit `f1647e8d0c1d280991f4d1b7d974c2704537fe66`; PE commit은 아래 증거 폴더에 기록했다. 기존 SAM3 HF cache에 `sam3.pt`가 있는 것을 확인했으며 가중치를 다시 다운로드하거나 로드하지 않았다.
- `/Users/hyunjae.kang/anaconda3/envs/meta_sam3/bin/python -m venv --system-site-packages .venv-open-set`으로 프로젝트 별도 환경 생성. PyTorch 2.13.0 등 기존 conda 패키지를 읽기 전용으로 재사용하므로 독립 배포 가능한 환경은 아니다. 기본 `.venv`와 conda 환경은 변경하지 않았다. `.venv-open-set/`를 gitignore에 추가했다.
- `.venv-open-set/bin/python -m pip install --no-deps --no-build-isolation -e third_party/sam3` 및 PE 소스 설치 성공. PE의 `core.vision_encoder.pe`, `transforms` import 성공. PE 체크포인트/embedding 추론은 아직 NOT_RUN이다.
- SAM3 import 실험 실패: `model_builder -> sam1_task_predictor -> sam3_tracker_base -> sam3_tracker_utils -> edt -> import triton`, `ModuleNotFoundError: No module named 'triton'`. 단일 이미지 모델 import에 영상 추적 의존성이 연결된다. 실제 이미지 추론은 시작되지 않았다. CUDA 전용 의존성을 가짜 모듈로 대체하지 않았다.
- 증거: `logs/demo_environment/sam3_probe_20261105/`의 `import.log`, `pe_import.log`, `packages.txt`, `source_commit.txt`, `pe_source_commit.txt`.
- `main.py`, `main_realtime.py`의 SAM3 builder와 Processor에 선택된 `device`를 명시했다. 기존 Processor CUDA 기본값 때문에 CPU/MPS 선택이 무시되던 경로를 수정했다. 이는 SAM3 MPS 지원을 보증하지 않는다.
- `.venv/bin/python -m pytest -q tests/test_demo_execution.py tests/test_regressions.py`: **22 passed**, 기존 Dash warning 1개. compileall, git diff --check, graft build 성공. 이전 전체 72-pass 이후 이번 작은 device 수정에는 관련 검사만 실행했다.
- 공식 설치 문서: https://github.com/facebookresearch/sam3#installation (Python >=3.12, PyTorch >=2.7, CUDA GPU 안내 및 HF checkpoint 접근 승인 필요). 실제 clone 메타데이터는 Python >=3.8이므로 문서와 패키지 선언이 다르다. 로컬 checkpoint 존재는 현재 계정의 원격 접근 승인 여부를 증명하지 않는다.
- 현재 F5 BLOCKED: macOS에서 upstream SAM3 import의 Triton 의존성 해결 및 실제 모델 실행이 필요하다. 다음은 upstream CPU/MPS 지원 경로와 안전한 이미지 전용 import 분리를 조사하거나 CUDA 환경에서 동일 checkpoint로 검증하는 것이다. PE는 import까지만 확인했으며 전체 객체 검색 PASS로 간주하지 않는다.

## S06 CPU 이미지 경로 호환성 진단 — 2026-11-05 후속

- `scripts/patch_sam3.py` 추가: `sam3_tracker_utils.py`의 EDT import를 실제 클릭 오차 샘플링 함수 내부로 지연한다. CUDA EDT 알고리즘은 변경하지 않았고 가짜 Triton을 넣지 않았다. 이미지 경로에서 SAM3 builder/Processor import가 성공했다. 영상/대화형 클릭 기능의 CPU 지원은 제공하지 않는다.
- 첫 CPU 실험 `logs/demo_environment/sam3_cpu_smoke_20261105_01/result.json`: 모델 초기화의 position_encoding.py:55가 device="cuda"로 고정돼 실패했다. patch script에 CUDA 없는 경우 CPU 위치 캐시 초기화를 추가했다.
- 두 번째 CPU 실험 `logs/demo_environment/sam3_cpu_smoke_20261105_02/`: 5.26초 뒤 decoder.py:349의 `_get_coords` CUDA 기본 장치로 실패. `result.json`, `stdout.log` 보존. 두 실험 모두 `car`, 기존 video run RGB, cached sam3.pt, CPU, torch 2.13.0 조건이며 마스크 추론에 도달하지 못했다. 체크포인트 텐서 로드 완료도 주장하지 않는다.
- `scripts/demo_sam3_smoke.py` 추가: 로컬 체크포인트만 사용하고 새 output 디렉터리에 RGB/mask/score/box 또는 실패 사유·소요 시간을 저장한다. 이것은 SAM3 단독 검사이며 PE 검색이나 VGGT-SLAM 3D OBB 실증이 아니다.
- 패치의 재실행 불변성, Python syntax, upstream source 변경 시 거부 동작을 임시 파일로 검사해 통과했다. compileall, git diff --check, graft build 성공. 기본 SLAM 코드는 이번에 변경하지 않아 기존 회귀를 반복하지 않았다.
- 계획의 동일 오류 수정 반복 제한에 따라 CUDA 고정을 연속적으로 바꾸는 실험은 두 시도에서 멈췄다. F5는 BLOCKED 유지. 다음 S06 작업: 남은 CUDA 하드코딩 및 cache-device 이동을 함께 조사해 CPU/MPS 지원 범위를 먼저 결정한다. CUDA 실행 환경이 있으면 upstream 경로로 단일 이미지부터 확인할 수 있다. Mac 지원은 아직 검증되지 않았다.
- docs/DEMO_GUIDE.md에 별도 환경의 실제 제약 및 재현 명령을 추가했다. 기존 `.venv`, run 결과와 사용자 데이터는 보존했다.

## S06 CPU SAM3 실제 이미지 추론 성공 — 2026-11-05 후속

- 남은 이미지 모델 CUDA 고정을 조사했다. `scripts/patch_sam3.py`에 decoder 좌표 cache의 CPU 생성, CPU fused MLP의 FP32 linear+ReLU/GELU, geometry box scale의 CPU pin_memory 생략을 추가했다. CUDA 경로는 기존 동작을 유지한다. 패치는 upstream commit에 대한 문자열 guard를 가지며 재실행 불변성을 확인했다.
- 실험 03: model/checkpoint 생성 후 이미지 encoder에서 강제 BF16과 float32 weight 혼용으로 실패(6.83초). 실험 04 CPU BF16 autocast는 native exit 139. FP32 fallback 실험 05는 text prompt의 geometry_encoders.py:649 `pin_memory()`에서 exit 139; faulthandler stack 보존. 04/05는 Python finally도 실행되지 않아 `process_exit.json`을 관찰한 exit status로 별도 기록했다.
- 실험 06 **실제 SAM3 CPU 성공**: `.venv-open-set/bin/python -X faulthandler scripts/demo_sam3_smoke.py --image logs/demo_runs/video_20261105T004239_058560000/submaps/0/frames/0/rgb.png --query car --device cpu --output logs/demo_environment/sam3_cpu_smoke_20261105_06`. 로컬 sam3.pt, torch 2.13.0, CPU FP32/autocast disabled, 10.907초, 마스크 19개, scores 약 0.504–0.960. 실제 RGB와 mask_00을 시각 확인: 거리 왼쪽 주차 차량 영역과 대응한다. 전체 19개 마스크의 품질/정확도를 평가한 것은 아니다.
- 증거: 각 `logs/demo_environment/sam3_cpu_smoke_20261105_03`~`06`의 stdout/result 또는 process_exit. 성공 run에는 frame.png, mask_00~18.png, model boxes/scores의 result.json이 있다.
- CPU fallback의 ReLU/GELU 결과를 표준 linear+activation과 비교하여 일치, FP32와 shape 유지 확인. Ruff E9/F63/F7/F82, compileall, git diff --check, graft build 통과. 기본 SLAM은 변경하지 않아 전체 회귀를 재실행하지 않았다.
- F5는 SAM3 단독 하위항목만 실제 PASS. PE checkpoint/embedding retrieval, 두 종류 객체+부재 대조, depth→3D OBB, 통합 UI 검색/Clear는 아직 미검증이다. 다음 S06/S07: 별도 환경에서 PE embedding을 얻고 같은 RGB/depth 기록과 연결해 실제 3D 박스와 검색 증거를 생성한다. MPS는 builder의 model 이동/일반 Python cache device 이동이 미지원 상태라 CPU 성공을 MPS 성공으로 해석하지 않는다.

## S06/S07 PE→SAM3→기록 지도 3D 박스 실제 연결 — 2026-11-05

- `scripts/demo_pe_retrieve.py` 추가. 실제 PE-Core-L14-336 CPU 모델로 run의 RGB 프레임별 정규화 embedding과 text embedding을 계산하고 cosine ranking/선택 frame event/embedding NPZ를 저장한다. 실제 10개 기록 프레임(중첩 포함)에 `car` query를 적용했다. best_index=4, cosine=0.1783425(확률 아님); overlap 쌍 index 5도 동점이며 argmax가 먼저 나온 index 4를 선택했다.
- PE 모델 최초 다운로드 Xet 방식은 0바이트에서 진행되지 않아 Ctrl-C로 중단(exit 130). `HF_HUB_DISABLE_XET=1` 일반 HTTP 재시도는 timeout resume 후 완료했다. 전체 다운로드+검색 412.69초. 약 2.5GB 가중치는 HF 캐시에 있고 git에 포함하지 않는다. 성공 증거 `logs/demo_environment/pe_car_20261105_02/{result.json,embeddings.npz,stdout.log}`.
- PE 선택 이미지 `submaps/0/frames/4/rgb.png`에 실제 SAM3 CPU FP32 query `car`: 11.480초, 19 masks. 증거 `logs/demo_environment/sam3_pe_car_20261105_01/`의 RGB/masks/model boxes/scores/result/stdout.
- `scripts/demo_cached_object_boxes.py` 추가. PE가 선택한 정확한 RGB와 query가 SAM3 결과와 같은지 확인한다. 같은 submap 전체 confidence의 percentile을 재계산하고, snapshot step 2 after의 node 4 projection inverse로 [u*d,v*d,d,1]을 변환·동차 나눗셈한다. 동일한 계산이 K inverse 후 기록 homography 경로와 최대 오차 0으로 일치했다. 원본 run에는 쓰지 않고 별도 폴더에 저장한다.
- 실제 마스크 19개 중 confidence-filtered point 기준 OBB 17개 생성, 2개는 minimum_points=8 미만으로 제외. 공통 boxes_from_masks/save_query_evidence를 재사용했다. 결과 `logs/demo_environment/pe_sam3_boxes_car_20261105_01/provenance.json`, query 하위 result.json/RGB/mask, geometry_validation.json. 17개 center finite, extent positive, rotation orthonormal/right-handed 검증 통과. 이는 위치/범위 정확도나 실제 객체별 올바른 분리를 증명하지 않는다.
- `.venv/bin/python -m pytest -q tests/test_object_query.py tests/test_demo_cache.py`: 4 passed, 기존 warning 1개. 신규 두 스크립트 Ruff E9/F63/F7/F82 통과, compileall/diff-check/graft build 성공. 기본 SLAM 재추론이나 전체 회귀 반복은 하지 않았다.
- F5의 실제 PE→선택 RGB→SAM3→기록된 깊이/변환→3D OBB 데이터 연결은 확보했다. F5 전체 PASS는 보류: 두 종류의 존재 객체+부재 대조, 3D 박스 시각 검토, 통합 Viser 검색/Clear/reopen은 남았다. 현재 결과는 별도 evidence 폴더이므로 기존 8091 cached viewer 목록에는 자동으로 나타나지 않는다. 다음 S07은 이 검색 결과를 새 derived run으로 등록해 원본 보존 상태로 viewer에서 검토하고, 두 번째 객체 및 부재 대조를 추가한다.

## S07/S11 실제 객체 검색 파생 run 및 브라우저 — 2026-11-05

- 실제 PE+SAM3 CPU 추가 검색: `tree` best_index 6, SAM3 11.000초, mask 8/valid OBB 3; `elephant` best_index 6, 11.257초, mask 0/OBB 0. 실제 원본 RGB와 tree mask_00을 열어 확인했다. 작은/먼 영역의 마스크도 있어 개별 객체 정확도는 미판정이다. elephant는 이 장면의 부재 대조 하나이며 일반적인 false-positive율 검증은 아니다. 결과 `logs/demo_environment/{pe,sam3_pe,pe_sam3_boxes}_{tree,elephant}_20261105_01/` 및 pipeline stdout 보존.
- `scripts/demo_register_queries.py` 추가: source 검증 후 새 derived run에 manifest/events/query evidence를 독립 저장하고 큰 submaps/snapshots/PCD는 symlink 참조. source event는 run_id를 제외하고 파생 초기 이벤트와 동일함을 확인했다. `logs/demo_runs/object_queries_20261105_01/evidence/source_preservation.json`. 원본 데이터 삭제·수정·재추론 없이 car/tree/elephant 검색을 등록했다.
- cached viewer의 `_asset_path` string에 `.parent`를 사용하던 실제 query 이미지 경로 오류 수정. Clear object boxes와 None 선택을 추가했고, 저장 OBB의 snapshot step/phase와 다를 때 박스를 숨긴다. live inference를 동시 실행한 결과가 아니라 post-hoc CPU 검색을 지도에 연결한 결과다.
- 실제 Viser 8092 실행. 격리 Chrome `scripts/demo_browser_check.py --url http://127.0.0.1:8092 --debug-port 9234 --object-query query_1793848788240336000 --output logs/demo_runs/object_queries_20261105_01/evidence/browser_objects_01` 성공. first_render 8.008초, WS worker connected, JS exceptions 0. rewind/play/end/point-limit/before-after/Fit/object-select/17 boxes/Clear/reopen 모두 true. object_boxes.png에서 지도와 빨간 OBB 표시를 확인했다. 박스의 GT 위치·치수 정확도는 검증하지 않았다.
- 관련 pytest 5 passed; Ruff E9/F63/F7/F82, compileall, diff-check, graft build 성공. 전체 pytest 최초 시도는 새 third_party SAM3/PE 자체 테스트 4개 수집 오류로 중단했다. 기본 환경은 외부 모델 테스트 의존성을 포함하지 않는다. 프로젝트 소유 회귀 범위를 `pytest.ini: testpaths = tests`로 명시한 뒤 재실행한다.
- 결과 보고서를 15개 run으로 재생성했다. F5 PARTIAL_PASS: 실제 두 종류 query+부재 대조/3D 연결/브라우저 표시와 Clear/reopen 근거 확보. 정확도·개별 mask/box 품질, live `--run_os` 동시 실행과 MPS는 미검증이다. 다음 S09: 원본/fixture 긴 비디오의 두 pacing, pause/step/stop·backlog/drop·종료 저장 실증. TUM/evo 평가도 남아 있다.
- pytest 범위 설정 후 전체 회귀 최종 결과: `.venv/bin/python -m pytest -q` → **72 passed**, 기존 Dash warning 1개, 24.09초. 외부 SAM3/PE 자체 suite는 별도 환경에서 실행하지 않았으며 PASS로 간주하지 않는다.

## S09 후속 — 긴 fixture·실제 MP4·드롭·PTS 무결성 (2026-11-05)

- main_realtime.py: headless에서도 OpenCV imshow/waitKey를 호출하던 문제 수정. offline video에서는 추론 worker가 끝날 때까지 기다려 선택 keyframe을 보존한다. realtime은 bounded backlog/drop 유지. 대기 후 worker 오류를 검사하고, decoder/UI 예외 종료에서도 worker가 recorder에 쓰는 작업을 마친 후 정리하도록 했다.
- `tests/test_video_pipeline_controls.py`: 모의 느린 worker에서 offline 12프레임 무손실 batch 처리 및 headless imshow 미호출 확인. 모의 OpenCV 키 입력 P→N→Q로 pause/1-step/stop/잔여 flush 확인. 이 검사는 실제 GUI 키 입력 또는 모델 실증이 아니다. 관련 회귀 26 passed. 이후 전체 회귀 74 passed, 기존 Dash warning 1개, 25.98초.
- fixture `logs/demo_fixtures/pandaset33_1fps_20261105/`: 기존 기록 RGB 33장을 1fps MP4로 재인코딩해 33초. `frames.json`은 원본 기록 RGB·frame ID·합성 PTS 연결을 명시. 독립 GT가 없으며 실제 촬영원본 영상이 아니다.
- 실제 MPS offline `video_20261105T045825_786594000`: decoded 33, selected 33, drop 0, submaps 4, pose rows 33, PCD 4,111,823점, capture+flush 23.277초, submap p50/p95 5.008/7.847초.
- 같은 fixture 실제 MPS realtime `video_20261105T050631_178838000`: decoded/selected 33, drop 0, submaps 4, poses 33, PCD 4,111,823점. 두 pacing 모두 EOF 잔여 flush/저장 완료.
- stress fixture `logs/demo_fixtures/pandaset33_30fps_20261105/`: 같은 RGB 33장을 30fps(1.1초)로 공급. 실제 MPS realtime `video_20261105T051501_049520000`: decoded/selected 33, backlog drop 16, processed unique 17, submaps 2, poses 17, PCD 2,055,937점. 드롭된 keyframe은 최종 poses에 포함되지 않았고 shared overlap anchor는 유지됐다. 원속도 처리 성공/30fps SLAM이라고 해석하지 않는다.
- `scripts/demo_validate_video.py` 추가: 선택 frame set이 processed/dropped의 서로 겹치지 않는 합집합인지, pose ID가 source_path의 keyframe ID와 일치하는지, quaternion 단위길이, 실제 PTS 단조성을 검증한다. `estimated_pts.tum` 첫 열은 pose ID 대신 기록 PTS 초다. 세 run 모두 `evidence/video_integrity_01/{validation.json,estimated_pts.tum}` 통과. ATE는 null, evo 미실행.
- 검증 script에 대한 추가 테스트 3 passed: ID와 PTS를 혼동하지 않는 export, 처리/드롭 중복 거부, 비단조 timestamp 거부. 이는 앞선 전체 74개 실행 후 추가됐으며 전체 77개를 다시 실행한 것은 아니다. Ruff E9/F63/F7/F82, compileall, diff-check 통과.
- 로컬 데이터 `/Users/hyunjae.kang/9000_Data/9002_ExpData/videos`에서 기존 실제 MP4들을 발견했다. `640_BDD_test01.mp4`의 fps=29.970, frames 0~899(약30초) 실제 MPS offline `video_20261105T051736_384616000`: decoded 900, selected 8, submaps 1, drop 0, poses 8, PCD 913,751점. 범위 EOF 종료와 PTS 무결성 검증 통과. 촬영원본 여부/라이선스 출처/GT 정확도는 조사하지 않았고 원본 파일은 수정하지 않았다. submap_size8,min_disparity90로는 map 하나여서, 연결 확인용 realtime은 submap_size4,min_disparity45로 별도 실행한다. 설정이 달라 pacing 성능의 공정한 비교군은 아니다.
- 모든 완료 run의 stdout.log를 해당 run으로 복사했다. 실제 GUI pause/step/stop, 강제 worker failure 실증, VFR/잘못된 FPS 및 timestamp fallback은 아직 미완료. F6 전체 PASS로 올리지 않는다.
- BDD realtime 실제 완료 `video_20261105T051812_966691000`: decoded 900, selected 38, drop 3, submaps 9, capture+flush 34.878초. `evidence/video_integrity_01`의 frame partition/pose mapping/PTS TUM export 통과. 실제 기존 MP4에서도 여러 submap 연결과 종료 저장을 확보했다.
- BDD realtime cache 재열기: {'frames_including_overlap': 43, 'optimization_steps': 9, 'displayed_points': 300000, 'full_pcd_points': 4882012, 'graph_edges': 8, 'reopened': True}; `evidence/cached_reopen.json` 저장. 모델 재추론 없이 30만 점 렌더 성공. 실제 새 브라우저 검사는 이번 run에서 수행하지 않았다.

## S10 실제 TUM/evo 소량 평가 — 2026-11-05

- 공식 TUM [download](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/download)의 Freiburg1 xyz archive를 `logs/demo_datasets/tum/freiburg1_xyz.tgz`에 다운로드했다(약427MiB). URL/citation은 download_source.json, archive SHA-256은 selection source.json에 기록했다. 기존 로컬 TUM 데이터는 조사한 Downloads/실험데이터 경로에서 발견되지 않았다.
- 기본 .venv를 보존하고 `.venv-eval`에 evo v1.38.1 설치. evaluation_packages.txt와 `/private/tmp/vggt_evo_install.log` 기록. evo 최초 실행은 ~/.evo 설정 폴더 쓰기가 차단돼 승인된 호스트 실행으로 초기화했다. 사용자 기본 plot 설정(TkAgg)을 바꾸지 않고 evaluator 자체 Agg 그래프를 생성한다.
- `scripts/demo_prepare_tum.py`: rgb.txt에서 GT와 무관하게 균등 33장 선택. 숫자 로컬 frame ID와 원래 RGB timestamp/member 이름/목록 인덱스를 sidecar에 연결한다. depth는 추출/사용하지 않고 groundtruth.txt는 이미지 폴더 밖 평가용으로 분리했다. `logs/demo_selections/tum_xyz33_20261105_01` 및 prepared run `s10_tum_xyz33_20261105_01` 생성. timestamp/GT 분리 synthetic test 통과.
- 실제 `.venv/bin/python -u main.py --headless --device mps --demo_run logs/demo_runs/s10_tum_xyz33_20261105_01 --submap_size 8 --max_loops 0 --use_all_selected_frames` 완료. RGB 33장, submap 4개, 실제 poses/PCD/graph snapshot/RGB/depth/confidence 저장. 일부 MPS bicubic 연산 CPU fallback warning이 있었으며 전체 CPU 실행으로 해석하지 않는다. stdout.log 보존.
- `scripts/demo_evaluate_tum.py`: selection timestamp로 pose 첫 열의 ID를 실제 초로 변환, quaternion/단조 timestamp 검증, evo nearest-time association 20ms 한계 및 `evo_ape tum GT EST -as` 실행. 결과 `evaluation/estimated.tum`, command.json, stdout.log, evo_results.zip, trajectory_metrics.json, ape_errors.png. GT는 추론 완료 후에만 사용했다.
- 실제 평가: estimated 33, GT 3000, matched 33, 제외 0, 실제 최대 timestamp 차이 **0.004662초**. fitted Sim(3) 위치 ATE RMSE **0.023689819m**, median 0.018732416m, max 0.045507382m. 한 시퀀스의 선택 RGB subset이며 전체 TUM benchmark·독립 정렬·절대 위치 정확도 또는 loop 개선 증거가 아니다. loop OFF이다. GT hash와 evo 버전/정렬 한계를 metric JSON에 기록했다. 오차 그래프 시각 확인.
- cache 재열기에서 preview 36,000 points/graph edge 3/metric 33 matches 확인. 실제 8093 viewer 시작 시 N×3 edge colors가 N×2×3 line segments에 맞지 않는 bug를 발견해 viewer에서 colors[:,None,:]로 수정했다. 실제 start는 수정 후 성공했다. 단일 edge에서는 우연히 broadcast돼 이전 검사에서 발견되지 않았던 문제다.
- 첫 browser probe는 검사 스크립트가 평가 경로의 마지막 slash를 frame count로 오해해 ValueError로 중단했다(앱 JS 오류가 아님). `playback index N/M` 정규식과 실제 preview 수가 point budget보다 적은 경우를 처리하도록 검사기를 수정하고 browser_tum_02로 재검증한다. 최초 probe 증거는 덮어쓰지 않았다.
- 관련 tests 17 passed; viewport 수정 후 전체 회귀 **78 passed**, 기존 Dash warning 1개, 24.35초. Evo export의 frame ID→원본 timestamp 변환을 별도 synthetic assertion으로 확인했다. 새 스크립트 Ruff E9/F63/F7/F82, compileall/diff-check 통과. 최신 browser-script 수정 후 정적 검사 및 실제 브라우저 증거를 추가한다.
- 최종 Chrome `evidence/browser_tum_02`: WebSocket worker connected, JavaScript exception 0, rewind/play/end/point-budget/before-after/Fit 모두 true. DOM에 `0.024 m RMSE (33 matched)` 표시 확인. 8093에서 새 TUM demo 실행 유지. 현재 browser check의 first_render_seconds는 고정 8초 대기 후 검사 시각이므로 실제 최초 draw latency의 정밀 측정값은 아니다. 이전 기록의 약8초도 이 측정 한계로 해석한다.
- 최종 관련 Ruff All checks passed, compileall/diff-check/graft build 성공. docs/DEMO_RESULTS.md는 21개 run으로 갱신했다. F7 targeted PASS: 실제 한 TUM subset 평가와 UI 연결 확보. 다음 미완료는 실제 GUI 비디오 Pause/Step/Stop·실패 종료, VFR/PTS fallback, live open-set 동시 실행 및 객체 박스 품질 검토다. 전체 7기능 통합 PASS는 아직 아니다.

## S09/S11 실제 라이브 GUI 제어 및 실패 종료 — 2026-11-05

- `vggt_slam/demo/video_controls.py`: thread-safe command queue로 Viser Pause/Resume·Step·Stop과 decoded/worker 상태, RGB 패널을 추가했다. main_realtime.py는 같은 P/N/Q 처리 경로에서 GUI와 OpenCV 명령을 소비하고 실제 video_control 이벤트를 기록한다. `--video_gui`, `--video_start_paused`, `--no_video_window`, `--viewer_port` 추가. Solver의 optional viewer_port는 기본8080을 유지한다. headless는 기존대로 별도 viewer 없이 동작한다.
- `VideoFileCamera.resume_pacing()` 추가: pause 동안의 벽시계 시간을 따라잡으려는 decode burst를 방지하도록 다음 프레임 기준 deadline을 재설정한다. timestamp 자체는 원본 PTS를 보존한다. synthetic clock test에서 resume 후 다음 간격 0.1초를 확인했다.
- 실제 `.venv/bin/python -u main_realtime.py --camera video_file --video logs/demo_fixtures/pandaset33_1fps_20261105/clip.mp4 --video_pacing realtime --video_gui --video_start_paused --no_video_window --viewer_port 8094 --vis_map --device mps --submap_size 4 --max_loops 0 --min_disparity 0` 실행. `scripts/demo_browser_video_controls.py`의 격리된 실제 Chrome이 initial pause→Step 5회→pause 유지→Resume→Pause→Step 1회→Stop을 실제 버튼으로 수행했다. paused counter 안정성과 single-step 증가 확인, JS exception 0. screenshot에 live map/RGB/Paused/worker busy 확인. OpenCV 창의 OS 키보드 입력 실증은 아니다.
- 성공 run `video_20261105T053815_749770000`: decoded/selected9, drop0, submaps2, poses9, 1,142,156 PCD points, pause toggles2, single_step_frames6, stop_reason=user_stop. `evidence/gui_controls_01` screenshots/browser.json, `evidence/video_integrity_01` partition/PTS/TUM 검증, stdout.log. capture wall 198.71초에는 초기 pause/승인 대기/사용자 조작 대기가 포함돼 속도 비교에 쓰지 않는다. 정상 종료 후8094 live process는 종료됐다.
- `scripts/demo_video_failure_probe.py`: 의도적 실패임을 config와 probe에 표시한다. 초기 direct-script import 경로 오류는 실제 pipeline 실행 전에 발생해 고쳤고, 이후 정상 실험을 별도 output으로 실행했다.
- 실제 decoder fault run `video_20261105T054359_337435000`: 5프레임 첫 MPS worker가 busy인 동안 capture OSError 주입. worker가 실제 submap 기록/최적화를 마친 뒤 main이 실패를 전달했다. camera released, recorder closed, lock released, event file stable, 마지막 run_failed, run_completed0 확인. `logs/demo_environment/video_decoder_failure_20261105_02/probe.json` 및 run의 `evidence/failure_probe_01`, stdout.log.
- 실제 worker fault run `video_20261105T054445_321720000`: 모델을 실제 로드하되 run_predictions에서 의도적으로 raise하여 VGGT forward 전에 worker 실패를 주입했다. 예외 원인 전달, camera/recorder/lock 정리, 안정된 event file, manifest failed/run_failed 확인. 모델의 자연적 실패나 실패한 실제 forward 실험으로 해석하지 않는다. `logs/demo_environment/video_worker_failure_20261105_01/probe.json` 및 run evidence/stdout.
- failure probe는 정상 종료 PCD/pose 저장을 보장하지 않는다. decoder fault에서 기록된 partial RGB/depth/snapshot은 보존된다. 실패 run을 성공으로 바꾸거나 기존 결과를 덮어쓰지 않았다.
- 관련 회귀27 passed. 전체 `.venv/bin/python -m pytest -q`: **79 passed**, 기존 Dash warning1, 23.51초. Ruff E9/F63/F7/F82 All checks passed, compileall/diff-check 통과. 최신 메타데이터 명명 정리는 별도 실제 추론을 반복하지 않았다.
- 다음 미완료: VFR/잘못된 FPS·PTS fallback, live open-set 동시 실행과 객체 OBB 품질. fixed-FPS 비디오의 실제 Viser Pause/Step/Stop 및 두 실패 종료 경로는 targeted PASS다. 원래 RealSense 하드웨어 및 OS OpenCV 키 입력까지 검증했다고 주장하지 않는다.

## S09 timestamp/VFR 완성 범위 — 2026-11-06 UTC (로컬 11-05)

- `VideoFileCamera` realtime deadline을 평균 FPS 대신 프레임별 PTS 차이로 변경했다. 첫 선택 timestamp와 wall time을 anchor로 하고 Resume에서는 다음 timestamp에 다시 anchor한다. 유효 increasing PTS가 있으면 FPS가 0/음수/NaN/Inf여도 pacing 가능하다. invalid FPS는 내부 0으로 정규화해 JSON에 NaN/Infinity가 나오지 않게 한다.
- PTS 누락/음수/반복/역행은 finite positive FPS로 frame_index/FPS 근사, 그 값도 이전 timestamp 이하이면 last_timestamp+1/FPS로 extrapolate한다. 타입을 각각 video_frame_index_over_fps_seconds / video_fps_extrapolated_seconds로 표시한다. 둘 다 불가하면 offline timestamp=None/type=unavailable, realtime은 명시적 ValueError다. 근사값을 관측 PTS로 표시하지 않는다.
- source_timestamp_type/reason/raw PTS를 decoded/keyframe/drop sidecar와 Recorder RGB/depth metadata까지 전달하고 summary에 timestamp_type_counts를 추가했다. TUM validator는 provenance를 보존하며 근사가 섞이면 estimated_approximate.tum, 실제 PTS만 있으면 estimated_pts.tum을 생성한다. timestamp가 없거나 비단조이면 export를 거부한다.
- warmup 첫 capture에서 timestamp 오류가 발생해도 이미 열린 camera를 stop하도록 보강했다. 모의 decoder의 warmup 오류 test에서 release 확인.
- 실제 fixture `logs/demo_fixtures/pandaset_vfr9_20261105`: 기존 PandaSet RGB9장을 ffmpeg concat/VFR로 인코딩. ffprobe PTS 0,.04,.24,.32,.64,.76,.80,1.04,1.20초; frame interval 40–320ms, decoder reported FPS8.333. 촬영원본 영상이 아니며 GT가 없다.
- 실제 OpenCV offline/realtime 디코딩 PTS 모두 ffprobe와 최대 차이0. realtime 전달 누적 시간 약1.205초로 PTS span1.20초와 대응했다. 증거 fixture의 ffprobe_frames.json/decoder_validation.json/source.json. 평균FPS 기준으로 대체하지 않음을 확인했다.
- 실제 MPS realtime `video_20261106T001912_118994000`: decoded/selected9, drop0, submaps2, poses9, PCD1,141,864점. 모든 timestamp type이 video_pts_seconds이며 디코더→sidecar→RGB/depth metadata PTS가 ffprobe와 일치했다. run의 stdout.log, evidence/pts_propagation.json, decoder_validation.json, video_integrity_01/{validation.json,estimated_pts.tum}. ATE N/A.
- cache 재열기·30만 점 render 성공, evidence/cached_reopen.json. 실제 browser/GUI 검사는 이번 VFR run에서 반복하지 않았다.
- synthetic decoder tests: VFR PTS pacing, 0/음수/NaN/Inf FPS+유효 PTS, invalid PTS fallback, backward PTS extrapolation, no-clock offline/realtime 정책, approximate TUM 구분. 실제 인코딩 파일 실증과 분리한다. 전체 회귀 **88 passed**, 기존 Dash warning1, 25.61초. 이후 한 줄 warmup cleanup와 해당 test 추가 후 관련 22 tests는 sandbox의 OpenMP SHM 제한으로 2개 git 자식 프로세스가 SIGABRT; 승인된 host 재실행은 **22 passed**, 2.87초. 최종 전체89개를 다시 실행한 것은 아니다.
- Ruff E9/F63/F7/F82 All checks passed, compileall/diff-check 통과. 작은 유효 VFR fixture와 명시적 fallback 경로까지 targeted PASS이며 모든 컨테이너/codec/10초 초과 timestamp gap 검증은 아니다.
- 다음은 F5 live open-set 동시 실행: 현재 실제 PE→SAM3→cached 3D OBB 및 cached viewer는 검증됐지만, 별도 CPU 환경에서 live `--run_os` 전체 의존성/검색/Stop·Clear를 연결해야 한다. 개별 mask/OBB 품질도 여전히 별도 검토 대상이다.

## S06/S07/S11 live --run_os 통합 실증 — 2026-11-06 UTC

- `.venv-open-set`의 torch2.13/torchvision0.28/numpy1.26.4를 먼저 import하고 base `.venv`의 site-packages 및 editable SLAM dependencies를 read-only로 노출하는 `scripts/demo_live_open_set.py` 추가. GTSAM SL4/Open3D/Viser/cv2/기존 Solver import 확인. pip install이나 기본 .venv upgrade 없이 캐시된 PE/SAM3/VGGT를 함께 로드했다. 실제 package 경로는 run의 open_set_runtime.json. 같은 Python3.11 로컬 환경 조합이며 독립 배포환경/다른 OS ABI 호환을 증명하지 않는다.
- 실제 CPU 명령: `HF_HUB_OFFLINE=1 .venv-open-set/bin/python -u scripts/demo_live_open_set.py --run_os --camera video_file --video logs/demo_fixtures/pandaset33_1fps_20261105/clip.mp4 --video_gui --video_start_paused --no_video_window --viewer_port 8095 --vis_map --submap_size 4 --max_loops 0 --min_disparity 0`. pacing은 default **offline**이다. 최신 torch2.13 CPU에서 VGGT forward 및 실제 PE/SAM3 검색이 성공했다. GPU/MPS/CUDA 조합이나 실시간 처리량으로 해석하지 않는다.
- main_realtime.py의 PE eval mode 적용. video GUI 종료 후 terminal input loop를 생략해 GUI Stop이 EOFError/입력 대기로 끝나지 않게 했다. video 종료 시 query_stop_event로 새 검색을 거부하고 solver worker 및 data_lock을 기다려 진행 중 검색의 mask/box/event 기록 후 recorder를 닫는다. Viewer Search는 실행 중 disabled, Clear도 같은 data_lock으로 직렬화한다.
- 실제 격리 Chrome `scripts/demo_browser_video_controls.py --url http://127.0.0.1:8095 --debug-port 9237 --object-search --output logs/demo_environment/live_open_set_gui_20261105_01`: Step5→첫 지도→car Search 중 Resume/캡처 진행→Pause→car 결과/Clear→tree Search/Clear→elephant Search 중 Stop 수행. 실제 car=17/tree=3 3D boxes, elephant=0. JS exception0. tree query RGB와 valid mask_01을 시각 확인해 오른쪽 가까운 수관과 대응함을 확인했다. 모든 mask의 정확도/3D 치수를 정량 평가한 것은 아니다.
- 실제 run `video_20261106T011557_281290000`: decoded/selected13, drop0, submaps3, poses13, PCD1,713,248점. VGGT와 검색이 같은 process에서 실행됐다. 첫 검색 중 캡처와 다음 submap forward가 진행됐고 graph 갱신은 data_lock으로 직렬화됐다.
- Stop seq38 → elephant query result seq39 → run_completed seq40, manifest completed. Stop 당시 진행 중 검색 결과가 먼저 저장된 후 정상 종료한 것을 event 순서로 확인. 각 query에는 선택 frame/retrieval score/RGB/masks/valid point count/OBB 또는 제외 사유가 있다. stdout.log, evidence/live_query_validation.json, browser_live_queries_01/screenshots/browser.json, video_integrity_01/PTS TUM 및 open_set_runtime.json 보존. 예상하지 않은 모델·검색 예외는 없었다.
- 새 query evidence는 최신 completed snapshot에 묶는다. 기존 실제 query 파일은 수정하지 않고 CachedRun이 query result 앞의 optimization_finished에서 snapshot을 추론한다(car step1/tree step2/elephant step3). Cached viewer에서 query 선택 시 해당 step/phase/frame으로 이동하고 기본 None으로 전체지도를 연다. snapshots와 다른 상태에서 박스를 잘못 표시하지 않는다.
- 라이브 세션 종료 후 같은8095를 cached viewer로 실행 유지. 실제 Chrome 재열기 `evidence/browser_cached_queries_01`: worker WS connected/JS exception0, rewind/play/point limit/before-after/Fit 및 car17 box/선택/Clear/reopen 모두 true. 이 서비스는 현재 cached 결과이며 모델 추론 중이 아니다.
- 관련 회귀8개 및 snapshot/cache/object query 관련5개 통과. 최종 전체 `.venv/bin/python -m pytest -q`: **89 passed**, 기존 Dash warning1, 27.10초. Ruff E9/F63/F7/F82 All checks passed, compileall/diff-check 통과.
- F5를 CPU 지원 경로의 targeted PASS로 올릴 실제 모델→검색→mask→depth/3D→box→live/cached UI→Clear/Stop 근거를 확보했다. F1~F7의 선택된 경로에 실제 증거가 있으며, 전체 환경/codec/객체 정확도/실시간 처리량/RealSense 하드웨어까지 PASS라고 주장하지 않는다. 다음은 인수 자료의 증거·실행법 최종 정리와 남은 품질/재현성 한계 검토다.

## 최종 인수 검토 1·2 — 변경분/증거 대조 및 객체 박스 품질 (2026-11-06 UTC)

- 사용자 요청 범위 1(변경분 최종 검토), 2(객체 박스 품질 점검)를 수행했다. `docs/DEMO_ACCEPTANCE_REVIEW.md`에 검토 범위·수정 결함·기능별 근거·남은 품질 판정을 정리했다. 기존 docs/CODE_REVIEW.md의 2026-10-30 기록은 보존하고 최신 검토 링크만 추가했다. 환경 재현성 작업/임의 commit은 수행하지 않았다.
- 발견/수정: (1) 점 수가 충분한 퇴화 cloud에서도 generic PCA helper가 양수 extent를 만들어 객체 box로 통과하던 경로를 rank<3에서 제외, (2) 제외된 mask도 저장, (3) optional scores=None의 float(None) 오류 해결, (4) camera.stop 예외에도 worker/query 대기·로그 정리가 실행되도록 nested finally. 실제 production OBB 생성 호출은 공통 mask helper 하나임을 exhaustive graft 조회로 확인했다.
- rank0/1/2 제외·mask persistence·score 생략 및 camera release 오류의 worker drain을 회귀로 검증했다. 모델의 자연적 오류 또는 실장치 release 오류로 주장하지 않고 의도적 모의 입력으로 분리했다.
- live run `video_20261106T011557_281290000`의 정확한 car/tree 선택 RGB 두 장에 SAM3만 실제 CPU 재실행했다. 기존 VGGT/PE 전체 추론, 원본 query/box/PCD는 재작성하지 않았다. `logs/demo_environment/object_quality_review_20261106_01/replay/{car,tree}`에 raw masks/scores/model boxes/result/log 보존.
- `scripts/demo_audit_object_quality.py` 추가. query 당시 snapshot+depth+confidence로 지지점을 재구성하고 새 geometry guard 적용. car19 masks→17 valid/2 zero-support, tree8→3 valid/4 zero-support+1 six-point support. 유효20개 모두 rank3, 기존 저장 mask와 재실행 mask 모두 byte-identical, 기존 OBB에 복원 지지점 각100% 포함. 원본 box와 데이터 대응의 일관성 검사이며 독립 정확도는 아니다.
- contact sheet를 시각 검토했다. 차량/수관 영역과 source RGB가 대응하며, 먼 물체와 occluded/cropped 물체에는 관측 한계가 있다. car #1(화면 밖 일부가 잘림)·#5(pickup)는 극단값으로 box가 크게 확장된다. saved OBB volume / 각 PCA축의2–98% support-envelope volume은 각각75.52/25.26. 3D scatter/box 그림에서 소수의 긴 꼬리를 확인했다. 이 비율은 GT 부피 오차나 보정된 confidence가 아니고 ratio>10은 리뷰 휴리스틱이다. 자동 trimming으로 원래 결과를 교체하거나 두 box를 정확도 PASS로 바꾸지 않았다.
- 최신 수치·mask contact sheet·두3D진단: `logs/demo_environment/object_quality_review_20261106_01/audit_v2`, 동일한 run의 `evidence/quality_review_01`. final_review.json에는 기준 HEAD/주요 코드SHA-256/검증/판정을 저장했다. audit_v1 중간 결과도 보존했다.
- 최종 전체 pytest: **94 passed**, 기존 Dash warning1, 23.09초. 프로젝트 소유 main/scripts/tests/vggt_slam 전체 Ruff E9/F63/F7/F82 All checks passed. compileall/diff-check/graft build 통과. 기존 .DS_Store/TerraScene 및 사용자 데이터는 변경하지 않았다.
- 판정: 선택된 지원 경로의 기능 인수 근거와 object geometry 일관성은 확보. 객체의 절대 위치·치수 정확도는 미평가이며 두 차량 box는 별도 검토 필요. 현재 CPU local environment composition은 다른 머신 단독 재현성을 보장하지 않는다. 전체 환경/실시간 처리량/RealSense 하드웨어까지 일괄 PASS라는 결론은 아니다.

## YouTube 90초 주행 영상 테스트 — 2026-11-06 UTC, 실행 기록

- 사용자 지정 URL `https://www.youtube.com/watch?v=2t1i5LYoZXo` 공개 영상 확인. 제목 `KOREA DRIVE | Highway Driving Ambience 4K 2021 중부내륙고속도로 주행영상 백색소음 ASMR`, uploader Godokhan Seoul Drive, 원본3597초. 재생목록은 다운로드하지 않고 해당 영상 첫0~90초만 yt-dlp로 받았다. yt-dlp는 별도 .venv-eval에 설치해 기본 SLAM 환경을 보존했다. JS runtime 부재 warning은 있었지만 metadata/section download는 성공했다.
- 입력 `logs/demo_inputs/youtube_2t1i5LYoZXo_90s_20261106/clip.mp4`: 영상 전용 re-encoded H264 MP4, 1280×720,30fps,2700frames,90.0초,약43MiB. 원본 촬영파일/독립 GT는 아니다. source.json에 URL/범위/출처/포맷/SHA256, ffprobe.json과 download.log/info JSON을 보존했다.
- 초기검은화면→fade를 sample로 확인해 SLAM에서는 첫30frames(1초) 제외. 5/10/30/60/85초 sample을 기록했다. 다운로드파일은90초 그대로 보존한다.
- smoke 실제 MPS `video_20261106T064204_758372000`: start30/max_frames300(약1~11초), offline,submap_size8,max_loops0,min_disparity120. decoded300/selected4/submaps1/drop0/poses4/PCD358,300점. 정상 종료 및 frame partition/PTS/quaternion/TUM-format 무결성 통과. ATE는 N/A. keyframe PTS1.0,1.267,1.4,10.167초로 최대간격8.77초여서 연결 입력이 성기다고 판단했다.
- 한 번의 threshold 조정45px를 실제 영상 전체에 read-only flow로 검사: sourceframes30~2699,decoded2670/selected474,max gap1.6초,median gap0.133초. source의 selection_flow45.json 보존. GT로 프레임을 선택하거나 성능 수치를 고른 것이 아니다.
- 전체실행 `video_20261106T064802_616910000`: original1280×720 input,start30,offline,MPS,submap_size8,max_loops0,min_disparity45로 진행 중. 드롭 없이 처리하며 수 분이 걸릴 수 있다. 아직 완료/PASS/기하 정확도 결과를 기록하지 않는다. 전체90초의 실시간 처리량 또는 loop closure 실증이 아니다.

## YouTube 90초 테스트 최종 결과 — 2026-11-06 UTC

- `video_20261106T064802_616910000` 완료. 다운로드 clip90초 중 초기fade1초 제외, decoded2670/selected474/processed474/poses474/drop0,60submaps/59edges, RGB-depth assets533(중첩59포함), PCD43,058,292점/688,932,853bytes. 사전 flow45 선택 목록과 실제 목록이 정확히 일치했다.
- 실제 MPS/offline capture+worker flush298.34초, 모델준비/최종저장 포함313.86초. submap p50/p95 4.94/5.15초. 원속도30fps 실시간 추론으로 해석하지 않는다. Loop OFF이며 새 영상의 재방문/객체 검색 검사는 하지 않았다.
- `evidence/video_integrity_01`: selected=processed+dropped partition, pose ID/원본PTS/quaternion 검사 통과, estimated_pts.tum 저장. source PTS는1.0~89.967초 구간이며 independent GT가 없어 ATE N/A다.
- PCD43,058,292점 전부 finite XYZ, header/size 읽기 통과. evidence/pointcloud_integrity.json. cache load1.09초/render5.08초, displayed300k points, evidence/cached_reopen.json. 이 값은 browser first draw/inference timing이 아니다.
- 완료된 캐시 뷰어8097 실행 유지. 실제 Chrome `evidence/browser_youtube_01`: worker WS connected/JS exception0, rewind/play/end+visible/point limit+visible/before-after/Fit 모두 true. initial.png에서 도로 점군과 연결된 경로 표시를 확인했다. 지도 위치·거리·누적 drift 정확도는 GT 없이 판정하지 않는다.
- `scripts/demo_browser_check.py`에 큰 데이터 render를 위한 실제 상태 대기 추가. 고정2초 후 점 수 판정 대신 end-frame/point-budget 반영을 최대30초 기다리며, 기존 first_render_seconds가 고정8초 후 검사 시각임을 timing_method로 명시했다. 실제 Chrome 검증·Ruff E9/F63/F7/F82·compileall/diff-check 통과. 이번 작업은 새 입력 실험이므로 기존94개 전체 회귀를 반복하지 않았다.
- `docs/YOUTUBE_90S_TEST.md`에 출처·명령·수치·증거·뷰어/파일 링크·한계를 정리했다. yt-dlp는 별도 평가 환경에만 추가했고 기존 데이터/결과는 보존했다. 다음은 새 영상 지도 연속성의 추가 검토 또는 이 영상에서의 객체 검색이며, 이번 수치만으로 정확도 PASS를 주장하지 않는다.


## 지도 캐시 재생·정지 및 상태 표시 수정 — 2026-11-06 UTC

- 사용자 보고 재현: 캐시가 마지막 프레임에서 열리므로 기존 Play가 다음 tick에서 즉시 종료됐다. 상태 표시가 없고, slider callback과 playback loop가 중복 render를 요청했으며, 30만 점 표시에도 전체 preview를 변환해 큰 지도에서 반응이 느렸다.
- 끝에서 Play 시 처음부터 재생, 명시적인 **Pause playback** 버튼과 **재생 중 / 정지 / 재생 완료** 상태 표시 추가. 중복 render signature를 생략하고 진행 중 render가 끝난 뒤 다음 프레임으로 이동한다.
- CachedRun은 node별 preview slice를 미리 인덱싱하고 표시 예산에 맞춰 샘플링한 뒤 좌표를 변환한다. 카메라·궤적·edge는 점 수 제한과 독립적으로 보존한다. 같은 YouTube 지도 30만 점 server render 준비 시간은 기존 약5.083초에서 약0.074초로 감소했다. 브라우저 FPS나 추론 속도 측정은 아니다. 원본 PCD/preview/모델 결과는 수정하지 않았다.
- 기존 주소 **http://localhost:8097** 에 수정본 실행 유지. 페이지 새로고침 필요. 실제 Chrome 최종 검증 evidence/browser_playback_fix_02/browser.json: 끝에서 재시작, 프레임 증가, Pause 후3초 프레임 유지, 재개 후 증가, 상태 표시 모두 true. rewind/end/point limit/before-after/Fit도 true, JavaScript exceptions0. playback_paused.png 및 initial/after_controls.png 보존. evidence 경로는 logs/demo_runs/video_20261106T064802_616910000/ 아래다.
- 전체 회귀 **94 passed**, 기존 Dash warning1,23.16초. 점 예산1에서도 projective 좌표와 전체 궤적/edge가 유지되는 회귀 assertion 추가. Ruff E9/F63/F7/F82 통과.


## 지도 점 크기 조절 — 2026-11-06 UTC

- 캐시 지도 뷰어에 **Point size (점 크기 배율)** slider 추가:0.1~10배,0.1단위,기본1배. 기존 지도 크기 기반 기본값에 배율을 곱한다. slider는 point-cloud handle의 point_size만 갱신하므로 좌표 재계산/점군 재전송/원본 결과 변경 없이 동작한다. 프레임·run 전환 후에도 선택 배율을 적용한다.
- 기존8097 서버에 적용. 실제 Chrome evidence/browser_point_size_01:3배 입력/표시/1배 복원, 기존 재생·정지·재개/끝에서 재시작/point limit/before-after/Fit 모두 true, JS exceptions0. point_size_3x.png 보존. evidence는 logs/demo_runs/video_20261106T064802_616910000/ 아래.
- 브라우저 검사에서 새 numeric slider 추가에 맞춰 point-limit 입력 선택 보정. compileall, Ruff E9/F63/F7/F82, git diff --check 통과. 이번 변경에는 추가 단위 테스트를 만들지 않고 실제 UI 상호작용으로 검증했다.


## Map Studio — 하늘 제거·BEV·검색·UI 개선, 2026-11-06 UTC

- 사용자 보고 원인 확인: 현재 YouTube run은 하늘 semantic mask 없이 depth confidence만 적용됐고 `--run_os` 미사용으로 객체 검색 event도 없었다. 빈 목록을 결과 누락으로 오해하지 않게 실제 입력/실행/결과 상태를 추가했다. 원본 영상·PCD·preview·event/manifest는 보존한다.
- **하늘 PASS(현재 캐시 표시 경로)**: VGGT 공식 skyseg ONNX를 logs/demo_models/skyseg.onnx에 다운로드. 기본 tensor 환경 변경/ONNX runtime 설치 없이 기존 OpenCV DNN CPU로 실행. scripts/demo_prepare_sky.py는 533개 프레임/474개 고유 RGB에서 실제 모델을 실행하고 별도 evidence/sky_20261106_01/에 확률 이미지와 preview score를 저장했다.78.96초,26,649,381점 전부 기록된 P@H로 올바른 RGB grid에 투영. threshold32+경계2px에서3,378,220점 제거. Hide sky ON/OFF와 threshold 조절 제공. view 시작 시 모델 추론/다운로드 없음. 원본 전체 PCD에는 적용하지 않는다. 새 run의 하늘은 별도 prepare 후 재열기 필요하며 live 추론 자체에 sky model을 상시 실행한 것은 아니다.
- 하늘 RGB/마스크 3구간 시각 검토 evidence/sky_20261106_01/visual_review.png. 하늘/구름 제거를 확인했고, 먼 산·가느다란 전선·나뭇가지 일부가 함께 제거되는 한계도 확인. IoU GT 없음. 완벽한 segmentation/정확도 PASS로 해석하지 않는다.
- **BEV PASS(캐시 및 실제 비디오 점진 입력)**: vggt_slam/demo/bev.py의 제한된 RGB raster를 두 viewer에서 공유. 현재 visible points/카메라 궤적만 투영하며 미관측 셀은 어둡게 유지, 주황 경로/청록 현재 위치. XZ/XY/YZ 선택(캐시). 기본 XZ는 초기 카메라 좌표의 상대 평면. ground/metric occupancy가 아니다. 기존 exporter는 전체 자료 정적 분석용으로 보존하고, UI는 프레임마다 작게 갱신하는 별도 raster helper를 사용한다.
- 기존 video 입력 명령에서 submap_size4,disparity0,video GUI/start_paused,no_video_window,MPS,max_loops0,port8099로 fixture 소량 실행. 실제 Chrome scripts/demo_browser_video_controls.py --verify-bev, logs/demo_environment/live_bev_20261106_01/:5회 Step 후 첫BEV, Resume/Pause/Step 후3개 서브맵 BEV 증가, Stop 모두 true, JS 예외0. 새 run video_20261106T173655_057395000는14decoded/selected,4submaps(Stop flush 포함),drop0,PCD1,941,682점 completed. 실제 지도 생성과 함께 BEV가 증가했으며 원속도 실시간 추론 FPS 주장은 하지 않는다.
- **검색 PASS(별도 CPU worker)**: scripts/demo_search_cached.py가 .venv-open-set의 실제 PE/SAM3를 실행, depth confidence와 projective snapshot을 사용해 OBB 계산. UI에 Query/Search/진행/실패/유효박스0 및 저장된 결과의 사람 읽기 쉬운 label 추가. 결과는 원래 events를 변경하지 않고 evidence/query_jobs/<unique_id>/에 저장, 재시작 시 다시 발견. 입력 영상 전체474개 중 최대48개 time-uniform frame의 최고 PE score RGB 한 장을 분할한다. 전수 탐지/추적 아님.
- 실제 car16프레임 검색:유효2개,tree48프레임:유효4개. car48프레임은 다른 RGB를 선택해유효0개(실제 결과 보존). 잘된 결과만 남기지 않았다. 검색 마스크 overlay 구현 중 read-only PIL 배열 오류가 최종1차 Chrome 검사에서 발견돼 .copy()로 수정; 검색 완료 상태는 실제 UI 결과 반영 후 표시하도록 순서도 수정했다. 실패 증거 browser_studio_final_01 보존.
- **UI PASS**: dark/cyan Map Studio, 고정 사이드바와 지도/검색/분석 탭, 공통 타임라인/재생상태, 접히는 하늘 근거, BEV, RGB/마스크 및 분석 분리. 기존 지도8097에 적용. 브라우저1440×1000에서 시각 확인. 사용자 새로고침 필요.
- 최종 실제 Chrome evidence/browser_studio_final_02/browser.json:재생재시작/정지3초유지/재개/점수/크기/하늘ON-OFF및상태/BEV표시/탭/최적화전후/Fit/실제tree검색완료/마스크결과표시/저장car2박스선택/Clear/재열기 전부 true, JS 예외0. search_result.png 및 object_boxes.png 확인. 서버8097은 최종 코드로 실행 유지.
- 성능 evidence/map_studio_validation.json:30만점 하늘필터 포함 render 준비0.0915초,BEV0.0320초,10,843관측셀/533궤적점. 단일 서버 측 측정이며 browser FPS/추론 성능 아님. evidence/bev_full_sky_filtered.png 보존.
- 관련 회귀5개 통과 후 전체 **98 passed**, 기존Dash warning1,25.24초. 하늘 픽셀/경계/무효투영,projective 변환,all-sky에서도 카메라·edge 보존,BEV미관측/현재위치/빈지도 검사. 최종 검색 overlay 수정은 실제 브라우저에서 재검증. Ruff E9/F63/F7/F82·compileall·git diff --check 통과. docs/MAP_STUDIO.md에 사용법/prepare명령/증거/한계 정리.
- 남은 품질 작업:하늘 GT/경계 IoU,중력/지면 보정 BEV 및 미터 축척,새 입력의 live sky filtering,전수 프레임 검색/여러 후보 재검증은 별도다. 현재 요청의 표시/입력/점진 BEV/UI 경로를 구현·검증했으며 이러한 정확도를 주장하지 않는다.

- 추가 UI 마감:검색 결과 선택 시 현재 지도 범위에 자동 Fit,새 검색 완료 후 상단 검색 개수 즉시 갱신. evidence/browser_studio_focus_01은 추가 모델 추론 없이 저장된 car2박스 선택/Clear/재열기와 타임라인·점크기·하늘 비교·BEV·탭을 전부 재확인(true),JS 예외0. Ruff/compileall/diff-check 재통과,graft build 갱신 완료.


## 메인 RGB·BEV 고정 및 RGB 카메라 Default/Reset, 자동차 누락 개선 — 2026-11-06 UTC

- 요청:왼쪽 메인에 RGB·BEV,재생 RGB와 같은 기본 카메라/Reset,자동차가 있는데없다는 검색 개선. 기존 데이터·PCD·모델·검색 실패 증거 보존,임의commit 없음.
- **레이아웃 PASS**:vggt_slam/demo/main_panel.py + web/studio.html의 로컬 main 화면에 위3D/아래RGB·BEV 고정. public8097과 내부빈포트 Viser를 연결하고,컨트롤은 iframe에 유지한다. 기존 Viser패키지/프런트빌드는 변경하지 않았다. 한 snapshot의 RGB/BEV/3D raster 및원본frame ID/PTS를 버전으로 묶고최근4개만보관. sidebar를간소화해탭이앞에보이게정리했다.
- **RGB 카메라 PASS**:camera_view.py는 실제기록P로 점군을 z-buffer 투영해skew/principalpoint를포함한다. 후반frame의decomposedK는centeredpinhole과크게달라단순Viserpose/FOV만으로RGB와동일한픽셀시점을주장하지않는다. 기본메인은전체P의calibrated point raster이며 RGB복사가아니다. 자유3D는기존Viserorbit,Reset은현재RGB시점복귀(프레임/run결과초기화아님). underlyingcamera위치/방향/FOV도RQ로맞춘다. 현재프레임localpreview최대50k를정확한H로변환해우선배치하고나머지지도샘플로예산을채워현재RGB시점에서성기게보이는문제개선. 총예산유지.
- camera_preview회귀는projectiveH를rigid로대체하지않고하늘필터도공유함을확인. camera unit은회전pose축/카메라중심,skew와lens shift가있는pixel대응,occlusion에서nearest우선,뒤쪽점제외/빈점군을검증.
- **자동차 원인 확인**:이전48샘플 PE best원본frame806은SAM3마스크0으로끝났고,실제car가보이는다른frame이있어도검사하지않았다. 첫프레임0검출을전체영상의부재로오해할수있었다. 기존16샘플run786은2valid였으나특정잘된frame을하드코딩하지않았다.
- **검색 개선 PASS**:search_policy.py와demo_search_cached.py는현재RGB먼저,이후PE상위5후보를중복원본ID없이검사하고유효3D발견시종료. 자동차/차/승용차를car에명시적으로매핑. 각실패/성공시도의RGB·mask·점수·validpoint/퇴화사유·OBB를별도보존. UI는2D개수/유효3D개수/검사후보범위를구분하며2Dmask있으나깊이부족을없다고표시하지않는다. 이전0결과는단일프레임구방식임을안내.
- 실제새CPUcar_retry_20261106_01:48sample,best806마스크0→PE2순위1984마스크3/유효3D1,47.85초. result.search.attempts에두시도와각result경로보존. 이것은best가실패한경우다음후보로회복하는실제모델증거이며전수탐지성공/정확도GT주장은아니다.
- 최종실제UI검색 evidence/browser_main_rgb_final_01:현재원본2696부터검사,806후보후1984에서3mask/유효3D1,총3후보. search_job search_1793992423750912000,결과query_1793992483044821000. 검색중메인RGB/BEV도표시하고완료후선택프레임으로이동. 모델을구경만하는view시작에서는로드/다운로드하지않고Search액션의분리CPUworker에서만실행한다.
- 실제Chrome browser_main_rgb_01 및 browser_main_rgb_final_01:메인RGB/BEV와defaultcamera,자유뷰/Reset,재생중프레임동기화,재생재시작/Pause3초유지/Resume,점수/크기/하늘ON-OFF/탭/최적화/Fit,최종실제car검색/결과표시모두true,JS예외0. 현재프레임우선표시후3Droad/표지판픽셀위치를RGB와시각확인. browsercheck는rootMainPanel과iframe컨트롤을모두검사하도록수정.
- 전체회귀 **103 passed**,기존Dash warning1,22.90초. Ruff E9/F63/F7/F82 통과. 초기compile중GUI문구의따옴표오류는실행서버변경전에수정하고compile재통과. docs/MAP_STUDIO.md 최신동작/실험/한계갱신.

- 최종화면재검사 evidence/browser_main_rgb_ready_01:추가모델추론없이저장된car1개선택→메인Reset→RGB카메라시점에서박스표시→Clear→재열기까지전부true,JS예외0. initial.png/object_boxes.png에서고정RGB·BEV와현재RGB시점의3D점군/빨간박스를시각확인. 현재8097에최종서버유지.


## 자유 3D 상하/전방 반전 수정 — 2026-11-06 UTC

- 원인:camera_view.rgb_camera가 R.T에 OpenCV→OpenGL 축 반전diag(1,-1,-1)을추가했다. 현재설치된Viser.CameraHandle.wxyz setter는이미OpenCV(+Z전방,-Y위)규약을받고클라이언트변환을내부처리한다. 중복변환으로원하는look_at/up를설정한뒤wxyz대입이전방과위쪽방향을다시반전했다.
- 수정:vggt_slam/demo/camera_view.py의wxyz는R.T그대로전달. P기반RGB투영/점군/검색결과는변경하지않음. 기존8097에적용.
- 회귀:tests/test_demo_camera_search.py에quaternion의+Z와-Y가계산된forward/up와일치하는assertion추가. 실제Viser.CameraHandle publicsetter에position/up/look_at/wxyz를동일순서로적용하고look방향과up dot>0.999확인하는테스트추가. fake클라이언트초기연결timestamp설정후관련 **6 passed**,기존Dash warning1. 전체104개를실행했다고주장하지않는다.
- 실제Chrome evidence/browser_free_camera_axes_01/browser.json:메인RGB·BEV,기본RGB시점,자유3D전환/Reset,재생/Pause/Resume/동기화/하늘/Fit등모든interaction true,JS예외0. 추가모델추론없음. Ruff E9/F63/F7/F82·compileall·diff-check통과,graft build갱신.


## 오른쪽 기능 패널 전체 높이 확보 — 2026-11-06 UTC

- 사용자스크린샷의원인:studio.html이Viser iframe높이를왼쪽3D높이(--viewer-height)로제한하고,오른쪽하단context상태창이남은세로공간을차지했다. 실제기능패널이상단높이로제한돼분석/검색/지도컨트롤을보기어려웠다.
- studio.html에서iframe은100vh전체높이로확장. 오른쪽하단context설명창제거,상태/프레임번호는왼쪽상단툴바에작게통합. RGB·BEV는기존왼쪽하단배치유지하고rightsidebar경계밖으로넘어가지않는다. HTML을요청마다읽으므로서버재시작/모델추론없이기존8097에적용,사용자페이지새로고침필요.
- 실제Chrome evidence/browser_full_height_controls_01:full_height_controls=true(iframe높이>=window높이,context없음),left_views_do_not_cover_controls=true(RGB·BEV오른쪽경계<=sidebar시작),메인3뷰/자유뷰·Reset/재생동기화/탭/최적화/점크기/하늘/Fit검사통과,JS예외0. initial.png에서기능패널이화면맨아래까지표시되는것을시각확인. default_rgb_camera=false는검사시작시사용자가선택해둔자유모드의기존상태이며이번레이아웃회귀로해석하지않는다.Reset동작true.
- 저영향HTML/CSS수정으로새단위테스트/전체모델실행은추가하지않음. 브라우저DOM치수및실제UI검증,Ruff E9/F63/F7/F82,git diff --check통과. 기존데이터/검색결과보존.


## 메인 3D가 RGB·BEV에 가리는 문제 수정 — 2026-11-06 UTC

- 직전수정은오른쪽기능을확장하면서Viser iframe전체를100vh로만들어3D캔버스도전체높이가됐고,왼쪽하단RGB·BEV카드가그위에겹쳤다. 이번에는iframe/오른쪽기능은전체높이로유지하되,왼쪽실제3Dviewport만상단영역높이로축소한다.
- main_panel.py가설치된Viser클라이언트정적파일을같은origin의/viser/아래에서read-only로제공하고,websocket은기존내부Viser서버에명시적으로연결한다. 패키지파일/빌드수정/추가설치없음. 경로resolve후clientbuild내부파일만제공한다.
- studio.html은같은origin의canvasancestor에서실제왼쪽viewport를찾아높이와position:relative를지정한다. WebGL과보조2Dcanvas모두그영역을기준으로크기를갖고R3F ResizeObserver가실제카메라aspect도갱신한다. 오른쪽패널은100vh그대로,RGB·BEV는viewport아래별도영역이다. 폭은실제패널너비를측정해맞춘다.
- 초기browser_split_viewport_01에서는WebGL영역은분리됐으나절대배치보조2Dcanvas가아직전체높이를따라main_canvas_not_covered=false였다. 실제DOMprobe로원인을확인하고viewportposition:relative를추가했다. 실패증거보존. 이후검증은browser_split_viewport_final_01을사용한다.

- 최종실제Chrome browser_split_viewport_final_01:main_canvas_not_covered=true(모든visiblecanvas하단<=RGB·BEV상단),full_height_controls=true,left_views_do_not_cover_controls=true. 자유3D/Reset/재생·정지·동기화/하늘/점수·크기/탭·최적화/Fit전부true,JS예외0. 기존8097에적용. 추가모델추론/설치없이브라우저DOM치수및화면으로검증,Ruff E9/F63/F7/F82·compileall·diff-check통과,graft build갱신.


## KITTI 폐루프 데이터 실제 데모 열기 — 2026-11-06 UTC

- 사용자요청에따라기존 s03_kitti_loop_on_20261031_01을별도 **http://localhost:8101** 에실행,기존8097서비스유지. 입력508~1855의226선택이미지,240개프레임자산(중첩14),15개서브맵갱신,실제수락루프2개. 기존VGGT/SLAM추론은반복하지않고저장된결과를재생한다. PCD13,220,806점과원본데이터/ON·OFF결과보존.
- ON시각화용실제skyseg추가전처리:240프레임/226고유RGB,240,000preview점전부pixel투영,34.46초. 별도evidence/sky_kitti_loop_demo_20261106_01/에보관,원본PCD·events미변경. OFF결과에는이필터가없으므로ON/OFF외관비교시동일필터조건으로맞춰야한다. 같은ONrun내before/after는같은필터를사용한다.
- 실제Chrome evidence/browser_loop_demo_20261106_01:메인3뷰/겹침없음/전체높이패널/자유3D·Reset/재생·Pause3초·Resume/시점동기화/하늘/점크기·수/최적화before-after/Fit전부true,JS예외0.
- KITTI의넓은영상비율/좁은수직FOV에서기존Fit이전체지도를자를수있음을시각확인해보완. camera_view.overview_distance는robust bounding sphere와실제viewport aspect/60도overview FOV로거리를산출한다. tall/square/wide viewport세경우에sphere전체가수직/수평FOV안에들어오는회귀추가,관련 **7 passed**,기존Dash warning1. Ruff E9/F63/F7/F82·diff-check·graft build통과. RGB Reset시점은기존P를유지한다.
- 실제focused Chrome evidence/browser_loop_compare_20261106_01/:첫루프1829↔508,step14,same_source_frame=true,실제before/afterprojection_changed=true,accepted_loops=2. loop_before.png/loop_after.png와validation.json보존. 동일카메라에서전후를비교했다. 검사후step15전체run로돌아가Reset하고Play로처음부터재생시작(playback_started=true),브라우저open localhost8101실행.
- 이데모는저장된226선택이미지결과의2fps목표재생이며실시간VGGT추론이나원본10Hz영상재생이라고주장하지않는다. 검증된대상루프2개의실제제약/최적화실증이며전체장거리전역정합완벽을의미하지않는다. 기존정렬ATE ON9.9486m/OFF16.1635m는각각전체구간Sim3정렬후217개기준대응으로계산된값이다.


## 왼쪽 3D·RGB·BEV 크기 조절 — 2026-11-06 UTC

- `web/studio.html`에 가로/세로 separator와 상단 **뷰 크기 초기화** 추가. 가로 드래그는 3D 높이/아래 행 높이, 세로 드래그는 RGB·BEV 너비 비율을 조절한다. 키보드 방향키/Home, 더블클릭 축별 초기화, 최소 크기, 창 resize clamp를 지원한다. 오른쪽 전체 높이와 왼쪽 실제 canvas 분리는 유지한다.
- 수동 높이는 화면 높이 비율로, 너비는 행 비율로 localStorage에 저장한다. 프레임 갱신이 설정을 덮지 않고 reload 후 복원된다. 저장을 사용할 수 없는 브라우저에서도 현재 세션 조절은 작동한다. 기존 모델/데이터/PCD/검색 결과는 변경하지 않는다.
- 첫 브라우저 시도(01/02)는 키보드/초기화는 됐으나 drag 변화가 없었다. 실제 pointer 로그에서 down은 separator, move는 RGB로 전달되고 캡처가 풀리는 것을 확인했다. lostpointercapture에서 즉시 종료하지 않고 document pointermove/up + cancel/blur로 추적하도록 수정했다. iframe은 드래그 동안만 pointer-events를 비활성화한다. 별도 실제 마우스 probe에서 높이 604→704px 변경을 확인했다.
- `scripts/demo_browser_check.py --verify-resize` 추가: 실제 CDP 마우스 드래그, reload 유지, 방향키, 최소값, 초기화, 겹침/오른쪽 패널 유지 검사. 초기 검사 증거는 `evidence/browser_resize_views_20261106_01`/`02`에 보존하고 최종 검증은 분리된 임시 포트8120에서 수행해 사용 중인 데모 상태와 분리했다.

- 최종 실제 Chrome `evidence/browser_resize_views_20261106_final/`: 높이290.39→390.39px,RGB635.09→535.09px/BEV384.91→484.91px를 마우스로 변경. 새로고침 후 같은 값 복원. 최소높이185px(3D180)/RGB120px 제한,초기화 후 원래값 일치. 키보드·겹침없음·전체높이패널·재생/Reset 등 모든 interaction true,JS예외0. `resized.png`/`layout_reset.png`/`resize_geometry.json` 보존. 임시8120뷰어는 검증 후 종료하며 기존8101/8097은 유지한다.
- JavaScript 문법 검사,Python compileall,Ruff E9/F63/F7/F82,git diff --check 통과. 이번 변경은 HTML/CSS/로컬UI동작이므로 모델 재추론이나 전체SLAM테스트 반복 없이 실제포인터/키보드/새로고침으로 검증했다. 사용자 페이지 새로고침으로 적용된다.

## 자동차 전체 구간 검색 및 검색 경로 점검 — 2026-11-06

- 원인: 기존 현재 프레임+PE 상위 소수 후보 검색은 첫 유효3D 결과에서 종료했다. source982의 car2건은 전체 루프의 자동차 수가 아니다. 쉼표 입력을 단일 문장으로 SAM3에 전달하고 저장 저해상도 RGB를 사용한 문제도 확인했다.
- `search_policy.py`에 전수/표본/현재 범위·다중 프롬프트·관측 수 라벨, `search_assets.py`에 원본RGB 검증과 픽셀 중심 마스크 변환, `search_cache.py`에 내용/프롬프트/모델별2D 마스크 캐시를 구현했다. `demo_search_cached.py`는 schema3의 프레임별 증거와 전체 집계를 저장한다. current/all/sampled는 PE 로딩을 생략하고 전수는 조기 종료하지 않는다. 3D 좌표는 최신 저장 snapshot으로 재계산한다.
- `viewer.py`: 기본 전구간 전수, 진행률/검사 범위, 반복 관측 안내, Result frame 전체/개별 선택, 대표 프레임 마스크와 개별 RGB 동기화, Clear 후 재선택을 구현했다. 8101에 적용했고 기존8097은 유지한다. 이전 결과와 사용자 데이터는 보존했다.
- 실제 SAM3 CPU 전수: `logs/demo_runs/s03_kitti_loop_on_20261031_01/evidence/query_jobs/car_all_native_20261106_01/`: 226/226 고유 선택 프레임, 마스크979, 유효3D720, 처리1574.747829초. 원본1348장 전체가 아니라 해당 run에 기록된226장이다. 중첩14장은 재검사하지 않는다. 고유 객체 추적은 없으며720대를 의미하지 않는다. 무효259건은 모두 깊이 지원점8개 미만이다. source982의 원본1408×376→기록518×140 재현 픽셀 오차0.0, 이 프레임은 마스크2/유효3D2다.
- 실제 다중 클래스 `search_current_multiclass_native_20261106_01`: source982 car2/2,tree9/4,truck0/0,building5/5,음성대조 elephant0/0(2D/3D). 총16/11, 처리23.1333초. 별도 `search_current_cache_replay_20261106_01`은 한국어 자동차 alias 포함5개 캐시 모두hit, 동일16/11, 처리0.42365초. 타이머는 Python import를 제외한다.
- `search_audit.py` 실제 전체 일관성 감사 PASS:226장979마스크720박스,867,213개 지원점의 저장OBB 내부 포함 및 좌표/마스크/집계/프레임 대응 확인. `consistency_audit.json` 보존. `visual_review_12_frames.jpg` 실제 원본+마스크12장 육안 확인. GT 정확도나 전체 자동차 재현율을 측정한 것은 아니다. 기존 단일프레임 감사 도구는 schema3를 명시적으로 skip한다.
- 실제 Chrome `browser_search_v3_live_20261106_01/validation.json`: 전체226/226·720박스, source982 선택2박스+RGB일치, 전체 복귀,Clear·재열기 모두통과,JS예외0. 초기 자동화01~03의 대량박스 갱신 대기 부족은 보존하고 상태 polling한04 및 운영8101 결과로 검증했다.
- 웹 Search 버튼 실제 전수 재실행 `search_1794021684215107000`:226개 모두캐시hit,979/720 동일, 처리17.9396초. `browser_search_button_all_20261106_01/browser.json`의 search_start/search_completed/query_result_visible=true,JS예외0. 이 범용검사의 기존 상태 의존 default_rgb_camera/rewind_visible/sky 상태 문자열 검사 일부는false이므로 전체 UI검사 all-pass로 주장하지 않는다. 검색 전용 검증은 위 별도 증거로 통과했다.
- 관련 새7개 포함 전체112개 테스트 통과(9.57초,기존Dash warning1). 최초 sandbox 실행은 subprocess 자식 SIGABRT로106통과6실패하여 코드 변경 없이 외부 재실행으로112통과했다. 저해상도/변환 불일치fallback,범위중복제거,다중어/alias,캐시입력변경을 검증했다.
- 마무리: 변경 Python compileall 및 git diff --check 통과, graft build로90개 파일 그래프 갱신. 이번 마지막 Ruff 실행은 PATH 및 .venv에 실행 파일이 없어 수행하지 못했다. 임시8120 검증 뷰어는 종료하고 운영8101은 유지한다.

## 검색 패널 정리·선택 삭제·메인 RGB 분할 표시 — 2026-11-06

- `query_display.py`에 유효3D관측>0 프레임 목록 필터와 현재 playback_index에 맞는 RGB 마스크 합성 구현. schema3 다중클래스와 기존 단일프레임 결과 모두 지원한다. 원본 이미지는 복사하여 overlay를 만들며 다른 프레임 마스크를 섞지 않는다.
- `viewer.py`: Result frame의0건 항목 숨김, Delete selected query 버튼, 오른쪽 Object query frame 이미지 제거, 왼쪽 RGB로 마스크 표시 연결. Clear는 선택None→RGB원본+박스없음 상태로 즉시 갱신한다.
- `CachedRun.delete_query`는 선택한 query_id만 `evidence/deleted_queries.json`에 원자적으로 기록하고 새로고침/재실행 발견 시 제외한다. 사용자의 원본 결과·마스크·events·지도는 보존한다. 다른 검색 결과는 유지한다.
- 신규 회귀3개:0건 제외,현재프레임 일치·다중클래스 RGB합성·원본불변,삭제 후 CachedRun 재로드 지속·증거보존. 관련10개 및 전체 **115 passed**,기존Dash warning1. compileall·git diff --check 통과.
- 운영8101 실제 Chrome 최종 `evidence/browser_search_panel_v4_20261106_02/validation.json`:0건 프레임 숨김,오른쪽 결과이미지 제거,source982 RGB마스크 표시→Clear 후 JPEG변경+같은프레임 유지,박스해제·재열기,확인용 검색만 삭제→reload 후 목록 제외·증거보존 모두true,JS예외0. frame_982.png/clear_rgb.png 보존. 첫01은 서버 시작 뒤 외부에 만든 fixture가 목록에 없어서 삭제선택 실패한 자동화 준비 오류로 보존했다. fixture를 읽은 서버에서02를 재검증했으며 기존 사용자 검색은 삭제하지 않았다. 운영8101 새 프로세스 유지,기존8097 유지.

## Result frame 선택 후 RGB 갱신/유지 수정 — 2026-11-06

- 실제 Chrome 정지 상태에서는982→1119 선택 시 RGB프레임/이미지 URL이 정상 변경됐다(`browser_result_frame_refresh_20261106_01`). 재생 상태에서는 같은 선택이 RGB999/1123으로 덮어써졌다(`browser_result_frame_refresh_playing_20261106_01/validation.json`). 원인: 검색 결과 선택 콜백이 재생을 정지하지 않았고 playback 스레드는 render_lock 밖에서 다음 프레임을 예약했다.
- `select_object`/`select_observation`에서 선택 시 재생을 일시정지한다. playback tick도 동일 render_lock 안에서 playing 상태를 재확인하고 프레임 변경/렌더를 수행해 선택 직후 대기 중이던 tick이 덮어쓰지 않게 한다. 선택 이후 사용자가 Play를 누르면 선택 위치부터 재생한다.
- 관련10개 테스트 통과(기존Dash warning1),compileall·git diff --check 통과,graft build 갱신. 운영8101 재시작 적용,8097 유지.
- 최종 실제 Chrome `evidence/browser_result_frame_refresh_fixed_20261106_01/validation.json`: 매 선택 전 Play 실행→982/1119 선택,왼쪽RGB label 일치·이미지URL변경·완료로딩 확인,자동정지 및 추가2초 후 같은프레임 유지 모두통과. frame_982.png/frame_1119.png 보존.

## 고밀도 표시 캐시·화면 해상도 개선 — 2026-11-06

- `dense_display.py`/`demo_prepare_dense.py`: 저장depth/confidence/valid·RGB·최신snapshot의 P@H로 camera-local 점을 역투영. 기존 confidence percentile과 유효점 기준을 유지하고 기존 skyseg 픽셀+2px 경계 점수를 같이 저장한다. 새로운 고유 evidence 폴더만 생성하고 완료 index를 마지막에 기록한다. 소량max_frames 캐시는 자동사용 제외. source events SHA256·snapshot hash·프레임별 점수/sky 출처 보존.
- 소량 `dense_probe_20261106_01`:3프레임60000점,0.1033초. 전체 `dense_kitti_20261106_01`:240기록프레임(226고유+중첩14),프레임당20000점·총4800000점,4.21095초. 새 추론 없이 기존 깊이에서 생성했으며,기존240000점 preview/13220806점 PCD를 보존한다.
- `CachedRun`: 완성된전체캐시만 events/frame count/sky출처 일치 확인 후 선택,없으면 기존preview fallback. camera-local 그룹/sky 점수를 기존 render/camera_preview에 연결하여snapshot별변환·타임라인 미래프레임 제외를 유지한다. 내부use_dense=False로 비교 가능.
- `camera_view.py`/`main_panel.py`/`studio.html`/`viewer.py`: 실제뷰port/DPR을 반영한 aspect 유지 출력(최대1920×1080),1.5배 supersampling→Lanczos 축소,둥근점,기본예산600000점,현재프레임 우선. JPEG95/색차subsampling0. viewport POST는크기/DPR범위검증·debounce·반복요청제거. 기존calibrated P/검색박스/Reset/자유3D규약 유지. 설치Viser0.2.23이 precision인자를 지원하지 않아 임시서버 초기실패 후 인자를 제거했다(의존성변경없음).
- 세 실제구간 source982/1228/1692 비교 `dense_quality_review_20261106_01/`:같은1280×346·AA1.5에서 전경픽셀점유율3.83→38.07%,6.93→40.90%,2.99→26.03%. render+정합+projection CPU측정 고밀도0.410/0.378/0.294초,기존0.035/0.106/0.078초. 브라우저전송/박스렌더시간은 제외하며FPS나GT정확도지표로해석하지않는다. 비교스크립트는전경추가로약619k점을썼고실제뷰어는총600k예산을지킨다. comparison.jpg육안확인:건물/차량표면식별성향상,기존깊이오차/줄무늬는남는다.
- 신규4개회귀:full projective 역투영·RGB/sky픽셀정렬,viewportaspect/Retina상한,AA+깊이occlusion,실제캐시loading→before/after변환+미래프레임제외+기존fallback. 전체119 passed(기존Dash warning1). 첫sandbox전체실행은torch import SIGABRT로중단되어제한밖동일검사119통과(9.59초). 컴파일/브라우저검증을별도수행한다.
- 고밀도임시브라우저02의3초고정대기는API프레임982가나온시점에화면이590인갱신중상태에서실패했다. 이미지preload뒤같은URL을재요청하던경로를blob1회다운로드·decode완료후3개이미지동시교체로변경해snapshot만료/중복요청을줄였다. 이후검사는실제RGB label/이미지완료상태를polling한다. 초기실패증거도보존한다.

- 실제Chrome 최종 `evidence/browser_dense_display_20261106_05/validation.json`:source982/1119 RGB이미지갱신·분할·600000점·AA1.5·선택후정지유지,Retina resize 출력519×1920,Clear·자유3D·Reset 모두통과,JS예외0. 초기03은Clear 직후0.5초대기로None선택상태미도달,04는Clear/free 후1초대기로상태미도달한자동화실패를보존하고05는실제상태polling으로검증했다. final단계고밀도웹동작은별도모델실행이아니다.
- 운영8101 재시작적용 완료. `dense_quality_review_20261106_01/live_8101.json`에서600000점·AA1.5·출력346×1280 초기값 확인. 페이지viewport를수신하면실제크기로변경한다. 기존8097은유지하고임시8120종료. 캐시총64,696,984bytes. 비교/브라우저실행스크립트도각evidence폴더에보존했다. JS문법(node --check),Python compileall,git diff --check 통과,graft build 갱신.

## 저장 road segmentation → 3D Road 및 BEV connectivity — 2026-11-07

- 사용자 생성 실제road전수검색 `evidence/query_jobs/search_1794054591014459000/result.json` 확인:226/226,218유효3D관측. 재분할하지 않고 저장schema3프레임별마스크/깊이/threshold를 재사용한다.
- `road.py`:best_road_query는삭제되지않은검색중최대검사범위를우선한다. RoadLayer는프레임ID대응·깊이격자마스크차원을검증하고mask union+valid/confidence로P@H를역투영한다. 프레임별최대6000개camera-local점을유지하며snapshot별world변환캐시와타임라인필터로before/after·미래프레임제외를지원한다.
- `viewer.py`:Show road기본ON,선택run에road없으면비활성/사유표시. 누적/현재프레임지원점수를표시한다. 자유3D의별도초록점군과기본calibrated raster에같은world도로점을표시한다(화면cap150000). BEV display 표면지도/Road connectivity선택추가,3D토글과독립,plane전환지원. 선택검색삭제시새best결과로갱신. 검색Clear는기존검색만해제하고도로는전용checkbox로제어한다.
- Connectivity는128×128의관측셀4-neighbour graph,색상연결성분+셀중심인접edge를표시한다. 미관측공백/대각선틈을메우거나궤적을road연결로사용하지않는다. 상대좌표2D투영이므로주행가능성이나입체교차연결을검증한것이아니다. 셀크기는관측범위의함수이며지정고정미터해상도가아니다.
- 실제 `evidence/road_connectivity_20261107_01`:209개프레임에유효지원점,총1242009점. 전체frame239에서1229관측셀/2035edge/2연결성분,cell_width0.0322343복원단위. frame0은6000점/594셀/817edge/59성분,frame75는425243점/817셀/1364edge/2성분. 처리1.7805초(준비+세구간변환·BEV·graph저장). graph.npz의nodes_yx/edges/counts/components/origin/cell_width 보존. 최초connectivity이미지이후인접선표시를추가했다.
- 현재source1829의저장road분할은mask0건을확인했다. 누적도로는있어도현재프레임0점으로표시한다. 없는마스크를보간하거나전체도로존재를부정하지않는다.
- 신규4개:공백/대각선미연결,empty/nonfinite,최대검색범위선택,projective snapshot변환/타임라인미래제외. 전체123 passed(27.60초,기존Dash warning1). 인접선/안내추가후관련4개재검증,compileall/diff-check수행.
- 임시8120 실제Chrome 01:road3D토글,BEV옵션복귀,둘의독립성,free/Reset통과,JS예외0. 초기화콜백으로source1829/frame236인시점에누적1230009점을확인했으며전체frame239의1242009점과혼동하지않는다. 최종02는도로검출된source982와frame239를명시선택해검증한다.
- 최종임시Chrome02 `browser_road_connectivity_20261107_02/validation.json`:frame75/source982↔frame239타임라인전환,3DroadON/OFF,BEV표면/연결전환,독립토글,자유3D/Reset 모두통과,JS예외0. source982의실제3D도로가초록으로표시된road_rgb_view.png 및 전체road_full_connectivity.png확인. 운용8101재시작후 `browser_road_live_20261107_01/validation.json`에서frame239,1242009도로점,1229셀/2035edge,자유3D+Road connectivity선택확인. road_full_demo.png보존. 왼쪽BEV카드제목/통계도연결모드일때ROAD CONNECTIVITY·셀/연결수로표시하도록연결했다(JS문법검사통과). 임시8120은종료,운영8101/기존8097유지.

## BEV Zoom·overlay/주행 토글·3D/RGB 분할·패널 Show/Hide — 2026-11-07

- `raster_bev`에zoom(.5..8),show_trajectory,road_points optional인자추가. 같은투영/범위로표면위road관측셀인접edge를초록색합성한다. 별도road이미지로교체하던방식을독립overlay체크로대체했다. 줌은좌표span을변경하고Reset1배,경로숨김시bounds유지. trajectory OFF는경로와현재마커를함께숨긴다. 기존실시간BEV호출자는기본값으로기존표시유지.
- `viewer.py`:3D/RGB마스크독립체크추가.3D OFF는road_surface와query OBB/raster박스숨김,RGB OFF는현재프레임overlay만생략. 선택검색/원본데이터는유지한다. selected_camera frustum color=(255,195,48). 기존Reset을View Reset현재프레임으로명확히표시했다.
- `MainPanel`의허용action에zoom_in/out/reset,road_overlay,trajectory,mask_3d/rgb를연결. GUI와같은state를갱신해좌측카드/상단버튼과오른쪽체크가동기화된다. unknown액션은거부한다. API메타데이터에zoom/trajectory/3D/RGB상태및overlaygraph통계추가.
- `studio.html`:BEV카드버튼5개,RGB Mask,3D Mask,항상접근가능한패널Show/Hide추가. same-origin Viser viewport의형제패널만접고flex/width와sidebar값을확장하며복원시원래display를되돌린다. 기존splitter비율은유지한다. 카드이미지를flex레이아웃으로조정해도구줄이이미지를가리지않게했다.
- 신규3개BEV회귀:zoom span·Reset픽셀동일,경로ON/OFF좌표bounds동일,road optional overlay가동일좌표를사용. 기존실시간/road/RGB검색포함전체 **126 passed**,기존Dash warning1(24.93초). JS문법검사/compileall통과. 임시8120에서실제Chrome검증후운영8101적용예정.
- 실제Chrome01에서Zoom/overlay/주행기록/독립마스크및실제RGB픽셀변화는통과했으나패널복원너비검사에서실패(before300→복원1056). 원인은보이는상태에서도Viser의원래inline width/flex를빈값으로덮던코드다. 숨길때만원래스타일을저장하고보일때정확히복원하도록수정했다. 초기증거는 browser_view_controls_20261107_01에보존하고02재검증중이다.
- 최종실제Chrome02 `browser_view_controls_20261107_02/validation.json`:ZoomIn/Out/Reset,도로overlay·주행기록토글,RGB JPEG실제픽셀변경,3D/RGB독립토글및query박스0↔2,패널너비1056→1440→1056.09375복원,ViewReset현재source982유지모두통과,JS예외0. panel_hidden.png/controls_ready.png 및실행스크립트보존. 운영8101재시작적용후 live_8101.json에서zoom1·mask3D/RGBtrue·trajectorytrue·도로/overlay확인. 기존8097은유지하고임시8120종료. 원본검색/지도/PCD/events변경없음.

## BEV Mask/Box·마우스 Zoom/Pan·패널 Resize·3D 재생조절 — 2026-11-07

- `raster_bev`:pan은전체관측범위span대비2D변위,유한값/범위검증. 줌·pan변환을표면/road edges/마스크/OBB/궤적에공통적용. 청록mask지원셀/빨강box별도옵션과통계추가. RoadLayer를prompt=None으로일반검색마스크에도재사용하고only_frame으로Result frame선택범위를동기화한다.
- `viewer.py`:BEV Mask/Box와RGB Box독립체크추가. BEV선택쿼리없을때Mask는road,Box없음. 선택query/관측의snapshot·타임라인을검증하여다른시점박스제외. RGB Box는저장깊이격자마스크2D경계이며RGB Mask와독립. query_display에show_masks/show_boxes플래그추가.
- MainPanel허용액션/검증추가:bev_view(zoom/pan),frame/previous/next,play/pause,BEV/RGB box/mask. 상단기능은기존GUI timeline/checkbox와같은state를갱신한다. 수동프레임은pause+범위clamp,빈프레임run은무시한다.
- studio:BEV휠커서기준줌·pointer capture팬,여백좌표보정·debounce/in-flight최종요청보존. ZoomReset은pan도0으로. 사이드바구분선실제마우스드래그/방향키,너비min/max제한·localStorage복원·Show/Hide유지. 상단play/pause·이전/다음·range/번호입력추가.
- 신규2개테스트(pan/semantic좌표일치,RGB box-only원본내부유지)포함전체128 passed(25.15초,기존Dash warning1). only_frame추가후관련12개통과. JS문법/compileall/diff-check수행.
- 브라우저01/02는이전car전수결과가사용자삭제목록에있어저장검색선택에실패했다. 삭제를되돌리지않고현재저장된road query `evidence/query_jobs/search_1794081691789521000/result.json`를사용하도록검증스크립트수정,source982의1개관측으로검증한다. 현재road/human목록과원본증거는그대로보존한다.
- Chrome03의모든BEV/RGB/프레임/재생조작은통과했으나패널변화384→966px가90px드래그와불일치함을추가검사로발견했다. DOM진단(browser_sidebar_diagnosis_20261107_01)에서패널너비설정루프가뷰포트본체까지같은너비/min/max로덮는원인을확인했다. 뷰포트와44px보조버튼은제외하고두실제패널컨테이너만조절하며뷰포트는나머지너비를사용하도록수정했다. 04실패증거도보존하고05에서변화량을엄격히검증한다.
- 최종Chrome05 `browser_advanced_controls_20261107_05/validation.json`:BEV Mask/Box독립·선택road982의BEV박스1개,RGB box-only,실제mouseWheel줌,실제drag pan[-0.116659,0.058361],Reset 줌1/pan0,패널384→474px(90px이동)·Show/Hide·reload474복원,frame번호/이전/다음/play/pause모두통과,JS예외0. advanced_controls.png/실행스크립트보존. 운영8101재시작적용후live_8101.json에서새Mask/Box/Pan/240프레임확인. 임시8120종료,기존8097유지. 선택삭제상태와원본road/human검색·데이터는보존했다.

## Classic V1 보존 및 별도 Smooth V2 — 2026-11-07

- 사용자 요청대로 기존8101프로세스/표시소스유지. 변경전표시소스24개를 logs/demo_versions 및 docs/versions에tar.gz+SHA256 manifest로보존. 비교결과기존표시모듈·HTML은모두동일하고demo.py만version CLI추가로변경됨. V2새파일로분리하고공통helper는변경하지않았다.
- 추천순서1/2/5구현:PlaybackClock 단조시간축/늦은지도frame건너뛰기,노드별PersistentMap업로드/seek미래노드숨김,재생중120k 계산예산·노드당1000점·20k도로표시·JPEG80·CPU camera raster생략/정지시기존고화질복원. frame처리완료뒤0.5초누적대기는V2에없다.
- 추천3/4구현:KITTI원본연속1348장 MP4 준비(508~1855,1280×342,134.8초,sourceFPS10 명시fallback;timestamps부재표시). 파일누락·선택RGB3지점대응·ffprobe프레임수검증.13.0237초/65759217bytes. Native video HTTP Range206전송,브라우저영상시계와지도시계동기화. CameraPath Slerp+위치보간20Hz/GPU시점,정지시기존skew/lensshift calibrated raster복귀. RGB분할/박스는정지한선택키프레임에서만표시하여영상의다른프레임에오버레이하지않는다.
- version_picker8100→Classic8101/Smooth8102선택,CLI view --version classic|smooth 및 versions추가. 기존view기본classic. V2상단에버전선택/V1링크,버전표기와지도키프레임/영상시간을구분했다.
- 전체132 passed(27.36초,기존Dash warning1). 초기보간테스트의Scipy Euler입력모양을Nx1로맞춰수정후관련4개통과. 처음V2브라우저01은초기관측6개분량의전체유효점113751개가120k보다작아고화질판정이실패한테스트오류였다. quality_mode/high 및AA1.5로검증을수정했고초기실패증거도보존했다.
- 최종Chrome초기02:영상/벽시계0.997508배,decode카운터증가10.5718/s,지도프레임1→4·chunk uploads2→5,render0.152~0.158초(그구간샘플). 후반late01:비율1.0000/decode9.94089/s. 둘다native영상진행·지도부분갱신·pause시간고정·정지고화질복원·BEV기존버튼통과,JS예외0. decode카운터는제시FPS아님/30·60fps보장없음. 스크린샷/샘플/스크립트를각evidence에보존했다.
- smooth_versions_20261107_01검증:기존V1 API가V2로바뀌지않음,8100두링크,8102MP4부분응답206/64byte확인. 상세실행/제약은docs/DEMO_VERSIONS.md.
- 최종UI/즉시경량전환후 `browser_smooth_v2_final_20261107_01/validation.json`:Play즉시quality_mode balanced+chunk업로드,3.3992초nativeRGB진행,Pause high복원,실제8100선택화면의8101/8102링크확인,JS예외0. version_picker.png/v2_ready.png와실행스크립트보존. source모듈23개최종SHA동일,launcher demo.py만변경확인. 관련4개재검증,JS문법/compileall/git diff --check통과,graft build갱신. Classic8101/Smooth8102/선택화면8100을동시에유지한다.

## Smooth V2 반복 재생 RGB 동기화 수정 — 2026-11-07

- 원인경로:기존smoothPoll은native.paused일때만currentTime을설정하여새재생/seek불연속을명시적으로구별하지못했다. 이전video timeupdate/ended가새재생에들어와시계/정지상태를덮을수있었다. 재생시간종료시마지막지도프레임이렌더되지않으면Play의프레임기반끝판정도놓칠수있었다.
- V2에generation추가:play/pause/명시프레임seek시갱신,API/smooth로전달. browser는generation변경시명시pause/seek하고seeked이후재생한다. source run+generation이맞는video_clock만수용하고seeking중시간보고는막는다. native ended의pause도generation으로낡은이벤트를거부한다. 같은시간seek에서이벤트대기가고착되지않도록필요할때만seek한다.
- 종료루프는마지막frame239를확정후정지. Play는프레임과clock양쪽의끝상태를검사해0으로재시작한다. Classic V1/원본데이터는변경하지않았다. 운영8102만재시작적용.
- 실제Chrome `browser_smooth_replay_20261107_01/validation.json`:끝직전238에서자연종료239→재생0복귀를2회반복,각RGB시간이1.5초대기중1초이상증가/paused=false,이전generation clock134.7전송거부,source982프레임seek후native/서버시간오차1초미만검증모두통과,JS예외0. replay_ready.png/실행스크립트보존. 전체134초를매번기다리지않고마지막0.2초부터종료경로를실제로통과했다.
- clock끝후재시작elapsed초기화회귀추가,관련5개통과(기존Dash warning1). JS문법/compileall/git diff --check통과. 사용자기존V2탭은새로고침으로새클라이언트를읽어야한다.

## Git 커밋 전 검증 — 2026-11-07

- 누적 데모 구현·테스트·문서·V1 표시소스 스냅샷78개 파일을 커밋 대상으로 확인했다. TerraScene/과 .DS_Store는 별도 변경으로 보존하고 제외했다. 실행 데이터/logs/모델은 포함하지 않는다. *.json ignore 규칙으로 제외되던 V1 SHA256 manifest는 해당 파일만 명시적으로 추가했다.
- 전체133 passed(13.22초,기존Dash warning1). 최초sandbox검사는132통과/1실패:OMP 공유메모리 제한으로git 자식프로세스가SIGABRT한 환경 오류였고,코드 변경 없이 제한 밖 동일검사로133개 통과했다. staged diff --check 통과.
