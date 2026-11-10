<!-- session-context: 2026-11-08 -->
> **현재 상태 안내 (2026-11-08):** 이 문서의 과거 실험·수치·코드 리뷰는 당시 범위의 기록입니다. 최신 구현·버전·검증은 [CURRENT_STATUS.md](CURRENT_STATUS.md), 다음 세션의 실행 순서는 [SESSION_HANDOFF.md](SESSION_HANDOFF.md), 지도 생성 중 객체 탐색 설계는 [HTML 계획서](../26.11.09.VGGT_SLAM.Plan.html)를 먼저 확인하세요. V4는 아직 미구현입니다.

# VGGT-SLAM 2.0 코드 검토 및 실행 기록

> 아래는 2026-10-30 당시의 기록이다. 이후 데모 변경분과 실제 SAM3/TUM 검증의 최종 검토는 [DEMO_ACCEPTANCE_REVIEW.md](DEMO_ACCEPTANCE_REVIEW.md)를 참고한다.

검토일: 2026-10-30. 저장소의 Python 모듈 16개, 설치 스크립트, README 및 TUM 평가 스크립트를 검토했다. 기존 사용자 변경인 `.gitignore`, `.claude/`, `.ignore`, `AGENTS.md`는 보존했다. 소스 위치와 호출 관계는 graft로 확인했다.

## 구조와 실행 흐름

1. `main.py`는 입력 영상을 숫자 순서로 정렬하고 `FrameTracker.compute_disparity`로 키프레임을 선택한다. 광류 구현은 OpenCV의 Lucas–Kanade이며 기존 CLI의 RAFT 표기를 바로잡았다.
2. `Solver.run_predictions` (`vggt_slam/solver.py:303`)는 겹치는 프레임 1장을 포함하는 서브맵을 만들고 SALAD 검색 벡터 및 VGGT 깊이/카메라 예측을 계산한다.
3. `Solver.add_points` / `add_edge` (`vggt_slam/solver.py:123,202`)는 서브맵 간 스케일과 프레임별 변환을 추정해 GTSAM SL(4) 그래프를 구성한다. SALAD 후보는 VGGT의 추가 영상 쌍 추론으로 검증한다.
4. `PoseGraph.optimize` (`vggt_slam/graph.py:80`)가 그래프를 최적화하고, `Submap`과 `GraphMap`이 점/카메라를 세계 좌표로 변환한다. `Viewer`는 Viser로 표시하고 `GraphMap.write_poses_to_file`은 궤적을 내보낸다.
5. `main_realtime.py`는 RealSense 영상을 저장하고 추론을 별도 스레드에서 실행한다. `--run_os`는 별도의 PE/SAM3 모델을 추가한다.

주의: **공식 VGGT 대신 SPARK 포크가 필요하다.** 포크의 `unproject_depth_map_to_point_map`은 docstring과 달리 카메라 좌표를 반환한다. 그래프의 프레임별 변환은 이 동작을 전제로 한다. 해당 계약을 회귀 테스트에 추가했다.

## 발견하고 수정한 문제

