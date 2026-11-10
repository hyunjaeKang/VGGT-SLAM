<!-- session-context: 2026-11-08 -->
> **재개 지침 갱신:** 아래는 10-30 원계획/프롬프트의 보존본입니다. S00–S12의 선택 경로 실증과 V1/V2/V3 구현·MOV 회전 보정까지 진행됐으므로 처음부터 다시 시작하지 마세요. [SESSION_HANDOFF.md](docs/SESSION_HANDOFF.md)와 [CURRENT_STATUS.md](docs/CURRENT_STATUS.md)가 최신 상태이며, 다음 과제는 [26.11.09.VGGT_SLAM.Plan.html](26.11.09.VGGT_SLAM.Plan.html)의 V4 R0 측정부터입니다. 과거 “코드/서버를 시작하지 않았다” 문구는 작성 당시의 기록입니다.

# Terra / Luna 실행용 인계 프롬프트

작성: 2026-10-30. 이 문서는 모델을 변경한 다음 제출하는 실행 지시다.
권장 모델: **GPT-6.1 Terra**, reasoning Medium 시작. 복잡한 좌표·회귀·스레드 문제에서 지원되는 High 사용.
대안: **GPT-6 Luna**, reasoning High, 아래 단일 단계 프롬프트로 작업 범위를 좁힌다.
모델 메뉴는 사용자가 변경한다. 에이전트가 자동으로 모델을 바꾸거나 하위 에이전트를 만들지 않는다.

## 1. 추천 시작 프롬프트 — 그대로 복사

