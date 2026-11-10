# 최신 현황 — 구현·실증·계획 구분

> **2026-11-09 최신:** V4는 구현되었고 장시간 사용자 작업은 그대로 보존 중입니다. V5 VGGT-SLAM 전용(8107/8108)을 추가했습니다. 초보자 설명서는 [USER_GUIDE.html](USER_GUIDE.html) / [PDF](USER_GUIDE.pdf), 기술·측정은 [LIVE_V5.md](LIVE_V5.md)를 먼저 보세요. 아래11-08 수치는 당시 기록입니다.

기준일: 2026-11-08 UTC. 재개 절차는 [SESSION_HANDOFF.md](SESSION_HANDOFF.md), 다음 설계는 [26.11.09.VGGT_SLAM.Plan.html](../26.11.09.VGGT_SLAM.Plan.html), 사건별 증거는 [DEMO_PROGRESS.md](DEMO_PROGRESS.md).

## 버전

| 버전 | 실제 동작 | 상태 |
|---|---|---|
| V1 Classic /8101 | 기존 저장 지도·RGB·BEV·검색 UI | 보존, 기존 표시 구현 |
| V2 Smooth /8102 | 원본 영상 독립 재생·카메라 보간·full K GPU 점군·검색 | 구현/브라우저 검증, 재추론 없는 캐시 재생 |
| V3 Live /8103+8104 | 디스크 영상→실제 VGGT/MPS→점진 3D/RGB/BEV→CPU SAM3 ROAD→완료 후 검색 | 구현/실제 소량 생성·검색·복원 검증 |
| V4 /8105+8106 | 지도 생성 중 사전 객체 검출·추적·깊이 결합, 도로·하늘 분할 | 구현, 실시간 지연 목표/장시간 수용 미완료 |
| V5 /8107+8108 | VGGT-SLAM 전용, 실제 추론 해상도·루프 선택,3D/RGB/BEV | 구현, KITTI 앞6프레임378/518 실제 시험, 전체 폐루프 미평가 |

V3의 “실시간”은 서브맵·분할 결과가 끝날 때마다 추가하는 의미다. 원본 FPS로 모든 영상 프레임의 새 지도·분할을 계산한다는 뜻이 아니다. V2 약60Hz GPU animation도 SLAM60fps가 아니다.

## 기능 판정

| 기능 | 실제 근거 | 남은 구분 |
|---|---|---|
| 깊이·색상 점군 | PandaSet/KITTI/비디오 PCD와 frame/depth/confidence | 상대 스케일·GT 깊이 정확도 별도 |
| 카메라·궤적 | 저장 poses, frustum, TUM33매 | 전체 benchmark·절대정확도 미검증 |
| 서브맵 연결 | overlap와 그래프·전후 스냅샷 | 화면 색상만으로 연결 통과 판정하지 않음 |
| 루프·그래프 최적화 | KITTI 실제2루프와ON/OFF fitted ATE | 모든 영상에서 루프·정확도 개선을 보장하지 않음 |
| 텍스트 객체 검색 | PE 후보/전체 SAM3,2Dmask·유효깊이·3DOBB | 고유 객체 추적 없음; 관측 건수/박스 포함률은 GT precision 아님 |
| 영상 점진 입력 | 실제 OpenCV decode·PTS·drop로그·EOF flush | RealSense 물리장치 실증 제외 |
| 시각화·평가 | Viser·RGB/BEV/ROAD·PCD/TUM·evo | 도로 연결은 관측 셀 인접성, 주행 가능성 아님 |
| 지도 생성 중 사전 객체 탐색 | V3는 road만 점진 계산, 일반 검색은 완료 후 | V4에서 고정 클래스 검출·추적·상주 worker로 구현 예정 |

초기 S00–S12는 선택한 지원 경로의 실증을 수행했다. 11-06 인수 기록의 PASS 범위를 이후 모든 버전·영상·모델·하드웨어에 확대하지 않는다.

## 최신 실험

