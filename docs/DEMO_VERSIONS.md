# 데모 버전 선택

<http://localhost:8100>에서 버전을 선택한다. 두 버전은 별도 프로세스·UI 상태를 사용하며, 저장된 run과 검색 증거는 공유한다.

| 버전 | 주소 | 재생 방식 |
|---|---|---|
| Classic V1 | http://localhost:8101 | 기존 프레임별 고화질 지도 재생과 기존 전체 조작 기능 |
| Smooth V2 | http://localhost:8102 | 독립 시간축·부분 점군 갱신·원본 RGB 영상·카메라 보간 |

## 실행

```bash
.venv/bin/python demo.py versions --port 8100
.venv/bin/python demo.py view --run logs/demo_runs/s03_kitti_loop_on_20261031_01 --port 8101 --version classic
.venv/bin/python demo.py view --run logs/demo_runs/s03_kitti_loop_on_20261031_01 --port 8102 --version smooth --source-fps 10
```

각 명령은 별도 터미널에서 실행한다. 기본 view 버전은 classic이므로 기존 실행 명령의 의미는 유지된다. 버전 선택 화면은 서버를 대신 시작하지 않는다. 새 버전 선택 화면의 링크로 V1에 돌아갈 수 있다.

## V1 보존

기존 `viewer.py`, `main_panel.py`, `web/studio.html`과 표시 helper의 내용은 변경하지 않았다. V2는 `viewer_smooth.py`, `smooth_panel.py`, `smooth_runtime.py`, `web/studio_smooth.html`로 분리했다. 공통 helper는 V1과 같은 구현을 재사용한다.

`docs/versions/classic_v1_20261107_01.tar.gz`는 변경 전 표시 관련 소스24개를 보존하며, 같은 이름 JSON은 파일별 SHA256이다. 비교 결과 기존 표시 모듈/HTML은 모두 일치하고 `demo.py`만 버전 선택 CLI 추가로 달라졌다. 원본 run/events/PCD/분할·검색 결과를 재추론하거나 덮어쓰지 않았다. 두 버전의 저장 검색 삭제는 같은 run의 목록에 반영된다.

## V2 동작과 범위

1. 단조 시계가 재생 시간을 진행하며 지도 계산 완료를 기다려 시간을 늦추지 않는다. 늦은 지도 프레임은 가장 최근 시간의 프레임으로 건너뛰며 쌓아두지 않는다.
2. 재생 중 지도 점군은 노드별 고정 샘플(최대1000점)을 유지하고 새로 관측된 노드만 업로드한다. 뒤로 탐색하면 미래 노드를 숨긴다. graph/sky/color 조건 변경은 캐시를 다시 만든다.
3. 재생 중 지도/BEV는 최대120000점 계산 예산과 경량 JPEG를 사용하고, CPU calibrated raster를 반복 생성하지 않는다. 정지하면 기존 점 수 예산·1.5배 안티앨리어싱 calibrated raster로 복원한다. 화면의 실제 점군은 노드 샘플을 누적하므로 계산용 BEV 샘플 수와 다를 수 있다.
4. RGB는 별도 MP4를 브라우저 video로 재생한다. 영상 시간과 지도 키프레임 시간을 함께 표시한다. 지도·BEV가 원본 영상의 모든 프레임에서 재계산되는 것은 아니다.
5. RGB 카메라 추적 시 위치 선형 보간·방향 Slerp를20Hz로 전달한다. GPU 카메라는 재생 중의 부드러운 시점용이며, 기존 projective camera의 skew/lens shift를 그대로 나타내는 calibrated raster는 정지 시 사용한다. 보간은 새로운 SLAM 추정이나 정확도 향상이 아니다. 자유3D에서는 시점 추적하지 않는다.

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