```text
현재 프로젝트의 VGGT-SLAM 전체 기능 데모를 구현하고 실험해줘.

프로젝트 루트:
/Users/hyunjae.kang/2026_opensrc/VGGT_SLAM/vggt_slam_map

먼저 AGENTS.md와 temp_VGGT_SLAM_Plans.26.10.30.md를 읽고, 구현을 시작해줘.
기존 docs/DEMO_PROGRESS.md가 있으면 완료 증거를 확인하고 미완료 단계부터 이어가고,
없으면 계획의 S00 현황 진단부터 시작해.

목표는 하나의 로컬 Viser 프로그램으로 다음 일곱 기능을 실제 증거와 함께 보여주는 것이야.
1. RGB·깊이·신뢰도와 밀집 색상 점군
2. 프레임별 카메라 위치·방향·궤적과 저장
3. 서브맵 분할·겹침·연결 제약
4. 실제 재방문 루프 후보·검증·제약·최적화 전후 비교
5. 실제 PE/SAM3 텍스트 객체 검색과 RGB 마스크·3D OBB
6. 비디오 파일(MP4/MOV 등) 디코딩 입력과 점진 지도 생성, EOF·Pause·Step·Stop
7. Viser 시각화·PCD/TUM 저장·정확한 대응을 사용한 궤적 평가
BEV·표면 높이·표면 등고선은 별도 부가 기능으로 연결해.

이제 모델 전환 후 실행하는 요청이므로 계획만 반복하지 말고 구현·테스트·소량 실험을 진행해.
S00→S12를 의존성 순으로 작게 완성하고, 단계마다 관련 검증을 통과한 뒤 다음으로 진행해.
루틴한 파일 수정·테스트·다음 단계 진행을 매번 나에게 재승인받지 마.
한꺼번에 대규모 리팩터링하거나 8.4km 전체 데이터를 재추론하지 마.

중요한 기존 상태:
- PandaSet 003: /Users/hyunjae.kang/9000_Data/9002_ExpData/pandaset/003/camera/front_camera
  RGB 80장. 기존 결과와 설명은 docs/PANDASET003_TEST.md.
- KITTI-360: /Users/hyunjae.kang/Downloads/2013_05_28_drive_0000_sync/image_00/data_rect
  기존 전체 복원은 약 2.12억 점, 정렬 ATE RMSE 321.266m로 전역 정합 실패 사례야.
  docs/KITTI360_0000_RUN.md와 기존 logs를 보존해.
- 기존 KITTI 루프 후보 508↔1826은 기준 위치로 검증되어 있어.
  두 이미지만 이어 붙이지 말고 재방문을 포함하는 연속 구간을 확인·선택해.
- PandaSet 기존 ON/OFF ATE는 0.558m/0.290m이고 기존 제약은 실제 재방문 사례가 아니야.
  루프가 반드시 정확도를 높인다는 전제로 실험하거나 결과를 고르지 마.
- 현재 기본 .venv는 torch 2.3.1 MPS 기반. SAM3/pyrealsense2/evo가 설치되었다고 가정하지 마.
  examples/kitchen도 현재 없어. 실제 환경·checkpoint·장치 접근부터 확인해.
- 기존 테스트 기록은 47개 통과. 사용자 수정이 많은 작업 트리이므로 reset/clean/임의 commit 금지.

구현 원칙:
- 코드 위치는 graft부터 조회하고 변경할 심볼은 callers --depth all로 영향 확인.
- 기존 Solver·Camera·PCD 스트리밍·평가 helper를 재사용해. 별도 SLAM 엔진은 만들지 마.
- 신규 demo.py와 vggt_slam/demo/는 계획상의 산출물이며 현재 있다고 가정하지 마.
- view 모드에서는 VGGT/SAM3 checkpoint를 로드하거나 다운로드하지 마.
- 매 run은 logs/demo_runs/<run_id>/에 새로 저장하고 기존 결과를 덮어쓰지 마.
- event JSONL·manifest·frame ID·원본 timestamp·좌표계·모델·device·source mode를 명시해.
- 점군 표시 기본 30만·최대 200만 점. 전체 큰 PCD는 memmap 유지하고 중복 복사하지 마.
- 최적화 전후는 같은 시점·같은 노드 집합의 실제 homography로 비교해.
  projective homography를 rigid camera pose로 대체하지 마.
- PCD만으로 객체 검색을 복구할 수 없으므로 embedding·RGB·픽셀 depth/3D 대응·변환 cache를 준비해.
- 검색 결과는 actual model→선택 RGB→mask→valid 3D점→OBB로 이어져야 해.
  부족·퇴화한 점에서는 box를 만들지 말고 사유를 저장해.
- SAM3 호환 때문에 기본 .venv를 일괄 upgrade하지 말고 필요하면 별도 환경을 사용해.
- RealSense는 사용자 요청으로 비디오 파일 입력으로 대체했어. 장치·SDK 설치는 필수가 아니야.
  실제 비디오 디코딩→순차 RGB 입력→점진 추론→새 지도 반영→EOF/Stop 저장을 검증해.
  offline-paced를 기본으로 하고 realtime-paced에서는 backlog/drop과 실제 처리량을 표시해.
  PTS가 없으면 frame_index/FPS를 근사 timestamp로 명시하고 VFR·잘못된 FPS를 처리해.
  점진 추론 도중 임의 seek는 금지하거나 새 세션으로 reset하고, EOF에서 재연결·자동 반복하지 마.
  비디오가 없으면 이미지 시퀀스에서 MP4 fixture와 원본 frame/GT 대응 sidecar를 만들어 검증해.
  일반 비디오에 GT가 없으면 ATE N/A야. 캐시 재생과 비디오 입력 추론을 구분해.
  원래 RealSense 기능을 실제 검증했다고 보고하지 마.
- 라이브 종료 시 worker·capture·남은 프레임·원자적 저장을 안전하게 마무리해.
- GT는 평가에만 사용해. frame index를 TUM timestamp 초로 오해하지 마.
- graph error 감소·루프 수락·ATE 개선은 서로 다른 지표로 보고해.
- surface contour를 검증된 지면/지형도라고 부르지 마.

검증·진행:
- 합성/모의 테스트와 실제 모델·브라우저·비디오 입력 실증을 분리해.
- 작은 입력→80장→선정한 루프 구간 순으로 실험해. UI 수정 때문에 재추론하지 않도록 cache를 저장해.
- 실제 Chrome에서 WebSocket·타임라인·점 수·서브맵·전후 토글·검색/Clear·Stop을 확인하고 증거를 저장해.
- docs/DEMO_PROGRESS.md에 단계, 변경, 실행 명령, 결과, 증거, 미완료 원인, 다음 작업을 갱신해.
- 기능별 PASS/FAIL/BLOCKED/NOT_RUN과 실제 evidence 경로를 기록해.
- 외부 조건에 막히면 필요한 비디오/접근권한/데이터를 구체적으로 알리고,
  가능한 독립 기능을 계속 완성한 뒤 그 조건만 남겨. 실패를 성공으로 바꾸지 마.
- 전체 일곱 기능 실제 PASS와 지원 경로 구현 완료를 구분해서 최종 보고해.
- 한국어로 간단한 진행 상황을 주고, 변경 후 필요한 회귀 검사와 graft build를 수행해.

먼저 현황·의존성을 확인한 다음 S01부터 실제 코드를 만들어줘.
```

