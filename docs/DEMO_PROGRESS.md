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
| F1 RGB/depth/점군 | NOT_RUN | 일부 실험 완료; 전체 합격 조건 검증 진행 중 |
| F2 자세 | NOT_RUN | 자세 파일 생성됨; 데모 화면과 합격 조건 미검증 |
| F3 서브맵 | NOT_RUN | 전체 연결 근거 및 화면 미검증 |
| F4 루프/최적화 | NOT_RUN | 실제 재방문 2건·전후 trace 검증됨; 통합 UI 미검증 |
| F5 PE/SAM3 검색 | BLOCKED | SAM3 미설치; 호환성 미검증 |
| F6 비디오 점진 입력 | NOT_RUN | 입력 경로 미구현; RealSense 실증 제외 |
| F7 시각화/평가 | NOT_RUN | 통합 데모 미구현 |