| 우선순위 | 위치 | 문제와 수정 |
| --- | --- | --- |
| P1 | `vggt_slam/loop_closure.py:53`, `solver.py:303`, 양쪽 진입점 | CPU 분기가 있어도 SALAD와 CUDA capability 조회가 CUDA를 강제했다. 공통 장치 선택을 추가하고 CUDA/MPS/CPU를 전달한다. |
| P1 | `scripts/patch_vggt.py`, `vggt_slam/runtime.py` | SPARK VGGT는 입력을 무조건 bfloat16으로 바꿨다. 설치 시 확인 가능한 작은 패치를 적용해 모델 dtype을 따르게 한다. CPU/MPS는 float32, CUDA는 지원 여부에 따라 bfloat16/float16을 사용한다. |
| P1 | `vggt_slam/loop_closure.py:63` | 필요한 SALAD 체크포인트가 없으면 첫 실행부터 실패했다. 공식 릴리스에서 PyTorch 캐시로 자동 다운로드한다. CUDA에 저장된 가중치도 CPU에서 읽는다. |
| P1 | `vggt_slam/solver.py:136,145` | 루프 연결에서도 이전 서브맵의 마지막 / 현재 서브맵의 첫 카메라 보정값을 사용했다. 실제 매칭된 프레임의 값을 사용한다. 현재 프레임 confidence에도 현재 서브맵의 임계값을 적용한다. |
| P1 | `evals/eval_tum.sh` | evo 실패나 RMSE 파싱 실패가 0으로 기록되어 잘못된 좋은 결과를 만들 수 있었다. 실패 시 중단하고 유한한 비음수 값을 검증한다. 데이터 경로와 도구 유무도 확인한다. |
| P2 | `main.py:49` | 잘못된 폴더/빈 폴더도 모델을 먼저 로딩한 뒤 실패했다. 입력을 먼저 검증하고 이미지 확장자 및 읽기 실패를 검사한다. |
| P2 | `main.py:122` | 마지막 입력이 키프레임으로 선택되지 않으면 겹침 프레임만으로 불필요한 서브맵을 만들 수 있었다. 새 키프레임이 남아 있을 때만 마지막 서브맵을 처리한다. |
| P2 | `main_realtime.py:267,304` | 실시간 backlog 절단 시 공유 프레임을 잃고 종료 시 남은 키프레임을 버렸다. 공유 프레임을 유지하고 남은 프레임을 마지막에 처리한다. 짧은 캡처의 종료 처리는 mock 카메라로 검증했다. |
| P1 | `main_realtime.py:83` | worker의 추론 실패를 출력만 하고 캡처를 계속했다. 오류 큐로 메인 루프에 전달해 중단하며, 실패한 결과를 정상 로그로 저장하지 않는다. 잠금 해제와 오류 전달을 테스트했다. |
| P2 | `vggt_slam/map.py:138` | 겹침 프레임의 동일 timestamp가 궤적에 중복 기록됐다. 프레임별 한 행만 내보내며 행렬 인덱스는 계속 올바르게 진행한다. |
| P2 | `main.py`, `main_realtime.py` | 의미 검색에서 `q`로 반환하면 로그 저장을 건너뛸 수 있었다. 검색 전에 결과를 저장한다. 확장자 없는 로그 경로도 점군 출력이 궤적을 덮어쓰지 않게 한다. |
| P2 | `vggt_slam/graph.py:77` | `get_projection_matrix`가 존재하지 않는 `projection_matri`를 반환했다. 반환 변수명을 수정하고 실제 GTSAM 최적화 후 역행렬을 확인했다. |
| P2 | `vggt_slam/map.py:42` | 모든 의미 유사도가 음수이면 검색 결과가 초기값에 머물렀다. 최저값에서 시작하고 검색할 벡터가 없으면 명시적으로 실패한다. |
| P2 | `vggt_slam/scale_solver.py:15` | 깊이가 0/NaN인 점이 스케일을 NaN/Inf로 오염시킬 수 있었다. 유효한 양의 대응점만 사용하고 모두 무효하면 중단한다. |
| P2 | `vggt_slam/frame_overlap.py:36` | 광류 추적 실패 시 None을 참조했다. 키프레임을 재초기화하며 점별 변위도 명시적으로 2차원 벡터 기준으로 계산한다. |
| P2 | `setup.sh`, `requirements.txt`, `README.md` | 설치 스크립트가 재실행에 실패하고 선택 기능도 항상 설치했다. 활성 Python을 일관되게 쓰고 재실행을 지원하며 PE/SAM3를 선택 설치로 분리했다. VGGT/PyTorch와 맞도록 NumPy를 2 미만으로 제한했다. 존재하지 않는 7-Scenes 스크립트 안내도 수정했다. |

## 남은 검토 사항과 검증 범위

- **장시간 시퀀스 메모리** (`vggt_slam/solver.py:321`, `submap.py:46`, `map.py:171`): 모든 영상과 고밀도 점을 유지하고 내보낼 때 전체 점군을 다시 합친다. `--vis_voxel_size`는 화면 표시만 줄인다. 대규모 데이터는 GPU/CPU 메모리 제한과 점군 스트리밍 저장을 별도로 검토해야 한다.
- **버전 재현성** (`requirements.txt`, `setup.sh`): 대부분의 패키지와 외부 저장소 기본 브랜치가 고정되어 있지 않다. 이번 환경의 전체 패키지 목록은 `logs/environment.txt`에 기록했다. 배포에는 플랫폼별 lockfile과 외부 저장소 commit 고정이 권장된다.
- **선택 기능**: 실제 RealSense 장치, SAM3/PE의 모델 접근 권한, 외부 TUM 데이터가 제공되지 않아 실장치 캡처, 개방형 객체 검색, APE 수치는 검증하지 않았다. 해당 기능의 성공을 기본 office_loop 실행 결과로 추정하면 안 된다.
- **수치 품질**: 실제 예제 완주는 실행 가능성 확인이다. CUDA 저정밀 실행과 MPS float32 결과가 완전히 같거나 논문의 정확도/실시간 성능을 재현한다고 주장하지 않는다.

## 실행 환경