## 2. Luna 또는 작업량을 더 나누고 싶을 때 — 한 단계 실행

아래의 `<단계 ID>`만 바꿔 제출한다. 첫 실행은 `S00`, 다음은 `S01`이다. Terra에서도 한 단계씩 검토하고 싶을 때 사용할 수 있다.

```text
프로젝트 /Users/hyunjae.kang/2026_opensrc/VGGT_SLAM/vggt_slam_map 에서 작업해.
AGENTS.md, temp_VGGT_SLAM_Plans.26.10.30.md, 존재하면 docs/DEMO_PROGRESS.md를 먼저 읽어.
이번 요청에서는 <단계 ID> 한 단계만 구현·검증하고 멈춰.

해당 단계의 입력·출력·완료 조건을 확인한 다음 graft로 실제 코드 위치와 callers를 조사하고,
필요한 최소 범위의 코드 수정, 관련 테스트, 필요한 소량 실데이터 확인을 실행해.
설명이나 계획만 다시 쓰고 끝내지 마.
선행 단계가 미완료면 그 사실과 필요한 작업을 밝히고 이번 단계의 독립 작업을 진행하되
검증하지 못한 부분을 완료로 표시하지 마.

기존 사용자 수정·데이터·logs를 보존하고 새 run_id만 사용해.
무거운 모델 설치·추론은 해당 단계에서 필요한 경우에만 해.
목업 테스트를 실제 PE/SAM3·비디오 추론 성공으로 기록하지 마.
projective 좌표, 원본 frame ID/timestamp, 캐시/이미지 Replay/비디오 입력 추론 구분을 유지해.

docs/DEMO_PROGRESS.md에 다음을 남겨:
1. 이번 단계의 변경 파일
2. 실행한 명령·검증 결과와 증거 경로
3. 완료/미완료 판정과 외부 제약
4. 바로 다음 단계 ID와 구체적 첫 작업

최종 답변은 이번 단계 결과·검증·미완료 이유·다음 단계만 짧게 알려줘.
```

## 3. 중단 후 재개 프롬프트

```text
VGGT-SLAM 전체 기능 데모 구현을 이어가줘.
AGENTS.md, temp_VGGT_SLAM_Plans.26.10.30.md, docs/DEMO_PROGRESS.md를 읽고
기존 코드·run manifest·검증 증거를 먼저 확인해.
마지막으로 완료된 단계는 반복하지 말고 첫 미완료 단계부터 진행해.
계획/진행 문서의 주장과 실제 파일이 다르면 실제 증거를 기준으로 상태를 정정해.
기존 학습 가중치·결과를 재다운로드하거나 같은 대규모 추론을 다시 시작하지 마.
확인한 상태와 다음 작업을 짧게 알린 뒤 실제 구현·검증을 계속해.
비디오·데이터나 접근권한이 필요한 부분만 정확히 BLOCKED로 남기고 가능한 작업은 마무리해.
```

## 4. 전환 방법

현재 앱의 모델 선택에서 Terra를 선택한 후 **1번 시작 프롬프트**를 제출한다. 앱의 실제 메뉴에 있는 reasoning 옵션을 사용한다. CLI라면 `/model` 또는 지원 버전에서 `codex -m gpt-6.1-terra`를 사용할 수 있다. 모델 전환 자체가 원본 SLAM 추론 모델을 교체하지는 않는다.

전체 계획 문서를 매 메시지에 붙이지 말고 파일을 읽도록 지시한다. 모델이 문서만 반복하면 “다음 미완료 단계의 코드와 검증 증거를 만들어줘”라고 범위를 다시 지정한다. Luna를 선택한다면 2번 단일 단계 방식을 권한다.

이 프롬프트 문서를 작성한 턴에서는 실행을 시작하지 않는다. 사용자가 모델 변경 후 실제로 제출하는 요청이 시작 신호다.
