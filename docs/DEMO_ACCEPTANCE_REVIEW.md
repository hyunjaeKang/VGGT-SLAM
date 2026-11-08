# 데모 변경분·객체 박스 최종 검토

검토: 2026-11-06 UTC. 기준 HEAD `3031d6d9340db249b0c7a458fe4e3cef07ec02c9`와 현재 미커밋 변경분. 입력·종료·검색·마스크/깊이 좌표 변환·저장·평가·캐시 표시 경로를 중심으로 코드와 실제 증거를 대조했다. 기존 데이터/결과, `.DS_Store`, `TerraScene/`는 보존했다. 커밋·환경 재구성은 이번 범위에 포함하지 않는다.

## 판정

- **선택된 지원 경로의 기능 실증: PASS.** 일곱 기능의 실제 증거 파일이 존재하고 주요 수치와 일치한다.
- **객체 기하 일관성: PASS.** 차량 17개·나무 3개의 재실행 마스크가 기존 저장 마스크와 모두 동일하며, 복원된 confidence-valid 지지점이 기존 OBB에 100% 포함된다. 이는 독립적인 정확도 증명이 아니다.
- **객체 치수/위치 정확도: 미평가.** 차량 `#1`, `#5`는 극단값에 민감해 별도 검토가 필요하다. 20개 박스 전체를 정확도 합격으로 표시하지 않는다.
- **배포·환경 재현성: 이번 범위 밖.** CPU open-set은 로컬 두 환경의 패키지를 재사용한다. 새 머신의 단독 설치, GPU/MPS open-set, RealSense 장치 및 전체 벤치마크는 검증하지 않았다.

## 발견 후 수정한 코드 결함

| 중요도 | 결함 | 수정·검증 |
|---|---|---|
| P1 | 점 수만 충분하면 동일점/직선/평면에서도 얇은 OBB를 생성 | `boxes_from_masks`에서 centered support의 수치 rank가 3 미만이면 제외하고 사유 저장. rank 0/1/2 회귀 통과 |
| P1 | camera 해제 예외가 worker 대기·로그 정리를 건너뛸 수 있음 | nested finally로 worker/query writer를 먼저 정리. 의도적 release 오류 회귀에서 worker 완료와 lock 해제 확인 |
| P2 | 3D 지지점이 부족한 검출의 원래 마스크가 사라짐 | 제외된 2D mask도 evidence에 저장해 판단 사유와 함께 재검토 가능 |
| P2 | optional scores가 없으면 `float(None)` 오류 | score=None을 유지. 정상 3D box 생성 회귀 통과 |

일반 `compute_obb_from_points`의 퇴화 입력 처리 자체는 유지한다. 실제 객체 검색의 모든 production 호출은 rank 검사 후 이 함수를 호출하는 공통 경로를 사용한다. Rank 검사는 정확한 기하 퇴화를 막으며, 깊이 잡음/외곽점/실제 치수 오류를 검증하는 기준은 아니다.

## 기능 증거 대조

| 기능 | 확인한 실제 증거 | 해석 한계 |
|---|---|---|
| RGB/depth/색상 점군 | [PandaSet 픽셀·3D 대응](../logs/demo_runs/s02_pandaset17_mps_20261030_01/evidence/correspondence_first_frame_v2.json) | 첫 프레임 대응 검사이며 GT 깊이 정확도 아님 |
| 자세·궤적 | [TUM 평가](../logs/demo_runs/s10_tum_xyz33_20261105_01/evaluation/trajectory_metrics.json) | RGB 33개, fitted Sim(3) ATE 0.023689819m, 전체 benchmark 아님 |
| 서브맵 연결 | [BDD 비디오 무결성](../logs/demo_runs/video_20261105T051812_966691000/evidence/video_integrity_01/validation.json) | 900 decoded, 35 poses, 9 submaps, 3 drops |
| 루프·최적화 | [루프 trace](../logs/demo_runs/s03_kitti_loop_on_20261031_01/evidence/loop_trace.json), [ON/OFF 비교](../logs/demo_runs/s03_kitti_loop_on_20261031_01/evidence/ate_comparison.json) | 두 실제 루프, 각각 fitted ATE 9.949/16.164m; 일반 개선 보장 아님 |
| 객체 검색 | [live 검색 검증](../logs/demo_runs/video_20261106T011557_281290000/evidence/live_query_validation.json) | CPU·offline-paced capture, car17/tree3/elephant0; 실시간 처리량 아님 |
| 비디오·제어 | [실제 GUI](../logs/demo_runs/video_20261105T053815_749770000/evidence/gui_controls_01/browser.json), [VFR PTS](../logs/demo_runs/video_20261106T001912_118994000/evidence/pts_propagation.json) | RealSense 하드웨어/모든 codec 지원 증거 아님 |
| 시각화·저장·평가 | [TUM 브라우저](../logs/demo_runs/s10_tum_xyz33_20261105_01/evidence/browser_tum_02/browser.json), [검색 캐시 브라우저](../logs/demo_runs/video_20261106T011557_281290000/evidence/browser_cached_queries_01/browser.json) | first_render_seconds는 고정 8초 대기 후 검사 시각으로, 최초 draw의 정밀 측정값 아님 |