| run | 조건 | 결과 | 의미 |
|---|---|---|---|
| `video_20261108T173307_231634000` | PandaSet fixture 앞6프레임, submap3/disparity0/loops0 | 2서브맵,799486점,생성104.96초,ROAD6매 | V3 실제 생성·전환·검색·복원 |
| 같은 run `car` 검색 | 고유6매 전수, SAM3 CPU |55.96초,2D116/유효3D104관측 | 고유 차량116대라는 뜻 아님 |
| `video_20261108T181003_605025000` | 사용자 MOV전체305입력,95고유키프레임,12단계 | ROAD95검사,831.53초 | **회전 보정 전 결과**, 원본·결과 보존; 정상 전체 지도는 재생성 필요 |
| `video_20261108T184700_282397000` | 같은 MOV 방향 보정,앞6프레임만 |2서브맵,233500점,94.07초,ROAD6검사 | 정상 RGB/3D/실제 검색 검증, 유효 road 표면 없었음 |
| `video_20261108T195829_755817000` | 새 유튜브90초 전체,V3 submap8/disparity10/loops1 | **3D 저장 완료 / ROAD 후처리 중** | 최신 job.json/완료 저장/로그를 다음 세션에 확인 |

초기 개발 smoke `video_20261108T172544_144963000`은 job UI 카운트 결함이 있었지만 실제 이벤트/결과는6고유키프레임/2서브맵/ROAD6. 과거 표시값을 완료 수치로 사용하지 않는다.

## 마지막 수정과 검증

- 입력 MOV Display Matrix180도를 추론 전에 적용하고 자동 회전 backend의 중복 보정을 피한다. 90/180/270도 실제 MOV를 FFmpeg autorotate PNG와 비교했다.
- 파일 선택은 실제 button click→chooser 이벤트로 검증했다. 처리 중 다음 영상 선택 가능, 새 생성만 잠금, 현재 작업을 자동 취소하지 않는다.
- 자유 overview는 기록 카메라의 up/forward를 따른다. 기존 잘못된 입력으로 만든 지도를 CSS로만 회전해 기하·마스크를 섞지 않는다.
- V2 끝→재생 generation 동기화, 고밀도 GPU 점군/보정투영, 툴바 단일 writer를 검증했다. Metal/M2 Max의600k/약59.98Hz animation과 소프트웨어 GPU의약6.49Hz는 서로 다른 실험이다.
- 최신 전체 코드 검증 **149 passed,30.25초,Dash warning1**. 이번 문서 세션은 전체 모델 추론·테스트를 다시 실행하지 않았다. 기록된 이전 검증을 새 실행으로 오인하지 않는다.

## 재개할 때 주의할 미완료

1. 현재90초 V3 실행의 완료·메모리·ROAD 대기열·저장 검증. 이 입력은 과거90초 테스트와 설정이 다르다.
2. V3는 CPU ROAD 후처리가 완료될 때까지 일반 검색과 최종 전환을 기다린다. 상주 모델/새 프레임만 처리/표시와 정밀완료 분리가 V4 우선 과제다.
3. 중지 후 생성 재개는 미지원. supervisor가 시작한 직접 자식은 관리하지만 뷰어가 추가로 시작하는 검색 자식의 종료·고아 상태도 다음 lifecycle 감사에 포함한다(확인 과제).
4. 새 머신에 두 환경을 독립 설치하는 배포 재현성, MPS/CoreML 객체 모델, CUDA 원격 worker, 실시간 3D 객체ID, 동적 객체 분리는 미검증/미구현이다.
5. GPU 화질·툴바·V3·회전 수정·문서들은 HEAD9a0e7ba 이후 미커밋. 승인된 범위 밖 사용자 파일을 건드리지 않는다.

## 8103 후속 상태 조회 — 2026-11-08 22:35 UTC

새 유튜브90초 run의3D는완료됐다:2700입력/2196고유키프레임/275서브맵,drop0,227654920점PCD(약3.39GiB),약51분53초. V3전체는ROAD1091/2196후처리중으로검색잠금유지. 최근관측간격약7.79초로단순잔여약2시간23분이지만변동가능하다. 최신카운트는job/status를다시확인한다.서버·작업을중지하지않았다. 근거는`../evidence/live_status_20261108_01/`와진행기록을참고한다.


## 2026-11-09 Live V4 구현

계획 기반 독립 V4를 추가했다. 실행: `.venv/bin/python demo.py live4 --port 8105 --viewer-port 8106`. 상주 객체 검출·ByteTrack·도로/하늘 분할·정확한 깊이 프레임 결합·생성 중 검색·증분 지도 뷰어를 제공한다. 상세 구현, 증거 및 미달성 목표: [LIVE_V4.md](LIVE_V4.md). 기존 사용자 수정과 run은 보존했다. R5 장시간/GT 및 R6 조건부 엔진 전환은 미완료다.


