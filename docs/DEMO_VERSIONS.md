# 데모 버전 선택

<http://localhost:8100>에서 버전을 선택한다. V1·V2는 별도 프로세스·UI 상태로 기존 run을 재생한다. V3는 새 비디오에서 실제 지도와 도로를 생성한 후 같은 검색·표시 기능을 제공한다.

| 버전 | 주소 | 재생 방식 |
|---|---|---|
| Classic V1 | http://localhost:8101 | 기존 프레임별 고화질 지도 재생과 기존 전체 조작 기능 |
| Smooth V2 | http://localhost:8102 | 독립 시간축·부분 점군 갱신·원본 RGB 영상·카메라 보간 |
| Live V3 | http://localhost:8103 | 파일 선택 → 실제 VGGT·도로 생성 → 3D/RGB/BEV 점진 표시 → 완료 후 검색 |

## 실행

```bash
.venv/bin/python demo.py versions --port 8100
.venv/bin/python demo.py live --port 8103 --viewer-port 8104
.venv/bin/python demo.py view --run logs/demo_runs/s03_kitti_loop_on_20261031_01 --port 8101 --version classic
.venv/bin/python demo.py view --run logs/demo_runs/s03_kitti_loop_on_20261031_01 --port 8102 --version smooth --source-fps 10
```

각 명령은 별도 터미널에서 실행한다. 기본 view 버전은 classic이므로 기존 실행 명령의 의미는 유지된다. 버전 선택 화면은 서버를 대신 시작하지 않는다. 새 버전 선택 화면의 링크로 V1에 돌아갈 수 있다.

## V1 보존

기존 `viewer.py`, `main_panel.py`, `web/studio.html`과 표시 helper의 내용은 변경하지 않았다. V2는 `viewer_smooth.py`, `smooth_panel.py`, `smooth_runtime.py`, `web/studio_smooth.html`로 분리했다. 공통 helper는 V1과 같은 구현을 재사용한다.

`docs/versions/classic_v1_20261107_01.tar.gz`는 변경 전 표시 관련 소스24개를 보존하며, 같은 이름 JSON은 파일별 SHA256이다. 비교 결과 기존 표시 모듈/HTML은 모두 일치하고 `demo.py`만 버전 선택 CLI 추가로 달라졌다. 원본 run/events/PCD/분할·검색 결과를 재추론하거나 덮어쓰지 않았다. 두 버전의 저장 검색 삭제는 같은 run의 목록에 반영된다.

## V2 동작과 범위

1. 단조 시계가 재생 시간을 진행하며 지도 계산 완료를 기다려 시간을 늦추지 않는다. 늦은 지도 프레임은 가장 최근 시간의 프레임으로 건너뛰며 쌓아두지 않는다.
2. 재생 점군은 각 관측의 고밀도 버퍼를 처음 한 번만 업로드한다. 이후 GPU draw count만 조절하여 점 수 예산을 지키며 현재 주변3개 관측을 우선 유지한다. 뒤로 탐색하면 미래 노드를 제외한다. graph/sky/color 변경은 캐시를 다시 만든다.
3. 재생 중 지도/BEV는 최대120000점 계산 예산과 경량 JPEG를 사용하고, CPU calibrated raster를 반복 생성하지 않는다. 정지하면 기존 점 수 예산·1.5배 안티앨리어싱 calibrated raster로 복원한다. 화면의 실제 점군은 노드 샘플을 누적하므로 계산용 BEV 샘플 수와 다를 수 있다.
4. RGB는 별도 MP4를 브라우저 video로 재생한다. 영상 시간과 지도 키프레임 시간을 함께 표시한다. 지도·BEV가 원본 영상의 모든 프레임에서 재계산되는 것은 아니다.
5. RGB 시점의 새 GPU 렌더러는 전체 intrinsic 행렬(skew/principal point 포함)·위치·방향을 사용한다. 카메라 knot를 한 번 받아 브라우저 animation frame마다 위치·Slerp·intrinsic을 보간하고 직접 점을 투영한다. 정지 CPU raster도 같은 보간 투영을 사용해 방식 전환의 시점 차이를 줄인다. 보간은 새로운 SLAM 추정이나 정확도 향상이 아니다. 자유3D는 Viser로 탐색한다.