- Apple Silicon, macOS 27.0.1, Python 3.11.12, MPS.
- PyTorch 2.3.1 / torchvision 0.18.1 / NumPy 1.26.4 / Open3D 0.20.0 / Viser 0.2.23.
- GTSAM develop: `4.3.2.dev202610301701` (`SL4`, `PriorFactorSL4`, `BetweenFactorSL4` 확인).
- SPARK VGGT: `6e6e16107b88e8e76c751826af10d4295d87ecd2` + dtype 패치.
- SALAD: `33ca9c0ca1e10cbb21efc0d6a5fcb6d45688e42d`.
- Open3D의 macOS wheel에 필요한 Homebrew `libusb`를 설치했다.
- PyTorch 2.3 MPS의 누락된 bicubic 연산은 CPU fallback을 사용한다. 진입점에서 환경변수 기본값을 설정한다.

## 재실행

```bash
./scripts/run_office_loop.sh
```

브라우저: `http://localhost:8080`. 완료 후에도 viewer가 유지되며 Ctrl+C로 종료한다. 로그를 포함해 직접 실행하려면:

```bash
.venv/bin/python -u main.py --image_folder office_loop --max_loops 1 \
  --vis_map --keep_alive --log_results --log_path logs/office_loop_poses.txt \
  > logs/office_loop_run.log 2>&1
```

검증 명령:

```bash
.venv/bin/python -m pytest -q tests
.venv/bin/python -m pip check
bash -n setup.sh scripts/run_office_loop.sh evals/eval_tum.sh
git diff --check
```

회귀 테스트에는 실제 GTSAM 최적화, 매칭 프레임 보정값, 중복 timestamp 제거, 스케일의 무효점 처리, 광류 실패, 음수 의미 검색, 마지막 서브맵 배치, 빈 입력 조기 실패, mock 카메라의 짧은 세션 flush, VGGT 포크 좌표 계약을 포함한다. 테스트는 모델 다운로드 없이 실행된다.

## 실제 office_loop 검증 결과

기본 `--submap_size 16`, `--max_loops 1` 설정으로 전체 실행을 마쳤다.

| 항목 | 결과 |
| --- | --- |
| 입력 영상 | 473장 |
| 선택한 키프레임 / 저장한 궤적 | 286장 / 286행 |
| 일반 서브맵 | 18개 |
| 루프 클로저 | 1개, 루프 서브맵 포함 총 19개 |
| 처리 시간 | 273.53초 (모델 로딩 및 마지막 파일 저장 시간 제외) |
| 출력 점군 | 32,681,124점, 522,898,172 bytes |
| 궤적 검사 | 전체 유한값, frame ID 중복 없음/오름차순, quaternion 단위 길이 |
| 점군 검사 | PCD 헤더/바이너리 크기 일치, 모든 XYZ 유한값 |
| Viser | `http://localhost:8080`, HTTP 200, 완료 후에도 실행 유지 |
| 회귀 테스트 | 20개 통과 (외부 Dash pytest 플러그인 deprecation 경고 1개) |
| 정적 검사 | Ruff `E9,F63,F7,F82` 통과 |
| 환경/스크립트 | `pip check`, shell 구문 검사, `git diff --check` 통과 |

산출물은 `logs/office_loop_run.log`, `logs/office_loop_poses.txt`,
`logs/office_loop_poses_points.pcd`, `logs/validation.json`, `logs/tests.txt`에
있다. `logs/`는 git에서 제외되므로 이 파일들은 현재 워크스페이스에만 존재한다.
모델은 사용자 PyTorch 캐시에, 예제 영상은 `office_loop/`에 준비되어 있다.

새로운 회귀 테스트는 TUM 평가에서 evo 실행 실패, RMSE 누락 및 NaN을
정상적인 RMSE 0으로 기록하지 않는지도 가짜 CLI로 검증한다. 실제 TUM APE
측정을 수행한 것은 아니다.

## 후속 구조 검토 안내 — 2026-11-08

현재 `main_realtime.py`는 video_file backend·PTS·offline/realtime pacing·기록·최적화 스냅샷을 지원한다. SAM3 실제 검색과 TUM/evo33매 실험도 후속 세션에서 수행됐으므로 위 초기 미실행 상태는 현재 상태가 아니다. V3 supervisor는 이 추론 경로와 분리 CPU 검색 worker를 관리한다. MOV Display Matrix와 자유 overview축,실제 chooser click 경로도 보정했다.

다음 검토 대상은 새 V4의 상주 worker/증분 관측, frame_uid·map revision 계약,동적 객체 분리,직접 자식 외 검색 worker 종료·고아 상태,장기 메모리/대기열 계측이다. 이 항목들은 이번 문서 세션에서 production 코드를 수정하거나 미검증 lifecycle 결함을 확정했다는 뜻이 아니다.
