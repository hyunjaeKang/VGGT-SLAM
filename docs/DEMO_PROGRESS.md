> **최신 요약 (2026-11-08):** [SESSION_HANDOFF.md](SESSION_HANDOFF.md) → [CURRENT_STATUS.md](CURRENT_STATUS.md) → [V4 HTML 계획](../26.11.09.VGGT_SLAM.Plan.html). 아래 기록은 시간순 누적이며 초기 “미완료” 표시는 이후 완료 증거로 갱신됩니다. V3와 회전 보정은 구현·검증됐고 V4는 계획 단계입니다. 현재 사용자가 새 유튜브90초 작업을 실행 중이므로 job 상태를 먼저 확인하세요.

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

## Smooth V2 재생 3D 점 밀도·투영 일치 — 2026-11-08

- 원인확인:PersistentMap 노드당1000점한도와재생시단순Viser중앙투영/정지시full K CPU투영의차이. 특히skew/principal-point가큰프레임에서형태/시점차이가커졌다. 기존V1은수정하지않는다.
- 새 gpu_scene.py:고밀도camera-local샘플→선택snapshot world좌표의immutable packet(positions float32/colors uint8),N/offset 검증가능한VGP2포맷. 동일노드최초1회업로드,고정무작위순서의draw count만LOD변경. 현재3개관측우선배분,전체budget준수. seek미래노드제외,sky필터/finite검사,run/snapshot/qualityepoch변경시낡은packet거부. free orbit도동일한점샘플사용.
- 새 gpu_renderer.js:별도WebGL shader로full K/pose를직접clip좌표에투영. CV +Y→GL축처리·depth test·원형soft point·실제뷰aspect/레터박스보존. camera path를최초수신후각requestAnimationFrame에위치/Slerp/K보간. 미래맵을잠깐표시하지않도록scene frame/epoch/path검사. 버퍼비동기수신/삭제·LOD draw count와geometry전송분리. GPU준비전은기존보정이미지를표시하고WebGL불가시CPU fallback. 숨긴camera img의rect가0이되는문제를피해실제height splitter 경계로canvas크기를계산한다.
- viewer_smooth/smooth_panel:GPU scene/path/packet엔드포인트,재생품질자동/높음/균형/가벼움,paused CPU도동일한보간P로시점차이완화. 보정GPU사용시Viser중복점군draw를피하고자유시점에서만동일LOD를보여준다. RGB재생/세대동기화/검색/BEV/소스데이터는유지한다. 표시면과BEV계산샘플수를구분한다.
- 신규 packet/LOD·near우선/반복업로드없음/seek/world투영/sky/snapshotepoch테스트4개. full136 passed(25.59초,기존Dash warning1;4번째추가전),관련9개통과. 최종전체검증은추가후별도실행한다.
- 실제Metal `browser_gpu_quality_metal_20261108_01`:renderer Apple M2 Max,software=false,실제맵600000점(정지/재생동일),GPU約59.9775fps,RGB requestVideoFrameCallback約9.99625fps,영상/벽시계1.0000. P픽셀최대오차1.364e-12,고화질정지복원/JS예외0. playing_dense_gpu.png 육안확인:RGB와동일방향의조밀한건물/문/도로표현.
- 첫SwiftShader고정600k실험은GPU約2fps/RGB約1.5fps로느렸고그사실을보존했다. 자동소프트웨어01(120k/960px)은GPU約6.82fps/RGB約3.65fps였다. 따라서명시적software감지시자동모드만90000점/640px/road10000제출로더낮추고재검증한다. 이환경을실제Metal성능으로혼동하지않는다.

- 자동소프트웨어02 최종실험은90000점LOD/640px/road10000으로영상속도1.00005배,RGB제시4.495fps/GPU6.493fps였다. 하드웨어가속과동등한성능은아니며그한계를docs/DEMO_VERSIONS에도기록했다. 일반GPU는600k로유지했고형편에따라자동/고정높음/균형/가벼움을선택할수있다.
- 최종전체137 passed(25.45초,기존Dash warning1). free orbit의snapshot전환시동일개수buffer를잘못재사용하지않도록epoch변경에서Viser handle도재생성하게수정했고관련9개통과. budget변경은패킷/epoch를유지하고GPU draw count만바꾸는회귀도추가했다.
- 운영V2(8102)적용후 `browser_gpu_quality_live_20261108_01/validation.json`:실제Metal/M2 Max,정지/재생600000점,RGB제시9.9965fps/GPU animation59.9790fps,벽시계속도0.999975배. 재생중자유3D/Reset전환·정지복원·JS예외0. 투영오차1.364e-12는JS보정행렬수학비교이며GPU raster실픽셀정밀도가아니다. 렌더스크린샷/스크립트보존. WebGL epoch교체시ready를해제해로딩중빈GPU화면을피하고기존보정이미지를사용한다.
- Classic 표시소스SHA비교는기존대로demo.py launcher만차이,나머지V1모듈/HTML동일. 운영8101/V1·8100선택화면은유지하며임시8120만종료한다. 원본지도/PCD/깊이/분할/사용자검색목록은변경하지않았다. JS문법·compileall·diff-check통과,graft build갱신.

## V2 재생 중 상단 툴바 깜빡임 수정 — 2026-11-08

- 원인:지도스냅샷poll과smoothPoll이#mode/#status에다른문구를서로덮었다. poll은ON/OFF와Play문구도같은값으로textContent재할당하여DOM을불필요하게재생성했다. 길이가다른상태문구·blur배경이GPU화면위에서재배치/합성을증폭시킬수있었다.
- studio_smooth.html만수정(V1유지):mode/status는smoothPoll한곳에서만갱신하고NativeRGB시간라벨과지도프레임라벨의소유도구분. setText/setPressed로실제변경일때만DOM수정. 모드/상태/프레임영역과Play버튼너비를고정하고숫자는tabular,툴바배경을불투명·명시z-index/isolation으로지정해GPU배경blur의존을제거했다. 미디어없는run의RGB표시는기록이미지로복귀한다.
- 실제Chrome/Metal `browser_toolbar_stability_20261108_01/validation.json`:정상재생4초동안MutationObserver가감시한버튼/모드/재생상태불필요변경0회,버튼좌표·너비·높이20샘플모두일치. pause/resume라벨정상변경,JS예외0. playing_stable_toolbar.png/검증스크립트보존. JS문법/node --check·git diff --check통과. HTML/CSS/DOM갱신변경이므로백엔드전체테스트반복대신실제DOM/레이아웃/전환을검증했다. 운영8102가정적HTML을동적으로읽으므로재시작없이페이지새로고침으로적용된다.

