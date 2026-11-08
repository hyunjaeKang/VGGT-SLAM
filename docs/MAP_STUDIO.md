# Map Studio

KITTI 전체 구간 검색 데모: <http://localhost:8101>. 기존 영상 데모: <http://localhost:8097>. 새 검색 UI는 8101 페이지를 새로고침한다.

## 화면

- **지도 · Map**: 프레임별 3D 점군, 점 수/크기, 하늘 제거, 동기화된 BEV와 RGB.
- **검색 · Search**: 검색어 입력 → 실제 PE/SAM3 실행 상태 → 선택 RGB의 청록 마스크 및 유효한 3D 박스. 저장 결과는 `검색어 · 박스 수 · 식별자`로 선택한다. Clear는 화면의 박스만 지운다.
- **분석 · Inspect**: 깊이/신뢰도, 최적화 단계와 before/after, 루프 근거 및 평가.
- 재생 상태는 탭 위에 계속 표시한다. 캐시 재생은 모델 실시간 추론이 아니다.

## 하늘

현재 90초 영상 run의 전체 533개 RGB/depth 프레임(중첩 포함)에 skyseg를 적용했다. 474개 고유 RGB의 모델 결과를 중첩 관측에서 재사용했다. VGGT 공식 데모에서 사용하는 [skyseg 모델과 전처리](https://github.com/facebookresearch/vggt/blob/main/visual_util.py)를 참고했다. 0=비하늘,255=하늘인 출력 방향은 실제 RGB/마스크를 확인했다.

기록된 `projection_matrix @ homography`로 각 camera-local preview 점을 동일 RGB 픽셀에 투영한다. 모든 26,649,381개 preview 점의 대응이 유효했다. 2px 경계 확장을 적용하고 기본 threshold32에서 3,378,220개 점을 표시에서 제외한다. **Hide sky**로 원본과 비교하며, 펼친 **Sky filter**에서 threshold를 낮추면 더 강하게 제거한다.

이것은 원본 PCD를 변경하지 않는 표시 overlay다. 먼 산, 가는 전선, 나뭇가지 일부가 같이 제거될 수 있다. 세 구간의 RGB/마스크 비교는 `evidence/sky_20261106_01/visual_review.png`. 분할 GT나 정량 IoU는 없다. 다른 run에 캐시가 없으면 제거 기능을 비활성화하고 이유를 표시한다.

새 run에 sky 캐시를 준비하려면 기존 폴더와 다른 output을 사용한다. 모델은 이 작업에서 `logs/demo_models/skyseg.onnx`로 받았다(SHA256은 index.json).

```bash
.venv/bin/python scripts/demo_prepare_sky.py \
  --run logs/demo_runs/<run_id> \
  --model logs/demo_models/skyseg.onnx \
  --output logs/demo_runs/<run_id>/evidence/sky_<unique_id>
```

완료 후 뷰어를 다시 시작한다. 뷰어 시작 시 모델을 로드하거나 다운로드하지 않는다.

## BEV

현재까지 표시된 점군과 궤적만 매 프레임 투영한다. 주황은 이동 경로, 청록은 마지막 카메라 위치다. 빈 셀은 미관측으로 남긴다. 기본 XZ는 초기 카메라 좌표 기준의 평면이며 XY/YZ도 선택할 수 있다. 상대 복원 단위의 표면 지도다. 검증된 지면, 장애물/자유공간 occupancy, 미터 축척 또는 ENU 지도로 해석하지 않는다. 전체 경로에 걸쳐 카메라 기울기를 추정해 지면을 보정하는 기능은 포함하지 않는다.

원래 비디오 입력 추론 화면에도 같은 BEV raster를 연결했다. 서브맵 생성/최적화 때 제한된 점군 샘플과 새 카메라 위치로 갱신하며, 동일 서브맵은 대체한다. 그 화면은 실제 추론 중에 갱신된다. 저장된 지도의 Map Studio는 프레임 재생/이동에 동기화된다.

## 검색

현재 90초 영상은 `--run_os` 없이 복원됐으므로 처음에는 검색 결과가 없었다. 이제 Search가 별도 `.venv-open-set` worker에서 실제 PE와 SAM3를 실행한다. 기본 `.venv`의 tensor stack은 변경하지 않는다. UI는 진행/완료/실패와 결과 0개도 표시한다.

기본 범위는 **전구간 전수**다. 해당 run에 기록된 고유 원본 프레임을 모두 검사하며 유효 박스를 찾아도 중단하지 않는다. **전구간 표본**, **현재 RGB**, **PE 후보 찾기**도 선택할 수 있다. PE 후보 방식은 이전처럼 일부 후보를 검사하고 성공 시 종료하므로 전체 구간의 객체 수를 나타내지 않는다. `car,tree,truck,building`처럼 쉼표로 여러 클래스를 입력하면 각각 별도 SAM3 프롬프트로 처리한다. 자동차/차/승용차는 car로 연결한다.

SAM3에는 가능한 경우 검증된 원본 해상도 RGB를 사용한다. 원본을 기록 당시 변환으로 재현해 저장 RGB와 일치하는지 확인하고, 분할 마스크는 픽셀 중심 변환으로 저장 깊이 격자에 맞춘다. 원본 확인에 실패하면 기록 RGB로 되돌아가며 사유를 남긴다. 2D 마스크만 내용·프롬프트·모델 기준으로 캐시하고, 3D 박스는 현재 저장 지도 좌표로 다시 계산한다.

KITTI `s03_kitti_loop_on_20261031_01` 전수 결과: **226/226 고유 프레임, 2D 자동차 관측979건, 유효 3D 관측720건**. 원본 전체1348장이 아니라 이 run에 선택·저장된226장을 뜻한다. 나머지259건은 유효 깊이 지원점8개 미만으로 3D 박스를 만들지 않았다. **720대의 서로 다른 자동차라는 뜻이 아니다.** 동일 차의 여러 프레임 관측을 포함하며 객체 추적·중복 통합은 하지 않는다.

Search에서 저장 결과 `car · 전수 226장 · 3D관측 720건`을 고른다. **Result frame → 전체 관측**은 전체 지도에 누적 박스를 표시하고, 개별 프레임을 고르면 해당 RGB·마스크·박스만 표시한다. source982는 실제로2개이며 다른 프레임의 검출은 전체 관측에서 확인한다. Clear 후 저장 결과를 다시 선택할 수 있다.

첫 전수 SAM3 처리 시간은 약26분15초였다. 웹 버튼으로 재검색한 경우226개 마스크 캐시를 모두 재사용해 처리 타이머17.94초로 같은979/720건을 얻었다. 타이머는 Python 시작·모듈 import를 제외한다. 결과는 새로운 `evidence/query_jobs/<unique_id>/`에 저장하며 기존 events/PCD/검색 결과는 보존한다. 이전2개 결과는 단일 후보 결과로 남는다. 마스크·박스 일관성은 검증했으나 GT 기반 precision/recall은 측정하지 않았다.

최신 근거는 KITTI run 아래 `evidence/query_jobs/car_all_native_20261106_01/`의 `result.json`, `consistency_audit.json`, `visual_review_12_frames.jpg`와 `evidence/browser_search_v3_live_20261106_01/validation.json`, `evidence/browser_search_button_all_20261106_01/browser.json`이다.

## 메인 RGB·BEV 및 카메라 Reset (최신)

메인 왼쪽의 위쪽에는 3D 지도를, 아래쪽에는 **RGB / BEV MAP** 카드를 고정 표시한다. 오른쪽의 지도/검색/분석 탭을 바꾸어도 두 카드는 유지된다. 프레임 ID와 원본 timestamp를 함께 표시한다.

기본 **RGB 카메라 시점**은 현재 프레임의 기록된 전체 projective projection으로 실제 3D 점을 투영한다. 단순한 centered perspective camera로는 후반 프레임의 skew/principal-point 변화를 정확히 표현할 수 없으므로, calibrated point raster를 메인 시점으로 사용한다. RGB 자체를 지도 대신 복사하는 기능이 아니다. 같은 프레임의 preview를 우선 배치하고 나머지 공간을 전체 지도 샘플로 채우며 총 점 수 예산은 유지한다. 가시 depth의 가까운 점이 같은 픽셀에서 우선한다.

**자유 3D 탐색**은 Viser의 3D orbit으로 전환한다. **Reset · 현재 RGB 시점**을 누르면 지금 선택한 RGB 카메라로 복귀한다. 타임라인 재생 시 RGB·BEV·기본 시점이 함께 바뀐다. 오른쪽 **RGB 시점 추적** 체크와 메인 모드가 연결되며, **Fit map**은 자유 시점의 전체 지도 보기다. Reset은 run/프레임/분석 결과를 초기화하지 않는다.

새 `MainPanel`의 로컬 HTTP 화면이 public8097, Viser는 빈 내부 포트에서 동작한다. 기존 `.venv` 패키지/빌드 파일은 수정하지 않았다. `/api/frame`과 버전별 RGB/BEV/camera 이미지가 한 snapshot을 공유하고 최근4개 버전만 유지한다. 구형 뷰어용 브라우저 검사도 iframe 안의 컨트롤을 검사하도록 갱신했다.

자동차 재검증 `car_retry_20261106_01`: 기존 실패 프레임806은마스크0,다음 PE 후보1984는마스크3/유효3D박스1. 최종 UI 검색은 현재프레임2696을 포함한3개후보 후 동일한유효박스1개를 찾았다. 기존 car0개 결과도 삭제하지 않고 이전 단일 프레임 검색이라는 안내를 표시한다.

## 검증 위치

기본 경로는 `logs/demo_runs/video_20261106T064802_616910000/`.

- `evidence/sky_20261106_01/index.json`, `visual_review.png`: 모델·프레임·점 대응·시각 근거.
- `evidence/map_studio_validation.json`, `bev_full_sky_filtered.png`: 표시 샘플과 BEV 통계.
- `evidence/browser_studio_01/`: 초기 UI와 실제 tree 검색 성공.
- `evidence/browser_studio_final_01/`: 하늘 ON/OFF 등 통과. 새 마스크 표시의 read-only 이미지 오류 발견 기록, 최종 성공으로 세지 않는다.
- `evidence/browser_studio_final_02/`: 이미지 복사 수정 후 최종 재검사.
- `logs/demo_environment/live_bev_20261106_01/`: 실제 비디오 Pause/Step/Resume/Stop과 BEV 증가 브라우저 증거.
- 실시간 추론 새 run `video_20261106T173655_057395000`:14프레임,4서브맵,drop0,PCD1,941,682점. 이전 결과를 재추론하거나 덮어쓰지 않았다.

최신 메인 화면 증거:

- `evidence/query_jobs/car_retry_20261106_01/`: 최고점 프레임의 미검출과 다음 후보의 실제 검출,각 시도 원본RGB/마스크/OBB.
- `evidence/browser_main_rgb_final_01/`: 기존8097에서 메인3뷰/기본카메라/자유뷰/Reset/재생동기화/실제car검색 확인.
- `evidence/browser_main_rgb_ready_01/`: 최종 간소화 UI와 저장된 car1박스 선택·Reset·Clear·재열기.
- 단위/회귀103개 통과:camera pose축,skew/lens shift가 있는 실제 픽셀 투영,앞뒤 occlusion,현재프레임 우선표시의 projective 변환/하늘필터,현재+후보 중복제거,2D/3D 실패 구분 포함.


자유3D축수정:Viser public CameraHandle은OpenCV규약(+Z전방,-Y위)을사용한다. RQ의R.T를그대로전달하며OpenGL축반전을중복적용하지않는다. 관련6개회귀와실제브라우저 browser_free_camera_axes_01에서전환/Reset/재생을재확인했다.


오른쪽기능패널은전체화면높이로표시한다. 오른쪽하단의별도상태설명창은제거했고,재생상태·프레임번호는왼쪽상단툴바에통합했다. RGB/BEV카드는왼쪽영역에만배치한다. 변경후페이지를새로고침한다.


메인3D와RGB·BEV는겹치는overlay가아니라위/아래실제영역으로분리한다. 오른쪽기능패널은전체높이를유지하며,내부3D/보조canvas의높이를상단영역에맞춰카메라aspect도갱신한다. 기존Viser정적client는로컬/viser/에서read-only로제공한다.


## 세 뷰 크기 조절

- 3D와 아래 두 뷰 사이의 가로 구분선을 위아래로 드래그하면 3D 높이를 조절한다.
- RGB와 BEV 사이의 세로 구분선을 좌우로 드래그하면 두 뷰의 너비를 조절한다.
- 상단 **뷰 크기 초기화**는 두 비율만 기본값으로 되돌린다. RGB 카메라 Reset과 별개다.
- 구분선에 포커스를 두고 방향키로도 조절할 수 있다. 구분선을 더블클릭하거나 Home 키를 누르면 해당 축만 기본 크기로 복원한다.
- 비율은 브라우저의 같은 주소에 저장되어 새로고침 후에도 유지된다. 창 크기가 바뀌면 최소 크기 안에서 조정된다. 재생 프레임이 바뀌어도 수동 설정한 높이는 유지된다.

## 검색 패널 결과 관리 (2026-11-06)

- Result frame은 유효 3D 박스가1개 이상인 프레임만 나열한다. 0건 기록은 원본 증거에 유지된다.
- Saved object query에서 항목을 선택하고 **Delete selected query**를 누르면 해당 검색만 목록에서 삭제된다. `evidence/deleted_queries.json`에 삭제 목록을 저장하므로 재실행 후에도 유지한다. 원본 검색/마스크/PCD/events는 보존한다.
- 오른쪽 별도 Object query frame 이미지는 제거했다. 결과 분할 마스크는 **왼쪽 아래 RGB 뷰**에서 현재 프레임에 맞춰 표시한다. 전체 관측 선택 시에도 타임라인의 현재 RGB에 해당하는 마스크만 표시하며 여러 클래스는 합친다.
- **Clear object boxes**는 선택을 해제하고 3D 박스와 RGB segmentation overlay를 함께 제거한다. RGB 원본은 그대로 표시한다. 저장 검색을 다시 선택하면 결과를 다시 볼 수 있다.

Result frame 또는 저장 검색을 선택하면 재생을 자동으로 일시정지한다. 선택한 프레임의 RGB·분할 마스크를 유지하며, 다시 Play를 누르면 그 위치부터 재생한다.

## 고밀도 표시 및 화면 해상도 대응 (2026-11-06)

KITTI run은 `evidence/dense_kitti_20261106_01/`의 고밀도 표시 캐시를 자동 사용한다. 원래 프레임당1000점 대신 최대20000점,240개 기록 프레임 총480만 점을 준비했다. 화면에는 기본60만 점 예산으로 제한하고 현재 프레임 점을 우선 배치한다. 최적화 before/after와 타임라인에는 기존 camera-local→snapshot homography를 그대로 적용한다. 원본PCD/events/깊이/검색 결과는 수정하지 않는다.

캐시 생성은 저장 깊이를 전체 projective camera로 역투영한다. 신뢰도 기준을 유지하며 기존 skyseg 출력과 경계2px 확장을 각 픽셀에 연결한다. 새 sky 캐시가 선택되거나 events가 달라진 캐시는 자동 사용하지 않는다. 완성되지 않은 소량 실험 캐시도 자동 선택하지 않는다.

RGB 카메라 3D뷰는 실제 뷰 크기와 화면배율에 맞춰 렌더링하며 최대1920×1080 안에서 원래 카메라 종횡비를 유지한다. 1.5배 supersampling 후 Lanczos 축소,둥근 점,더 높은 JPEG 품질/색차 샘플링을 사용한다. 자유3D도 둥근 점으로 표시한다. 화면 확대가 새로운 깊이 디테일을 만들지는 않는다. 3D뷰를 넓히거나 브라우저 크기를 바꾸면 출력 해상도가 다시 맞춰진다. 여러 브라우저는 같은 로컬 뷰어 상태를 공유하므로 마지막 viewport 요청이 기준이다.

다른 run 준비 예시(기존 캐시를 덮지 않는 새 output 필요):

```bash
.venv/bin/python scripts/demo_prepare_dense.py \
  --run logs/demo_runs/<run_id> \
  --output logs/demo_runs/<run_id>/evidence/dense_<unique_id> \
  --per-frame 20000
```

해당 run의 sky 캐시를 먼저 준비하면 함께 적용된다. 완료 후 뷰어를 재시작한다. `--max-frames 3`은 소량 실험용이며 전체 캐시로 자동 선택하지 않는다.

비교 이미지: KITTI `evidence/dense_quality_review_20261106_01/comparison.jpg`(왼쪽 기존/오른쪽 고밀도),측정 `metrics.json`. 사진 수준의 표면 복원이나 새 SLAM 정합 개선을 뜻하지 않는다.

## road 3D 및 BEV connectivity (2026-11-07)

지도 탭 **Show road · 3D 도로**를 켜면 저장 road 마스크에 해당하는 실제 깊이점을 초록색으로 표시한다. RGB 카메라 3D뷰와 자유3D 모두 적용된다. **실시간 2D 맵 · BEV → BEV display → Road connectivity**는 도로 관측 셀의 연결 지도로 전환하고 **표면 지도**로 복귀할 수 있다. 3D 토글과 BEV 옵션은 독립적이다. 검색의 Clear object boxes는 검색 박스/마스크를 지우며, 독립 도로 레이어는 Show road로 제어한다.

해당 run의 삭제되지 않은 road 검색 중 검사 범위가 가장 넓은 결과를 자동 선택한다. 입력은 현재 KITTI 전체226장 검색 `evidence/query_jobs/search_1794054591014459000/result.json`. 깊이 해상도에 정렬된 마스크를 union하고 저장 confidence/valid 기준으로 걸러 전체projective camera를 역투영한다. 프레임당 최대6000점을 추출하며 실제 약124만개 도로 점을 확보했다. 타임라인 이후 프레임과 선택snapshot에 없는 카메라는 표시하지 않고, before/after의 homography로 다시 변환한다. 화면용3D 레이어는 최대15만 점으로 제한한다.

BEV는 현재까지 관측된 road 점을128×128격자로 투영한다. 셀 중심이 노드이며 상하좌우로 맞닿은 관측 셀만 edge로 연결한다. 색은 연결 성분,밝은 선은 인접 연결이다. 빈 셀을 채우거나 궤적으로 연결을 만들지 않는다. 기본XZ와XY/YZ 전환을 지원한다. 셀 크기는 현재 관측 범위에 따라 바뀌는 상대 복원 단위이며, 해상도에 따라 연결 성분도 달라진다. 고가도로·장애물·경사·차선·실제 주행가능성을 검증한 도로망은 아니다.

일부 프레임의road분할은0건이다(예:source1829). 도로 안내의 **현재 프레임0점**으로 확인할 수 있으며, 해당 프레임 도로를 임의로 생성하지 않는다. 누적 도로는 다른 프레임의 관측이므로 계속 표시될 수 있다. 원본road검색·깊이·PCD는변경하지않는다. 검증근거는 KITTI `evidence/road_connectivity_20261107_01/`의 validation.json/graph.npz 및 browser_road_connectivity_*이다.

## 뷰 조작·독립 토글·패널 숨김 (2026-11-07)

- **BEV 카드**: Zoom In/Out은0.5~8배 범위의 지도 좌표 확대·축소,Zoom Reset은1배로 복귀한다. **Road ON/OFF**는 기존 표면 지도 위에 도로 셀 인접 연결선을 겹치거나 숨긴다. 이전 BEV display 모드 교체 방식은 Overlay Road connectivity 체크로 대체했다. **주행 기록 ON/OFF**는 주황 궤적과 현재 위치 마커를 함께 표시/해제한다. 궤적을 숨겨도 지도 좌표 범위가 바뀌지 않는다.
- **3D 상단**: View Reset은현재타임라인프레임의calibrated카메라시점으로복귀한다. 자유시점의선택카메라frustum은밝은노랑(255,195,48). **3D Mask ON/OFF**는도로분할색과선택검색의3D박스를표시/숨김하며,RGB마스크와독립이다. Show road는기존도로레이어전용스위치로유지한다.
- **RGB 카드**: RGB Mask ON/OFF는현재선택된저장검색의분할마스크만표시/숨김한다. 원본RGB/선택프레임/3D표시는유지한다. 검색선택이없으면원본RGB다. Clear object boxes는기존처럼선택을해제해검색박스/RGB마스크를지운다.
- **오른쪽 상단 패널 숨기기/보이기**: 기능패널만접고3D·RGB·BEV를전체너비로확장한다. 토글은숨긴상태에서도화면에남으며,복원시기존패널/검색선택/뷰크기비율을유지한다. 패널을숨겨도카드/상단버튼으로조작할수있다.
- 같은 옵션은오른쪽지도탭의3D segmentation mask/RGB segmentation mask/BEV zoom/Overlay Road connectivity/주행 기록에서도제어할수있고,버튼의ON/OFF상태와동기화된다.

## 마우스 BEV·박스·패널 너비·상단 재생 (2026-11-07)

BEV의 **Mask**와 **Box**는 독립 토글이다. 저장 검색/Result frame을 선택하면 해당 관측의분할지원점(청록)과3D OBB의평면투영(빨강)을표시한다. 전체관측은현재타임라인까지의결과를보여준다. 선택검색이없을때Mask는저장road분할을사용하고Box는표시하지않는다. Road는도로셀연결선전용이다. 3D/RGB토글과서로독립이며,RGB에도 **RGB Box**를추가했다(현재프레임마스크의2D경계박스).

BEV 이미지 위 휠은커서위치를기준으로0.5~8배줌,왼쪽드래그는패닝이다. 이미지종횡비에따른여백을고려하여같은좌표계의지도/도로/분할/박스/주행기록을함께이동한다. Zoom Reset은줌1배와중앙위치를복원한다. 제스처요청은중간이벤트를합치고마지막상태를보존한다.

오른쪽패널왼쪽구분선을좌우드래그하면너비를조절한다. 구분선에포커스한뒤좌우방향키도가능하다. 너비는localStorage에저장하여새로고침후복원하며,패널Show/Hide도수동너비를보존한다.

3D상단의재생/일시정지,이전/다음버튼,프레임슬라이더·번호입력은오른쪽타임라인과같은상태를사용한다. 수동프레임변경은재생을정지하며,번호는기존Frame과같이0부터시작한다. Reset은선택된현재프레임시점으로복귀한다.