재생 중 원본 영상에 다른 프레임의 마스크를 얹지 않는다. 선택 검색의 RGB 분할/박스는 정지한 지도 키프레임 이미지에서 확인한다. 저장된 모든 중간 영상 프레임의 segmentation을 새로 계산하지 않는다. 도로·BEV·검색·패널/줌/재생 조작은 V2에서도 유지한다.

## 현재 KITTI 미디어

`evidence/smooth_media_20261107_01/`:원본508~1855의1348장,1280×342,MP4134.8초. 저장된 source timestamp가 없으므로 명시한10fps를 사용한다. 측정된 센서 타임스탬프라고 주장하지 않는다. 초기·중간·마지막 선택 RGB의 원본 대응을 확인하고 연속 파일 누락도 검사했다. 생성13.02초,65,759,217bytes. 기존226개 고유 지도 키프레임과 구분한다.

다른 순번 이미지 run의 미디어 준비 예:

```bash
.venv/bin/python scripts/demo_prepare_smooth_media.py --run logs/demo_runs/<run> --output logs/demo_runs/<run>/evidence/smooth_media_<unique_id> --source-fps 10
```

실제 입력 FPS를 명시해야 한다. 현재 준비 도구는 연속 번호 원본 이미지 입력을 지원한다. 미디어 캐시가 없는 run은 기록 RGB 키프레임으로 재생한다.

## 검증

전체132개 테스트 통과. 새 테스트는 계산 지연 중에도 진행하는 시계/누적 지연 방지,중복 시간 처리,pause/seek,Slerp,노드당 최초 업로드·미래노드숨김,FPS fallback 표기를 검증한다.

KITTI run의 `evidence/browser_smooth_v2_20261107_02/validation.json`:초기 구간 영상 시간/벽시계 비율0.9975,decode 카운터 증가 약10.57/s,지도 갱신·정지 고화질·BEV조작 통과. `browser_smooth_v2_late_20261107_01/validation.json`:후반 비율1.0000,decode 증가 약9.94/s,같은 검증 통과. decode 카운터는 화면 표시 FPS 자체를 보장하는 지표가 아니며,측정은 해당 로컬 Chrome 환경의 짧은 구간이다. 30/60fps 성능을 주장하지 않는다.

`smooth_versions_20261107_01/validation.json`:V1/V2 동시 운영·버전 선택 링크·MP4 HTTP206 범위 전송 확인. V2 화면 증거에는 재생 중과 고화질 정지 상태를 각각 보존했다.

V2 반복 재생 수정: 재생 세대(generation)로 원본 영상 seek를 동기화하고 이전 재생의 timeupdate/ended를 무시한다. 끝에서 Play를 누르면 지도와RGB가함께처음으로돌아간다. 기존V2탭은새로고침하여새클라이언트를사용한다. 검증: browser_smooth_replay_20261107_01.


## 2026-11-08 재생 3D 화질 개선

기존 V2는재생시노드당1000점과단순중앙투영Viser카메라를사용했다. 정지시600000점의전체보정CPU투영과달라화질/시점이갑자기변했다. 현재는별도GPU canvas가같은보정투영을사용하고,기본점수예산600000을재생중에도활용한다. 현재주변3개관측의고밀도점을우선한다. 고밀도버퍼의순서는고정된공간샘플이며노드추가시기존버퍼를재전송하지않는다. 맵·도로·박스·궤적의world좌표는그대로사용한다.

지도탭 **재생 3D 품질**:

- **자동**(기본): GPU성능에맞춰배경LOD를조절하고현재주변점을우선유지한다. Metal하드웨어검증에서는600000점그대로표시했다.
- **높음**:사용자가설정한Displayed point limit을우선한다.
- **균형 / 가벼움**:최대300000/120000점의대상을설정한다.