## Live V3 — 디스크 비디오에서 실제 지도·도로 생성 및 완료 후 검색 — 2026-11-08

- 사용자 요청: V2를 기반으로 새 버전을 만들고, 로컬 비디오 선택 → 실제 3D/RGB/BEV+ROAD 생성 표시 → 생성 완료 후 검색을 구현했다. 기존 V1(8101)·V2(8102) 실행과 이전 사용자 데이터/검색 삭제 목록은 보존했다. 새 V3는 `http://localhost:8103`, 작업 뷰는 8104이며 8100 선택 화면에 링크를 추가했다. 실행은 `.venv/bin/python demo.py live --port 8103 --viewer-port 8104`. 사용법·저장 구조·범위는 `docs/LIVE_V3.md`에 기록했다.
- `live_studio.py`/`studio_live.html`: 실제 파일 선택과 스트리밍 업로드(원본 복사본, 최대4GiB), 설정 검증, 고유 작업 폴더와 실제 run 식별, 단계·입력/고유지도/서브맵/ROAD 수·경과시간·로그, 완료 작업 다시 열기를 구현했다. 동시 생성/취소된 업로드 교체를 막고 중지는 자신이 실행한 자식만 대상으로 하며 결과를 삭제하지 않는다. 서비스 재시작 후 완료 작업 기록을 다시 읽는다.
- 실제 모델 경로: 기존 `.venv`의 `main_realtime.py --camera video_file --headless --no_video_window --video_pacing offline --device auto`로 VGGT 깊이·카메라·점군·서브맵 연결·그래프 최적화를 수행한다. 이 Mac에서는 MPS가 선택됐다. ROAD는 `.venv-open-set`의 SAM3 CPU worker로 계산한다. `demo_search_cached.py --stream-results`는 프레임마다 원자적 부분 결과를 공개한다(기본 검색 동작은 유지). 최신 스냅샷 배치로 합치며 같은 run의 segmentation 캐시를 재사용한다.
- 기록 중 JSONL의 미완성 마지막 줄은 제외하고 마지막 `optimization_finished`까지의 접두부만 공개한다. 완료 스냅샷 폴더만 링크하여 worker가 미완성 NPZ를 읽지 않는다. 원본 Recorder 이벤트를 수정하지 않는다. V2 viewer에 선택적 live-control 갱신을 추가했고, 미지정 시 기존 V2 동작을 유지한다. 생성 중에는 최신 지도 프레임으로 이동하며 검색을 막는다. 생성 완료 후 실제 최종 run으로 전환해 전체 구간 검색을 허용한다. sky_v3·smooth_media_v3 캐시는 별도 생성하고 원본 PCD/깊이를 변경하지 않는다.
- 첫 실제 소량 실험 `logs/demo_v3_jobs/live_20261108T092540_da3e45b7`: PandaSet 로컬 518×294/1fps 영상의 앞6프레임, submap_size3/min_disparity0/max_loops0. 실제 VGGT 2개 서브맵·고유6키프레임(중첩포함7관측), 원본 PCD799486점, ROAD6/6프레임 모두 유효3D 관측, 입력 키프레임 누락0. 생성~90.50초. 이 개발 초기 실험에서 단계 번호를 개수로 표시하던 문제와 ROAD 완료 count 초기화를 발견해 수정했다. 기존 결과는 유지했다.
- 최종 실제 Chrome 검증 `evidence/browser_live_v3_20261108_01/browser.json`: 브라우저 파일 입력 선택으로 새 run `video_20261108T173307_231634000` 생성. 지도4→6 고유프레임, 서브맵1→2, ROAD1→6 순차 증가. RGB/3D/BEV 이미지 로딩, 생성 중 Search disabled, live ROAD 표면, 최종 V3 title/검색 활성화/기본 전구간 범위/검색 결과 선택을 모두 통과했다. JS 예외0. selected/live_road/completed/car_search PNG와 시간별 samples.json을 보존했다. 이 검증 브라우저는 SwiftShader를 사용했으며 하드웨어 렌더 FPS 측정이 아니다.
- 최종 소량 실험 생성104.96초(모델 로딩·실제 추론·도로·하늘·MP4 준비·작업 뷰 전환 포함). VGGT 결과는 2서브맵·PCD799486점·6고유키프레임·drop0이며, 최종 선택 프레임의 누적 ROAD 표시36000점. 생성 후 실제 `car` 전구간 검색은6/6프레임,55.96초,2D116건/유효3D104건. 이 수는 여러 프레임의 중복 관측이며 고유 차량 수나 정답 recall/precision을 뜻하지 않는다. 기존 검색 코드를 통한 실제 SAM3 추론이며 mock 결과가 아니다.
- 새 회귀8개: 미완성 JSONL/미완료 스냅샷 배제, 완료 접두부와 원본 보존, 업로드 경로/확장자·동시 생성·고유 폴더, 잘못된 처리 설정, 소유 자식만 취소 및 취소 업로드 보호. 최종 전체145 passed/25.71초, 기존 Dash deprecation warning1. Python compile/HTML JavaScript `node --check`/`git diff --check` 통과. 그래프를 갱신했다.
- 한계: 실시간은 **완료된 서브맵·분할 결과를 순차 표시**하는 뜻이다. 모든 원본 프레임의 30/60fps 추론은 아니며 선택되지 않은 중간 프레임의 road를 계산하지 않는다. 생성 도중에는 새 결과 도착 시 최신 프레임으로 이동하고 마지막에 최종 run으로 뷰를 한 번 재연결한다. 중지 작업의 추론 재개는 지원하지 않으며 결과 보존 후 새 생성/완료된 지도 열기를 사용한다. 검증은 짧은6프레임이며 긴 영상의 처리시간·지도정확도·도로주행성은 별도 검증이 필요하다.
- 최종 재시작/복원 검증 `evidence/browser_live_v3_20261108_01/restore.json`: V3 서버 재시작 후 완료 작업 ID로 같은 실제 run을 다시 열고 ROAD 표시·원본 영상 미디어·V3 title·검색 가능 상태를 확인했다. 8100/8101/8102/8103 모두 HTTP 접속 및 선택 화면 V3 링크 확인. 복원 전후 원본 events.jsonl/poses.txt/poses_points.pcd SHA256이 같았다. 최종 운영 V3에는 이6프레임 검증 지도를 열어두었으며 새 영상을 선택해 새 run을 생성할 수 있다.