이전 [CODE_REVIEW.md](CODE_REVIEW.md)는 2026-10-30 시점의 역사 기록이다. 그 문서의 당시 SAM3/TUM 미실행 상태를 현재 상태로 해석하지 않는다.

## 차량·나무 품질 검토

VGGT 전체 추론을 반복하지 않고 live run의 정확한 두 선택 RGB에 SAM3만 재실행했다. 기존 raw query/box 파일은 수정하지 않았다. 저장 depth/confidence와 검색 당시 snapshot을 사용해 3D 지지점을 재구성하고 새 rank 정책을 적용했다.

| 대상 | 재실행 마스크 | 기존/새 유효 OBB | 제외 | 기존 저장 mask 동일 | 기존 OBB 지지점 포함 |
|---|---:|---:|---:|---:|---:|
| car | 19 | 17 / 17 | 2: 지지점 0 | 17 / 17 | 각 100% |
| tree | 8 | 3 / 3 | 4: 지지점 0, 1: 지지점 6 | 3 / 3 | 각 100% |

유효 20개는 모두 rank 3이다. 마스크 contact sheet에서 차량/수관과 겹치는 영역, confidence 필터로 제거된 영역을 확인했다. 먼 물체의 작은 마스크와 화면 밖으로 잘린 차량은 관측이 제한된다.

### 정확도 합격을 보류한 두 차량

| 검출 | 지지점 | 저장 OBB 부피 / 각 축 2–98% support envelope 부피 | 판단 |
|---|---:|---:|---|
| car #1 | 5,635 | 75.52 | 화면 오른쪽 밖으로 일부 잘린 차량. 소수의 깊이 극단값으로 box가 크게 확장됨 |
| car #5 | 8,827 | 25.26 | 가까운 pickup의 지지점에 극단값이 있어 box가 대부분의 support보다 커짐 |

위 비율은 **GT 부피 오차가 아니다**. 2–98% envelope는 진단용이며 모델 박스를 자동 교체하지 않았다. `ratio > 10`은 리뷰 대상을 찾기 위한 휴리스틱이며 보정된 신뢰도/합격 기준이 아니다. 향후 강건한 box fitting을 비교하려면 실제 경계 보존과 외곽점 제거의 tradeoff를 따로 평가해야 한다.

- [차량 전체 mask/support contact sheet](../logs/demo_runs/video_20261106T011557_281290000/evidence/quality_review_01/car_mask_review.png)
- [나무 전체 mask/support contact sheet](../logs/demo_runs/video_20261106T011557_281290000/evidence/quality_review_01/tree_mask_review.png)
- [car #1 3D 극단값 진단](../logs/demo_runs/video_20261106T011557_281290000/evidence/quality_review_01/car_01_expansion.png)
- [car #5 3D 극단값 진단](../logs/demo_runs/video_20261106T011557_281290000/evidence/quality_review_01/car_05_expansion.png)
- [검출별 수치·제외 사유](../logs/demo_runs/video_20261106T011557_281290000/evidence/quality_review_01/quality_audit.json)

## 최종 검사

- `.venv/bin/python -m pytest -q`: **94 passed**, 기존 Dash warning 1개, 23.09초.
- `uvx --offline ruff check --select E9,F63,F7,F82 main.py main_realtime.py scripts tests vggt_slam`: All checks passed.
- compileall, `git diff --check`, graft build 통과.
- 실제 모델 재실행과 합성 rank/release-error 회귀를 구분해 기록했다. 이번 변경 후 live 세션 전체를 다시 실행한 것은 아니며, 공통 mask/OBB 경로에 실제 27개 replay mask를 적용했다.