## 2026-11-09 · V5 폐루프 품질 후속

사용자전체1348장378/submap8/disparity0실행은완료했으나GT사후적합ATE113.90m로전역정합품질실패였다. 새V5시간간격필터와518/submap16/선택226장조건으로V2동일재방문2쌍을검출했고ATE12.56m(기존V2약9.95m),84.32초로개선했다. 원인별효과는분리하지않았으며전체1348장의해당설정재실험은미실행이다. 상세 LIVE_V5 및 evidence/v5_loop_recovery_20261109_01.


## 2026-11-09 · 전체 영상과 검색 복원 최신

- 전체1348장을모두키프레임으로쓰는518/16/gap10재실험:4루프/사후정렬ATE60.00m(품질주의).
- 전체1348장을읽고이동80으로224키프레임선택:1루프/사후정렬ATE11.56m/80.06초. 새run video_20261109T213652_654365000, V5작업 live_20261109T133652_full_keyframes. 프레임수와키프레임수구분.
- V5는지도를생성한뒤선택검색/마스크/박스가가능하다. 생성중상주분할모델없음은유지. 실제SAM3/currentRGB검색과왼쪽표시픽셀/토글/Clear실증PASS. CLOSED_LOOP_GUIDE/LIVE_V5최신항목참조.


## 2026-11-09 · RF-DETR-Seg 실제 연결

V5 Search model의 RF-DETR 준비필요 상태를 실제 RF-DETR-Seg Nano 검색으로 대체했다. 별도 `.venv-rfdetr`/rfdetr1.12.0/Torch2.15.0 환경, 공식 COCO Seg Nano 가중치(134545398bytes,공식MD5통과),CPU/312입력/threshold0.3. 기존 SLAM/YOLO/SAM3 환경은 변경하지 않았다. 선택기능:현재/표본/전수/PE후보,RGB마스크·박스,깊이기반3D/BEV,저장모델명·scope,Clear/선택삭제. 공식COCO클래스ID로 car/person 등을구분하고 printer/road등미지원은모델로딩전안내. 다중검색어는프레임추론공유,모델버전/가중치hash/클래스/임계값을캐시identity에포함한다.

실제 KITTI playback34/source256 car검색:2D마스크2/유효3D1,worker기록6.657초(패키지설치·다운로드제외). 전체회귀188passed/25.27초. 증거 evidence/v5_rfdetr_20261109_01의requirements.txt/model_identity.json/search_status.json/inference.log. 사용법·설치재현 docs/RFDETR_SEARCH.md. 기존현재완료run을/api/open으로재열기,지도재추론없음. 전체구간정확도·고유3D객체수·다른모델대비우열·실시간성은미검증.


## 2026-11-09 · Search 비활성화 고착 복구

실제 현재완료지도에서RF-DETR검색 search_1794270739076919000은20/24프레임에서KeyboardInterrupt로중단됐지만status.running/worker_pid80927이남았다. ps로PID부재확인. V5는시작시running상태만으로검색을재개감시하고프로세스없음을확인하지않아Search가영구잠겼다.

search_lifecycle를추가해저장된workerPID생존과명령/작업폴더일치(PID재사용방지)를확인한다. 종료작업은원본interrupted_status.json을보존하고failed/InterruptedWorker로전환한다. 재연결watcher에도검사,직접시작한worker는status가있어도process.poll로종료감지한다. 권한부족은종료로단정하지않는다. 감시종료버튼조건은allow_search도존중한다. 기존query결과/로그/지도/삭제목록보존,실행프로세스종료신호없음.

동일완료V5지도를재열어복구했고실제Chrome에서Search활성/새RF-DETR검색완료/유효3D/저장모델·범위/완료후Search재활성/JS예외0 PASS. evidence/v5_search_unlock_20261109_01/browser_checks.json,rfdetr_search.png,original_status.json. 회귀추가:종료PID복구·원본보존·PID재사용·정상실행작업유지. 최초전체테스트185passed/6failed는Macsubprocess비정상종료로관련항목재검사중이며전체성공을주장하지않는다.