## V3 영상 선택 비활성 및 MOV 상하 반전 수정 — 2026-11-08

- 사용자 실제 영상 `duke_status.mov`의 기존 전체 작업은 ROAD 처리 중이었고, poll이 file input을 disabled로 만들었다. label은 활성 버튼 모양을 유지하여 클릭해도 아무 반응이 없었다. 이전 검증은 DOM.setFileInputFiles를 사용해 이 클릭 경로를 놓쳤다. 명시적인 영상 선택 button → 동기 input.click으로 바꾸고 처리 중에도 다음 영상 선택은 허용했다. 새 추론 시작만 완료/중지까지 비활성화하며 안내 문구를 표시한다. 파일 창 취소 시 기존 선택을 유지하고 같은 파일 재선택도 가능하다.
- RGB 반전의 실제 원인: 해당 MOV의 Display Matrix rotation=-180, OpenCV AVFoundation ORIENTATION_META=180/AUTO=0. 기존 VideoFileCamera가 표시 회전을 적용하지 않아 RGB·깊이·SLAM 전체가 뒤집힌 입력에서 계산됐다. 추론 전 metadata의90/180/270도를 한 번 적용한다. backend auto rotation이 켜진 경우 추가 회전을 피한다. 원본 영상/기존 결과는 수정하지 않는다. 새 생성의 키프레임·깊이·검색·브라우저 원본 재생의 방향이 일치한다.
- 자유 탐색 overview는 고정 world -Y 대신 기록 카메라의 up/forward/right로 위쪽 방향과 시점을 구성한다. rolled camera에서도 horizon 위/forward 뒤에 위치하는 회귀 검증을 추가했다. V1 표시 코드는 변경하지 않았다.
- 실제 FFmpeg display-matrix90/180/270 MOV fixture를 생성해 VideoFileCamera의 결과와 FFmpeg autorotate PNG의 shape/픽셀을 비교하는3개 테스트 추가. 회전된 카메라 overview1개 추가. 최종 전체149 passed/30.25초, 기존 Dash warning1. JS node --check 및 diff-check 통과.
- 실제 사용자 MOV의 방향 보정 소량 재추론: `logs/demo_v3_jobs/live_20261108T104656_694854fa`, 실제 run `video_20261108T184700_282397000`. 앞6프레임/서브맵3/이동기준0/루프0, MPS 2서브맵·PCD233500점·ROAD6프레임 검사·약94.07초. `evidence/browser_live_v3_rotation_20261108_01`: 정상 방향 RGB·3D를 스크린샷으로 확인, 생성 중 검색 잠금/완료 활성화/실제 car 검색 선택/JS 예외0. 이 장면의 road 검사는6프레임 완료했지만 유효 road 표면이 없으므로 도로 존재를 주장하지 않는다.
- 기존 사용자 전체 작업 `video_20261108T181003_605025000`은 중단하지 않고 완료됐다(305입력/95키프레임/12서브맵,약831.53초). 이 결과와 원본 MOV는 보존했다. 기존 전체 결과는 반전 입력으로 추론했으므로 화면만 뒤집어 기하·마스크를 섞지 않고, 정상 방향의 전체 지도가 필요하면 원본을 새로 생성해야 한다. 현재 V3에는 보정된6프레임 검증 run을 열어두었다.
- `evidence/v3_picker_orientation_20261108_01`: 실제 버튼 mousePressed/mouseReleased → Page.fileChooserOpened 이벤트 → YouTube clip.mp4 선택까지 검증. 이전의 DOM 강제 파일 지정만으로 버튼 클릭 성공을 추정하지 않는다. 원본 raw 프레임과 보정 프레임을 별도 증거 JPG로 보존했다.
- 처리 중 UI 상태에서도 실제 chooser 이벤트/선택 성공, input·선택 버튼 enabled 및 생성 시작 disabled를 동시에 확인했다(`picker_busy.json`). 자유 탐색 Fit map 스크린샷 `free_upright.png` 확인 후 RGB Reset으로 복귀했다. 새 페이지는 서버 재시작 없이 정적 HTML을 다시 읽으므로 기존 탭은 새로고침하면 영상 선택 수정이 적용된다.

## 문서 전체 인계 갱신 및 V4 실시간 객체 지도 조사·계획 — 2026-11-08 UTC

