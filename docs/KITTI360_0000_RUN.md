# KITTI-360 0000 실행 결과

요청한 `/Users/hyunjae.kang/Downloads/2013_05_28_drive_0000_sync`의 이미지로 전체 시퀀스를 처리했다. 3D 점군, 카메라 궤적, RGB BEV, 표면 높이 및 표면 등고선을 저장했다. **이번 설정은 장거리 전역 정합에 실패했다. 결과는 기능 시연·오류 분석용이며 정확한 도로 지도나 지형도로 사용할 수 없다.**

## 입력과 처리 범위

- 입력: `image_00/data_rect`의 1408×376 PNG 11,518장. 원본은 수정하지 않았다.
- 원본 해상도 기준 광류 변위 임계값 50픽셀로 3,649장을 선택했다. 선택 목록은 `logs/kitti360_0000_selection.json`, 원본을 가리키는 심볼릭 링크는 `logs/kitti360_0000_keyframes/`에 있다.
- 선택한 전체 시퀀스를 처리했다. 모델 입력 해상도는 518×140이다.
- Apple Silicon MPS, 일반 서브맵 228개, 루프 제약용 서브맵 19개. 기록된 재실행 시간은 약 1,228초이며 키프레임 선택·평가·지도 출력 시간은 별도다.
- 저장 점군: **212,204,997점**, 약 **3.16 GiB**. 반복 관측과 루프 서브맵의 점이 포함된 수이며 고유 표면점 수가 아니다.

## 열어 보기

서버가 실행 중이면 <http://localhost:8082>에서 확인한다. 브라우저는 기본 30만 점을 표시하며 슬라이더로 최대 200만 점까지 조절한다. `Fit map`으로 장면에 맞춘다. 실제 Chrome에서 WebSocket 연결과 30만 점 표시를 확인했다. 화면 캡처는 `logs/kitti360_0000_viewer.png`이다.

서버를 다시 시작하려면 프로젝트 루트에서 실행한다.

```bash
.venv/bin/python scripts/view_saved_map.py \
  --point_cloud logs/kitti360_0000_poses_points.pcd \
  --poses logs/kitti360_0000_poses.txt --port 8082
```

주요 결과:

| 파일 | 내용 |
|---|---|
| `logs/kitti360_0000_poses_points.pcd` | 원본 좌표계의 전체 RGB 점군 |
| `logs/kitti360_0000_poses.txt` | 선택 프레임별 TUM 형식 카메라 자세. 첫 열은 초 단위 시간이 아닌 원본 프레임 ID |
| `logs/kitti360_0000_poses_camera_matrices.npz` | 투영행렬 및 프레임 ID 백업. 겹치는 프레임 포함 |
| `logs/kitti360_0000_bev/overview.png` | RGB BEV, 표면 높이, 표면 등고선 개요 |
| `logs/kitti360_0000_bev/bev_rgb.png` | 격자별 상부 표면 RGB |
| `logs/kitti360_0000_bev/surface_elevation.png` | 셀 내 높이 90백분위수 |
| `logs/kitti360_0000_bev/surface_contours.png` / `.svg` | 건물·수목을 포함하는 표면 등고선 |
| `logs/kitti360_0000_bev/contour_lines.csv` | 표면 등고선 좌표·높이 |
| `logs/kitti360_0000_bev/rasters.npz` / `metadata.json` | 격자·좌표변환·샘플링 및 제외 범위 |
| `logs/kitti360_0000_evaluation/trajectory_comparison.png` | 기준 궤적과 추정 궤적 비교 |
| `logs/kitti360_0000_evaluation/trajectory_metrics.json` | 정렬·위치오차 수치 |
| `logs/kitti360_0000_validation.json` | 파일·유한값·프레임 ID 검증 결과 |

## 정확도와 중요한 한계

공식 KITTI-360 `data_poses.zip`에서 해당 시퀀스의 카메라 기준 자세를 받아 **사후 평가에만** 사용했다. 다운로드 출처는 `logs/kitti360_0000_reference/source.json`에 기록되어 있다. SLAM 추론에는 기준 자세, LiDAR, GPS 또는 정답 깊이를 넣지 않았다.

기준 궤적 길이는 약 **8.403 km**이다. 선택 프레임 중 3,598개가 기준 프레임 ID와 정확히 일치했다. 기준 자세가 없는 51개는 보간하지 않고 평가에서 제외했다. 전체 일치 위치에 하나의 Sim(3) 변환을 맞춘 뒤의 위치 오차는 다음과 같다.

| 지표 | 결과 |
|---|---:|
| ATE RMSE | **321.266 m** |
| 위치오차 중앙값 | 289.774 m |
| 최대 위치오차 | 1,409.076 m |
| 맞춘 스케일 | 0.412278 m / 복원 단위 |

정렬 후에도 궤적이 기준 경로와 크게 다르고 장거리 구조가 접히거나 압축되었다. 이 평가는 같은 궤적으로 스케일·회전을 맞춘 결과이며, KITTI 공식 구간별 drift 점수가 아니다. 지도 축의 미터 표시는 이 사후 적합 스케일에 따른 것으로 실제 측량 정확도를 뜻하지 않는다. 수직축도 이 정렬로부터 얻었으므로 독립적인 중력·고도 검증이 아니다.