소프트웨어GPU의자동모드는저해상도·90000점배경/전경예산과도로표시제한으로CPU렌더비용을줄인다. 일반하드웨어GPU의상한은1920×1080이며,성능환경에따라실제프레임률은다르다. WebGL을사용할수없으면CPU보정화면으로복귀한다. 상단표시점수는GPU에제출한맵점수이며프러스텀내실제로차지한픽셀수와는다르다. BEV샘플수는독립계산예산이다.

하드웨어실험(M2 Max/Metal,짧은검증구간):정지600000점/재생600000점,RGB제시약9.996fps/GPUanimation약59.978fps,영상시간벽시계비율1.000. 기존카메라와브라우저보정행렬의수학적픽셀좌표비교오차약1.36e-12(실제GPU raster픽셀정밀도를뜻하지않음). 새로운독립적기하정확도나모든기기에서60fps를보장하는수치는아니다. 근거는KITTI run의 `evidence/browser_gpu_quality_metal_20261108_01/validation.json` 및 재생/정지 스크린샷이다.

운영8102 최종검증 `browser_gpu_quality_live_20261108_01`:600000점·RGB약9.9965fps·GPU animation약59.979fps,자유3D↔Reset/고화질정지통과. 소프트웨어GPU강제실험의자동모드02는RGB제시약4.50fps/GPU約6.49fps여서실제하드웨어가속수준의성능은보장하지않는다.

## Live V3

V2 기반의 새 영상 처리 버전이다. 기존 V1·V2 서버는 보존한다. 업로드·실제 계산·도로·완료 후 전구간 검색·이전 작업 다시 열기와 저장 구조는 [LIVE_V3.md](LIVE_V3.md)를 참고한다. 실시간 갱신은 완료된 서브맵 단위이며 모델의 30fps 추론을 뜻하지 않는다.

## 세션 재개와 다음 버전

최신 코드·데이터·실행 중 작업은 [SESSION_HANDOFF.md](SESSION_HANDOFF.md)와 [CURRENT_STATUS.md](CURRENT_STATUS.md)를 먼저 확인한다. V3 영상 선택과 MOV 방향 보정은 적용됐으며 기존 탭은 새로고침한다. 반전 입력으로 생성된 과거 run은 원본을 보존하고 새 run으로 재생성한다. 지도 생성 중 사전 객체 탐색을 추가할 **V4는 계획만 작성된 상태**이며 아직 선택 화면/CLI에 없다. [26.11.09 계획서](../26.11.09.VGGT_SLAM.Plan.html)에 구현 순서와 모델 비교를 정리했다.


## 2026-11-09 Live V4 구현

계획 기반 독립 V4를 추가했다. 실행: `.venv/bin/python demo.py live4 --port 8105 --viewer-port 8106`. 상주 객체 검출·ByteTrack·도로/하늘 분할·정확한 깊이 프레임 결합·생성 중 검색·증분 지도 뷰어를 제공한다. 상세 구현, 증거 및 미달성 목표: [LIVE_V4.md](LIVE_V4.md). 기존 사용자 수정과 run은 보존했다. R5 장시간/GT 및 R6 조건부 엔진 전환은 미완료다.


## 2026-11-09 · V5와 버전별 쉬운 설명서

[사용자 설명서 HTML](USER_GUIDE.html) / [PDF](USER_GUIDE.pdf) / [Markdown](USER_GUIDE.md). V5는 `.venv/bin/python demo.py live5 --port 8107 --viewer-port 8108`로 실행한다. VGGT-SLAM 전용이며 의미/도로/하늘 분할은 하지 않는다. 실제추론 너비378이 기본이고518/322/224도 선택가능하다. 루프1이 기본,0이면장소검색모델도로딩하지않는다. 기존버전은보존한다. [V5 측정·사용법](LIVE_V5.md).

최신V5는생성완료후선택검색·Object mask/Bounding box를지원한다. 생성중상주모델을실행하지않는방식이며,기존“검색없음”은최초구현시점범위다. 전체1348입력→224키프레임/루프1/사후ATE11.56m/80초를추가검증했다.