- 사용자 요청: 지금까지의 작업을 다음 세션에 이어갈 수 있도록 문서를 갱신하고, 지도를 생성하면서 미리 정의한 객체를 찾는 방법을 최신 자료와 함께 검토해 `26.11.09.VGGT_SLAM.Plan.html`에 정리했다. 요청 파일명은11-09지만 실제 clock 기준일은11-08UTC이며 그 차이를 문서에 명시했다. V4 구현·새 모델 설치·다운로드·원격 worker 생성은 하지 않았다.
- 새 `docs/SESSION_HANDOFF.md`에 읽는 순서·복사 가능한 재개 프롬프트·branch/origin/HEAD/미커밋·서버·데이터·실행 중job·코드 연결·회전보정·삭제목록 보존·검증 근거·다음 R0를 정리했다. `CURRENT_STATUS.md`에 구현/실증/계획 및 한계를 분리하고 `INDEX.md`로 문서별 역할을 연결했다.
- README/AGENTS/10-30 계획·프롬프트와 데모 가이드·버전·V3·UI·결과·인수·초기 코드 리뷰·PandaSet/KITTI360/YouTube 보고서를 갱신했다. 과거 수치와 초기 미완료 기록은 역사로 보존하고 최신 상태로 연결해 재시작 시 혼동을 줄였다. 기존 단계나 모델 실험을 처음부터 다시 수행하지 않는다.
- 공식 코드·문서·저자 논문/프로젝트41개를 검토했다. VGGT-SLAM/SceneVGGT/ConceptGraphs/ConceptFusion,YOLO26/YOLOE-26/YOLO-World,ByteTrack,EdgeTAM/CoreML,SAM2/SAM3.1,DART/DARTF,PIDNet,Stream/Fast/Infinite/XStream/RetrieveVGGT,HorizonStream/SceneBound,DA3/VDA,MASt3R-SLAM/CUT3R,VGGT-Segmentor,S2Tok,LingBot-Map/MetricTrail,최신RT-DETR-World까지 적용 범위와 공개·장치 조건을 구분했다. 검색 결과 요약의 날짜를 그대로 쓰지 않고 arXiv 수정일·공식 release를 확인했다. 조사 원장 `docs/research/2026-11-09_realtime_object_mapping.md`.
- 권고: 기존 VGGT-SLAM 유지 → 단계별 계측 → 상주 semantic worker/새 완료 프레임만 → 고정 대상 경량 detector 또는 사전 vocabulary YOLOE → ByteTrack/선택 프레임 mask → 동일frame의깊이 준비후local anchor3D승격 → 최신 H로 재투영. ROAD/sky는별도경량 semantic 경로,CPU SAM3는희소정밀 fallback. 병목이남으면CUDA worker 또는 streaming geometry adapter를분리비교한다. 2D트랙ID를3D고유객체ID로오인하지않고동적객체를정적맵에영구융합하지않는다.
- HTML에는 architecture diagram·모델역할필터·실시간처리예산계산기·R0–R6단계/후보수락기준·41개직접출처검색·모바일/인쇄CSS를넣었다. 입력FPS/표시FPS/실제추론처리량/관측결과나이를분리한다. 목표 수치는측정결과로채우지않았다. 외부CDN/폰트없이 로컬파일로동작한다.
- 환경 read-only 재확인: branch `vggt_slam_map`, origin SSH `git@github.com:hyunjaeKang/VGGT-SLAM.git`, HEAD9a0e7ba 이후미커밋유지. sandbox doctor는mps=false였으나권한밖동일doctor에서MPS=true/cuda=false. 기본venv의SAM3=false를분리환경검색실패로판단하지않는다.
- 사용자가이번세션전시작한 새90초V3 job `live_20261108T115826_4ffce9d7` / run `video_20261108T195829_755817000`은문서작성중에도진행됐다. 기존server/worker를종료하거나무거운전체테스트·새모델추론을추가하지않았다. 정확한조회시각과변동카운트는`docs/research/handoff_snapshot_20261108.json`에남기고완료판정은다음세션에실제job/저장으로확인한다.
- 문서 검증: 모든HTML id중복/내부anchor/로컬파일링크를검사하고출처41행과외부runtime의존성0을확인했다. JavaScript `node --check`, `git diff --check` 통과. 실제격리Chrome `evidence/plan_review_20261108_01/validation.json`: PC/390px모바일가로넘침없음,모델역할필터·출처검색·예산초과경고·초기계산기·JS예외0 모두통과. desktop/mobile/architecture스크린샷확인. 실제runtime시험이아니라문서의표시·상호작용검증이다.
- 시간계약도계획서에명시했다: 실시간replay는stream monotonic origin에PTS상대시간을대응시키고,offline은ingest→result latency를따로보고한다. 서로다른장치의monotonic clock이나절대walltime·상대PTS를직접빼지않는다.


## V3 8103 사용자 요청 상태 점검 — 2026-11-08 22:35 UTC

- 서버8103상태API/8104frame·smoothAPI/실제파일/프로세스를읽었다. 서버·worker는종료하거나재시작하지않았다. 샌드박스내localhost연결실패는권한밖재조회로정상응답을확인했다.
- 사용자90초job `live_20261108T115826_4ffce9d7` / run `video_20261108T195829_755817000`: decoded2700,고유키프레임2196,submaps275,drop0. 실제VGGT처리종료·manifest completed·poses/PCD저장확인. PCD227654920점/3642478901bytes(약3.39GiB), capture_wall3112.99초(약51분53초),submap p50/p95 11.07/15.98초.
- V3 job은아직state=road이며일반Search disabled. 최종275단계의ROAD worker는1091/2196고유프레임완료(약49.7%)이며status수정과관측파일생성이계속된다. 최근11개새관측간격중앙7.79초. 남은1105프레임을동일속도로단순계산하면약2시간23분이며완료시각보장은아니다. 앞선단계의검사를캐시재사용하므로이전총경과시간만으로잔여시간을추정하지않는다.
- 8104는최신지도프레임2469/2470(중첩포함),source2698/89.93초,600000표시맵점,ROAD누적6492000점,RGB카메라·BEV연결표시를응답했다. 원본MP4캐시는최종전환전이라media=null. ROAD새결과수신시최신프레임으로갱신되는상태이며정지표시는추론중단을뜻하지않는다.
- 측정당시뷰어PID32354는CPU약98%/RSS약7.7GiB,CPU SAM3 worker PID84681는CPU약250%/RSS약6.5GiB. CPU%는코어합산값이다. 반복CachedRun/ROAD 재구성과CPU분할이경합하며입력disparity10으로과거disparity45실험보다키프레임·서브맵·파일이많다. “웹서버가꺼짐”이아니라무거운ROAD후처리+전체ROAD완료를기다리는V3설계가현재병목이다.
- 증거: `evidence/live_status_20261108_01/status.json`, `progress.json`, `review_live_8103.py`. 현상검토만수행했으며V4구현·새모델·새추론은시작하지않았다.
- 추가 품질 신호: inference.log의마지막루프수는252다. 90초고속도로영상에서이연결들이실제재방문인지확인하지않았으므로수용루프수만으로정확도PASS를선언하지않는다. 기존11-06실험은max_loops0/disparity45였으며이번은max_loops1/disparity10이다. 다음품질점검에서loop pair·제약·왜곡·before/after를검토해야한다.