루프 제약은 19건 수락되었다. 기준 자세가 있는 18건 중 17건의 실제 위치 간격은 2m 미만, 나머지 한 건은 약 5.3m였다. 한 건은 기준 자세가 없어 검증하지 못했다. 이는 19개의 서로 다른 장소를 뜻하지 않으며 같은 재방문 구간과 중복 쌍이 포함된다. 장소 재인식이 대체로 맞더라도 전역 기하 정합까지 정확하다는 뜻은 아니다. 세부 목록은 `logs/kitti360_0000_loop_reference_checks.json`, 이미지 예시는 `logs/kitti360_0000_loop_examples.png`에 있다.

## BEV와 등고선 해석

전체 점군에서 균일한 인덱스 간격으로 200만 점을 표본 추출했다. 극단적인 투영 좌표 때문에 화면이 축소되는 문제를 줄이기 위해, 이 표본의 변환된 XYZ 각 축에서 양쪽 0.1백분위 꼬리를 제외했다. **최종 1,989,839점**을 1m 격자로 표시했다. 제외 범위는 metadata에 기록했으며 전체 PCD는 그대로 보존했다. 이 미리보기는 전체 원시 좌표 범위를 보여주는 그림이 아니다.

기존 도로 색상·궤적 기반 지면 추정은 충분한 지지 셀을 확보하지 못했다. 따라서 **지면 등고선을 만들지 않았다.** 대신 `--surface_only` 모드로 셀별 상부 표면 P90 높이와 표면 등고선을 출력했다. 건물, 차량, 수목이 포함되며 지형 고도나 주행 가능 영역으로 해석하면 안 된다. 높이 기준은 첫 카메라 위치다. 지면 배열은 모두 NaN, 지면 지지점 수는 0이다. 관측이 부족한 셀은 보간하지 않는다. 표면 등고선만 관측 셀 안에서 가우시안 평활화한다.

## 재현

기존 키프레임 선택을 재사용한 실제 실행 명령:

```bash
.venv/bin/python -u main.py \
  --image_folder logs/kitti360_0000_keyframes \
  --min_disparity 0 --max_loops 1 \
  --log_results --log_path logs/kitti360_0000_poses.txt --headless
```

`--min_disparity 0`은 이미 선택한 프레임을 다시 줄이지 않기 위한 설정이다. 원본 폴더로 직접 실행할 경우에는 `--image_folder /Users/hyunjae.kang/Downloads/2013_05_28_drive_0000_sync/image_00/data_rect --min_disparity 50`을 사용한다. 같은 로그 경로로 다시 실행하면 결과를 덮어쓰므로 별도 경로를 지정하는 편이 좋다.

```bash
.venv/bin/python scripts/evaluate_kitti360.py \
  --estimated_poses logs/kitti360_0000_poses.txt \
  --reference_poses logs/kitti360_0000_reference/cam0_to_world.txt \
  --output_dir logs/kitti360_0000_evaluation

.venv/bin/python scripts/export_bev_maps.py \
  --point_cloud logs/kitti360_0000_poses_points.pcd \
  --poses logs/kitti360_0000_poses.txt \
  --meters_per_unit 0.412277774964921 \
  --up_vector -0.045755747152 0.998545660338 -0.028512730882 \
  --max_points 2000000 --clip_percentile 0.1 --surface_only \
  --cell_size 1 --output_dir logs/kitti360_0000_bev
```

## 실행 중 수정한 코드와 검증

- 큰 점군을 프레임 단위로 스트리밍 저장하고 뷰어에서 메모리 매핑으로 읽도록 변경했다. 전체 점군을 여러 번 메모리에 복제하지 않는다.
- 루프 검색의 프레임별 GPU 동기화를 서브맵 단위 벡터 연산으로 줄였다.
- 첫 실행은 추론을 마친 뒤 카메라 자세 저장에서 부적절한 회전행렬 오류가 발생했다. 투영행렬 P와 -P의 동일성을 이용해 분해 전 부호를 정규화했고, 부호가 다른 합성 카메라로 회귀 검증했다.
- 헤드리스 실행과 투영행렬 백업을 추가하고 점군을 자세 변환보다 먼저 저장해 저장 단계 오류 시 복구 자료를 남기도록 했다.
- PCD 왕복·원자적 저장·프로젝트 변환·검색 일치성·카메라 분해·희소 기준 프레임 매칭·합성 경사면·지면 없는 표면 출력 등을 테스트했다. 실행 결과는 `logs/large_map_tests.txt`에 있다.
- 실제 전체 PCD 좌표의 유한값, 선택 프레임 ID 일치, 모든 자세의 유한값·단위 쿼터니언, 지도 표본 수 일치와 지면 미생성을 검증했다.

이번 실행으로 단안 3D 복원, 카메라 자세 추정, 장소 재인식·루프 제약, 오프라인 지도 저장·시각화, BEV·표면 높이 출력을 확인했다. 선택적 객체 검색·분할 모델, 실시간 카메라 입력, LiDAR 기반 기하 검증은 실행하지 않았다. 정확한 장거리 지도 제작은 아직 해결되지 않았다.