## 2026-11-09 Live V4 구현

계획 기반 독립 V4를 추가했다. 실행: `.venv/bin/python demo.py live4 --port 8105 --viewer-port 8106`. 상주 객체 검출·ByteTrack·도로/하늘 분할·정확한 깊이 프레임 결합·생성 중 검색·증분 지도 뷰어를 제공한다. 상세 구현, 증거 및 미달성 목표: [LIVE_V4.md](LIVE_V4.md). 기존 사용자 수정과 run은 보존했다. R5 장시간/GT 및 R6 조건부 엔진 전환은 미완료다.

검증 추가: 전체 회귀 테스트 `163 passed` (59.98초, 샌드박스 밖 재실행), V4 의미/캐시 테스트14개 통과, `git diff --check` 통과. 초기 샌드박스 실행의 OpenMP SHM 오류 및 V4 재검증의 DINO HTTP504는 환경/외부 접근 실패로 분리 기록했다. 최신 브라우저 재검증: evidence/browser_live_v4_20261109_04.

최신 재실행 `live_20261108T234040_da2ad77b`: 실제6프레임/2서브맵/799486점, 도로6/의미6, 객체모델로딩1회 완료. 전체약266초로 앞선82초보다 느렸다. 최신 timing_summary의 객체p95 약3.12초/도로p95 약15.13초/깊이결합p95 약18.53초이므로 실시간 목표 미달이며 속도 개선 완료로 주장하지 않는다. 최신 기능 경로와 전체회귀163개는 구분하여 판단한다.

재검증04는 생성 완료 후 브라우저 검색 확인 중 CDP timeout으로 끝났으므로 전체 PASS가 아니다. 로그에서 발견한 증분 프레임 선택/시간표 갱신 순서 오류를 수정했고, 서브맵 중복 프레임을 V4에서 제거했다. 추가 회귀 포함 의미/캐시 테스트15개 PASS. 완료 지도를 수정된 뷰어로 다시 열었다. 전체163개 PASS 결과는 이 마지막 두 수정 이전이며 이를 구분한다.

정정: 서브맵 겹침은 query playback_index와 일치하도록 보존해야 한다. 중복 제거 시 도로 관측 인덱스가 어긋남을 재열기 검사에서 발견해 제거 변경을 되돌렸고, 인덱스 보존 회귀 테스트로 대체했다. 소스 고유6프레임/뷰어7개 서브맵 관측이다. 시간표 갱신 순서 수정은 유지한다.

최종 재열기 API 확인: viewer_version=live-v4, frame_count=7(고유소스6+겹침1), camera_available=true, road_points=6000, BEV connectivity cells1630/edges2277. 의미/인덱스 테스트15개 PASS(2.85초). localhost8105/8106 실행 유지.

재열기 브라우저 공통 검사02는 기존 검사기의 `displayed` 상태 텍스트 대기에서 시간 초과했다. API 재열기 응답은 정상이나 브라우저 전체 수용 PASS로 간주하지 않는다. 후속: V4 상태 계약에 맞춘 검사 및 최신 증분 갱신 E2E, R5 장시간·GT 검증, 처리 지연 최적화.


## 2026-11-09 · V5 VGGT-SLAM 전용 + KITTI 영상 + eli5 설명서

- 사용자 요청에 따라 V4 작업을 보존하고 새 V5 controller8107/viewer8108/jobs_root logs/demo_v5_jobs 추가. SEM/ROAD/sky worker0, VGGT깊이·색상점군·자세·서브맵·루프/그래프·저장·뷰어 유지. 루프1기본,0일때만DINO/SALAD로딩/embedding생략.
- V5실제입력너비224/322/378/518,14배수높이/crop/padding/픽셀중심변환계약. 기존버전기본518보존. 로컬VGGT mmap/weights_only/assign 로딩,로컬DINO TorchHub경로,CPU4/OpenCV1,표시preview10000점/기본200k/CPUprojection960x540으로제한. 원시PCD저장에는표시상한미적용.
- 원본KITTI508~1855전체1348장→134.8초 및 V2선택226장→22.6초 H264MP4(1408x376/10fps). source_manifest와ffprobe카운트/SHA256기록. logs/demo_inputs/kitti_closed_loop_508_1855_20261109/. 원본timestamp미사용10fps가정,선택영상시간압축. 원본과V2결과/사용자삭제쿼리보존.
- 모델비교 evidence/v5_resolution_20261109_01: 동일KITTI4장MPS,3회씩(첫회제외2회중앙값),5181.979초/3781.252초/3221.559초/2241.206초.378약1.58x모델속도,작을수록항상빠르지않음.깊이유한/양수100%이나GT정확도아님. V4동시부하있음.
- 브라우저실제6프레임/서브맵3/이동0/루프1: evidence/browser_live_v5_20261109_01(378,21.05초,194480점,2서브맵), evidence/browser_live_v5_518_20261109_01(518,22.38초). 업로드/해상도/카메라/생성완료/worker0/JS예외0 PASS. 두번째는생성중3뷰도PASS. 첫번째생성중화면검사미포착을PASS로추정하지않음. 전체시간향상약6%,V4타데이터실험과배수비교안함. 루프검출0개/전체폐루프미평가.
- 전체회귀174 passed/11.46초,Dashwarning1. V5추가10개. 기존mapping/recording/video controls7개도PASS. `git diff --check` 확인.
- eli5스킬로 USER_GUIDE.html/md/pdf 작성: 버전목적/실행명령/조작/재생vs계산중지/KITTI경로/해상도비용/상대지도한계. HTML목적필터/모바일/인쇄PDF 제공. docs/INDEX,README,CURRENT_STATUS,SESSION_HANDOFF,DEMO_VERSIONS,AGENTS 최신범위갱신.
- 세션시작V3사용자90초작업은completed/ROAD2196확인. 다른V4사용자작업진행중을읽었고중지하지않음. V5자체와버전선택8100만업데이트하여재시작.
- 다음검증: 전체226/1348프레임루프ON/OFF,해상도별독립GT궤적/정합,장시간메모리. 이소량시험은실시간30fps/전체폐루프정확도를보증하지않는다.

- 최종 조작 API검사 evidence/v5_actions_20261109_01: 프레임이동/자유카메라/Reset/BEV줌·패닝·Reset/재생후정지/378실제격자/검색·도로0/버전선택링크/설명서서빙 모두PASS. 설명서브라우저 evidence/v5_guide_20261109_01:5개버전/목적필터/실행안내펼치기/모바일넘침없음/JS예외0 PASS. PDF614KiB 생성. 첫 설명서검사는 접힌V4명령의innerText검사때문에실패했고 실제summary를펼치는동작으로보완해재검증했다.

추가실증: V5너비322/루프0/3프레임/1서브맵 run `video_20261109T182600_236195000`,60858점,약12.67초. DINO/SALAD를로딩하지않는경로로완료했다. `evidence/v5_resolution_20261109_01/correspondence_322.json`: 첫프레임19755점을깊이·K·저장투영행렬로재구성해PCD와비교,XYZ최대오차0/RGB불일치0/원본전처리RGB오차0. legacy오프라인검증기의execution_args/카메라행렬파일가정을비디오config/after스냅샷fallback으로확장하고실제검증했다. 최초CLI --run인자착오 및legacy계약오류 후 수정·재실행PASS; GT정확도판정은아니다.


## 2026-11-09 · V5 재생이6프레임으로끝나는원인확인

8107/api/live read-only확인: 현재열린job live_20261109T093557_8f32eb46은앞6프레임시험지도(max_frames6/고유지도6/submap2),원본22.6초. V5의최대지원프레임이6이라는뜻이아니며 기본max_frames0은전체처리다. 현재설정과기존run설정을혼동하지않도록 작업options의실제제한을상단에‘부분처리지도·앞6프레임제한’으로표시한다. 기존6프레임지도는보존했고새전체추론은시작하지않았다. 전체선택영상은max_frames0/min_disparity0으로새로생성해야226장의지도를재생할수있다.


## 2026-11-09 · 사용자 V5 전체 KITTI 완료/루프 품질 진단

- 8107현재job live_20261109T110040_ad530df7 /run video_20261109T190043_925571000은 completed. 전체1348입력/1348고유키프레임/169서브맵/426.91초/46298495점. 설정378/submap8/disparity0/maxloops1/maxframes0. 현재8108은마지막source1347/134.7초를표시하므로6프레임제한이나초반지도표시문제가아님.
- 실제loop후보92,검증수락84,그래프loop_constraint_added84. 수락중78개는source시간차8~30프레임(0.8~3초)이하근접관측,장거리6개는1311~1319프레임차로마지막과시작부연결. 수락건수가모두독립재방문/정확한제약이라는뜻은아니다. 최근서브맵1개만제외하는기존검색구조를확인했다.
- 최신poses를원본KITTI ID로+507매핑(1..1348→508..1855),GT1276개매칭,단일ProperSim3사후적합ATE RMSE113.895860691m. V2원실행226선택/518/submap16은217개매칭ATE9.948557765m. 조건이달라해상도하나의인과효과로비교하지않는다. 영상전프레임/작은서브맵/낮은해상도·근접제약등이달라졌다. 원시궤적점프도커서전역정합품질실패로판정한다.
- 근거 evidence/v5_closed_loop_review_20261109_01/{summary.json,loop_pairs.json,estimated_original_kitti_ids.txt,evaluation/trajectory_metrics.json,평가그림}. 기존결과/사용자화면/추론서버보존,새추론시작안함. 후속은시간근접후보제외·키프레임선택·표준해상도/서브맵조건의통제실험및GT평가. 단순히더기다리거나수락임계값을완화해해결된다고안내하지않음.


## 2026-11-09 · V5 루프 품질 복구 실험 시작

- 사용자후속요청으로최근source-video10초이내후보를검색전에마스킹하는V5옵션min_loop_seconds추가. 기본기존GraphMap경로는0(비활성),V5신규CLI/API만10초.프레임시간은videoPTS기록에서조회하고없으면failclosed. 가까운best후보를사후에버리지않고더오래된후보를검색한다.
- V5 UI에루프품질우선설정(518/submap16/movement45/loop1/gap10/maxframes0)과최소시간간격입력추가. 이미선별된226장비교실험에서는movement0으로같은선택순서를보존한다. 시간압축선택영상의10초는원본주행10초가아님.
- 회귀 tests/test_slam5.py+test_large_map_io.py 17passed/18.98초. 전체회귀및실제226장실험진행. 증거 evidence/v5_loop_recovery_20261109_01/inference.log. 기존1348장실패run/사용자데이터보존.

- 후속실제실험완료: video_20261109T193118_668535000/226장/15단계/13186136점/CLI geometry84.32초. 1829→508,1855→541의V2동일재방문2쌍수락. GT217매칭/Sim3적합ATE12.56179m. 실패전체1348장113.89586m보다개선됐으나조건동시변경으로시간필터단독효과는미분리. 기존V2PNG9.94856m와도완전히동일하지않다. summary.json과evaluation기록.
- V5완료job이런타임history에즉시반영되지않던문제를update시갱신으로수정하고회귀추가. 종료된V5만재시작하여새지도등록live_20261109T113118_loop_quality를열었다.다른버전/원본/실패결과보존. 초기17개PASS,전체177개PASS/11.77초,history추가후V5테스트14개PASS. 최종전체검사후수치추가예정.

- 최종전체회귀178 passed/10.88초(Dashwarning1). 개선지도브라우저검사 browser_checks.json:마지막source225/카메라/geometry-only/전체보기/JS예외0 PASS, completed_overview.png. GT궤적비교그림에서주경로·재방문형태를확인했으나측량정확도로보장하지않는다. 현재8107은새품질결과,내부8108마지막프레임·자유전체보기로표시.


## 2026-11-09 · V5 Chase View / RGB 갱신 개선

- 사용자요청:자유3D의과도한확대대신RGB카메라뒤에서따라가는Chase버튼,RGB갱신오류확인. V5전용수정,V1~V4/원본지도보존.
- camera-relative위치=-forward*거리+up*0.35거리,진행방향앞을바라보며이동/회전추적. 기록카메라이동중앙값으로상대스케일을정하고거리배율0.5~8 제공,월드up고정없음. RGB Reset/Chase/자유모드를분리,재생중보간camera20Hz사용. Chase근거리clipping/점크기는local이동스케일기준으로조정.
- V5재생시계는server-monotonic하나로고정. 오래된video_clock메시지가전체지도를되감지않도록무시. RGB는별도컨트롤러로분리하여BEV/3D JPEG동시수신실패에묶이지않고,원본디코딩실패·지연시최신RGB JPEG로대체. 세대변경seek는한번만하고디코딩중반복currentTime지정으로프레임준비를방해하지않도록보완.
- Chase수학6개PASS/0.26초(뒤/위/진행방향,임의월드회전시up유지,스케일변환,이상거리거부). 전체184passed/18.04초는추가near/pointsize·seek완료대기미세보완전이며후속브라우저로검증중.
- 첫브라우저01는NumPy bool결과저장오류,02는새generation확인전재시작샘플을취해반복재생판정실패. 실패증거보존. 02에서RGBseek/픽셀변화/Chase이동/legacyclock무시/오류시JPEG갱신/Reset·자유복귀/JS예외0확인. 03은새generation·native디코딩준비확인후재검증.

- 03브라우저검사전체PASS: 정지RGB/native seek(1.9→7.6초),재생픽셀변화,Chaseoffset/이동,지연video_clock되감기방지,끝에서재시작native0.14→1.66초+픽셀변화,RGB오류강제시JPEG변화,Reset/free모드,Chase버튼pressed,JS예외0. viewport1216×328.64로3D뷰경계안에서실제canvas크기도확인했다. near clipping/local점크기보완이후캡처는03에저장. Chase상태문구의불필요한20Hz재전송도같은값검사로제거.

- 최종전체회귀184passed/10.77초. 동일품질지도의뷰어를최종코드로재열었고원래보던부근frame34로복귀·Chase활성화. 기존지도/원본불변,재추론없음.


## 2026-11-09 · 전체1348장 조건 재검증 / V5 선택 검색 복원

- 사용자요청에따라전체1348장을모두키프레임으로넣는518/submap16/gap10/disparity0/maxframes0/loop1새실험시작. evidence/v5_full1348_quality_20261109_01/inference.log. 기존실패/226개선결과보존. 결과확정전성공을주장하지않음.
- V5는생성속도비교를위해검색을숨겼었으나완료후on-demand검색탭/current기본/SAM3실행,RGBmask·box/3Dmask/BEVmask·box/Clear복원. 생성중상주semantic모델없음. 영상RGB위에오버레이가필요할때nativevideo대신annotatedJPEG표시,Chase선택을검색결과선택시유지하도록보완.
- 일반요건·전체입력vs전체키프레임·조건별실험해석은CLOSED_LOOP_GUIDE.md. VGGT-SLAM/ORB-SLAM원논문확인. 10초는보편요건이아닌데모설정임을명시.

- 검색복원실제브라우저검사PASS:현재RGB car1장/SAM3 CPU20.62초/2D9/유효3D4,결과RGBJPEG표시·RGB/BEVmask/box토글·Clear·JS예외0. evidence/v5_search_restore_20261109_01. 전체회귀184passed/17.07초. 생성코어run_os=False와상주semantic worker0은유지.

- 전체1348장모두키프레임실험완료 run video_20261109T212129_410269000:518/16/시간필터10/이동0,526.42초,후보5/수락4(모두시작-마지막장거리),GT1276매칭사후Sim3 ATE59.9954m. 이전113.90m보다는개선이나정합품질해결로보지않음.
- 이어서전체1348입력+자동키프레임선택실험 run video_20261109T213652_654365000:동일518/16/10초,이동80,decode1348/지도224/submaps14/12883120점/80.06초. 후보3/수락1,GT214매칭ATE11.5583m. 원본프레임ID는poses행ID+507로정확히대응,기준없는10개는제외. evidence/v5_full_input_keyframes_20261109_01. 전체입력은모두읽고그중지도에쓸사진을선택한다는구분확인.
- 두실험을새V5작업목록에등록하고기존모든결과보존. 새권장‘KITTI 폐루프 설정’은이영상에서검증한518/16/이동80/간격10(다른영상보편값아님).
- 검색복원02는같은car를새frame141에서새검색한뒤기존frame140결과를잘못재사용하지않음도검증. 실제왼쪽RGB픽셀과서버annotatedJPEG의완전일치,RGB/BEV토글/Clear/JS예외0 PASS. 01 screenshot은새JPEG도착전에촬영됐지만서버RGB파일에는실제마스크/박스확인;02에서표시픽셀까지기다리도록보완.
- V5상태search_ready와완료후검색안내를업데이트하고V5컨트롤러만재시작. 새full-input224지도를기본열기. V1~V4·원본·사용자검색삭제목록보존. 안내서HTML/MD를최신기능으로수정,PDF재생성예정.

- 최신 V5 전용 재생 helper 추가: 완료된영상은decoded video PTS로그끝까지RGB를재생하고마지막추정키프레임이후에는카메라를유지한다. 현재전체입력run에서마지막추정pose134.5초/마지막RGB134.7초구분. 진행중지도는미완료프레임을공개하지않도록기존키프레임끝만사용한다. 단위검증포함전체185passed/10.60초. 첫시도는존재하지않는test_smooth_runtime.py경로지정으로테스트수집실패했고전체검사로재실행완료.
- 새full-input지도브라우저확인:마지막source1345/3D카메라/전체보기/끝RGB시각134.7초/Search탭/JS예외0 PASS. 입력source1346/1347에는새3D추정이없으며이는키프레임선택설명과일치한다.


## 2026-11-09 · Saved Object 모델 및 Search scope 표시

- 공통 query_label에 실제 저장된 모델명(SAM3 / RF-DETR / YOLOE / YOLO26 / YOLO11)과 Search scope(전체 / 현재 RGB / 표본 / PE 후보 / 생성 중), 검사 프레임 수, 유효 3D 관측 수를 함께 표시한다. 예: `car · SAM3 · 전체 224장 · 3D관측 18건 · 123456`.
- SAM3 기존 search.model 문자열도 인식한다. 모델/범위 기록 없는 과거 결과는 `모델 미기록` / `범위 미기록`으로 표시하며 추측하지 않는다. 기존 저장 파일·삭제 목록은 수정하지 않았다.
- 새 SAM3 검색과 V4 resident 검색은 backend를 명시 저장한다. Road는 SegFormer로 구분한다. RF-DETR 표시는 메타데이터 지원이며 RF-DETR 엔진 설치/연결을 뜻하지 않는다.
- 검증: 5모델×5범위 25조합 및 과거 SAM3/메타데이터 누락 확인 PASS. `tests/test_demo_camera_search.py tests/test_live4_semantics.py`:23passed. 공통 함수를 사용하는 V1/V2/V4/V5 목록에 다음 뷰어 시작 시 반영된다. 실행 중 V5는 동일 완료작업 live_20261109T133652_full_keyframes를 /api/open으로 다시 열어 새 코드 적용을 요청했다(지도 재추론 없음).


## 2026-11-09 · V5 검색 모델 선택

V5 우측 `검색 · Search` 탭의 Query 위에 `Search model`을 추가했다. SAM3(기본)/YOLOE/YOLO26/YOLO11은 실제 선택 엔진으로 검색한다. RF-DETR은 엔진·가중치 미설치로 `준비 필요` 표시, 선택 후 검색 시 명확하게 안내하고 다른 모델로 대체하지 않는다. 모델을 바꾸면 지원 클래스·자유텍스트 여부·RGB/3D/BEV Mask와Box·Search scope 안내가 바뀐다. YOLO26/11은 COCO 학습클래스만, YOLOE/SAM3은 텍스트 대상 검색이다. Road 전체 표면 처리는 별도이며 일반 YOLO 고정클래스 검색은 road/printer를 지원하지 않는다.

검색 worker는 --backend(기본sam3)로 분기한다. SAM3 의존성은 해당 분기에서만 import하며 기존 V1~V4 호출은 기본 유지. YOLO 계열은 .venv-v4와 로컬 가중치, PersistentDetector CPU를 사용한다. 한 이미지의 여러 검색어는 추론을 공유하며 클래스별 마스크를 분리한다. 캐시 identity에 backend/가중치hash/classes/confidence/size를 넣어 모델 간 캐시 혼용을 막는다. 저장 결과는 실제 backend/model과 scope를 기록하며 기존 query_label에서 표시한다.

실제 같은 KITTI 현재프레임(playback34) car검색:YOLO26/11/YOLOE 모두 completed,각2D1/유효3D1. `evidence/v5_search_models_20261109_01/results.json` 및 모델별log. 전체회귀187passed/31.48초. V5 동일 완료작업을 다시 열어 메뉴 적용; 재추론 없음. RF-DETR 실제추론과 새 모델간 정확도·속도우열은 검증하지 않았다. graft build 갱신.

- 실제 Chrome 검증 PASS: Search model 메뉴/5모델 옵션/SAM3 안내/YOLO26 선택 후 COCO 안내 전환/Search scope/JS예외0. 증거 browser_checks.json 및 search_models.png.


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


## 2026-11-10 · 데모 변경 커밋 준비

macOS .DS_Store를.gitignore에추가(하위폴더포함). 누적V3~V5/다중모델검색/전체클래스/색상Legend/독립3D토글/메뉴숨김/문서·검증자료를커밋대상으로확인했다. 관련없는TerraScene은보존하고커밋제외. 입력영상·모델·실행run·가상환경은기존ignore유지. 검증증거의작은JSON/log는문서참조가깨지지않도록명시포함한다.

- 커밋전전체회귀194passed/31.27초. .DS_Store는루트/하위폴더모두ignore확인. 소스/문서공백검사통과;원본실패검증log의출력공백은증거보존을위해유지. 커밋대상280개파일,TerraScene/.DS_Store제외확인.


## 2026-11-10 · web_app 폴더 등록

사용자요청으로미추적TerraScene/을web_app/으로이름변경하고시제품전체12파일을커밋대상으로추가했다. TerraScene브랜드/독립HTML파일명은보존했다. package_deliverables.py의이전/workspace고정출력을프로젝트내deliverables로변경하고ZIP루트는web_app으로맞췄다. 산출물폴더ignore추가. 기존validation.json/HTML내용보존,dist필수파일은전역ignore에도명시stage. 검증:Node문법2개/core8개/interface7개PASS,Python문법PASS,임시복사본패키징ZIP12항목/web_app루트PASS. 원본사용자산출물을재생성하지않았다.


## 2026-11-10 · web_app 영어·한국어 병기

사용자확인범위는web_app화면·도움말·README. 버튼/패널/상태/범례/시나리오/캔버스객체이름/오류·알림/영상열기/내보내기/접근성문구를영어·한국어동시표시로변경. 한국어객체검색지원,수치·시간·단위/파일명/코드식별자/기계용내보내기스키마유지. README도양언어로작성. 개발계획서본문과V5앱은범위밖이라보존했다. 긴문구는줄바꿈을지원하고단일HTMLUI도갱신.

기존core8/interface7(양언어연결상태·한국어객체필터검사보완)PASS,Node문법PASS,패키징PASS. 실제Chrome데스크톱1600/모바일390가로넘침없음/한국어객체검색/양언어도움말·오류·내보내기/단일HTML로드/JS예외0. 표시문구영문단독감사결과0개(브랜드·수치·단위제외). evidence/web_app_bilingual_20261110_01/의checks.json,visible_text_audit.json,desktop.png,mobile.png,help.png. 시나리오옵션은양언어가한줄에보이도록간결하게정리했다.
