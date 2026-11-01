# PandaSet 003 실행·평가 기록

2026-10-30, Apple Silicon MPS / Python 3.11.12 / PyTorch 2.3.1.

## 입력과 범위

입력은 `/Users/hyunjae.kang/9000_Data/9002_ExpData/pandaset/003/camera/front_camera`의
1920×1080 JPEG 80장이다. 기록 길이는 7.9004초이며 제공된 카메라 자세의 이동
거리는 약 75.40m다. 영상 80장의 파일 무결성을 확인했다. 원본 해상도로 읽지만
VGGT에는 기존 전처리대로 518×294 영상이 입력된다.

이번 실행은 RGB 기반 재구성, 궤적 추정, 서브맵 연결, 루프 제약 활성/비활성 비교,
PCD/궤적 저장, BEV/추정 등고선, 가벼운 브라우저 뷰어까지 포함한다.
PE/SAM3 객체 검색, LiDAR 형상 오차 평가, 다중 카메라 융합 및 실제 카메라 캡처는
실행하지 않았다.

## 실행 결과

두 실행 모두 `--submap_size 16 --min_disparity 0 --conf_threshold 25`로 모든
프레임을 사용했다. `--max_loops`만 각각 1과 0으로 변경했다.

| 항목 | 기본 루프 활성 | 루프 비활성 비교 실행 |
| --- | ---: | ---: |
| 처리 영상 / 저장 궤적 행 | 80 / 80 | 80 / 80 |
| 처리 시간 (모델 로딩·최종 저장 제외) | 74.01초 | 59.89초 |
| 일반 서브맵 | 5 | 5 |
| 추가 루프 제약 / 루프 서브맵 | 2 / 2 | 0 / 0 |
| 전체 점군 | 10,051,266점 | 9,594,391점 |
| 정렬 후 ATE RMSE | 0.558m | 0.290m |
| 정렬 후 최대 위치 오차 | 1.618m | 0.888m |
| 정렬로 추정한 축척 | 37.3872m/unit | 35.9068m/unit |

이번 구간에서는 루프 비활성 실행이 더 낮은 위치 오차를 보여 이를 기본 뷰어
결과로 선택했다. 이는 이번 한 구간의 결과이며 다른 주행에서도 루프 비활성이
좋다는 의미는 아니다.

## 궤적 평가 방법과 해석

`camera/front_camera/poses.json`의 카메라 위치와 추정 궤적의 정수 frame ID를
직접 대응했다. 원본 timestamp는 `timestamps.json`에서 가져와 오차 CSV에 기록했다.
같은 대응 프레임 전체를 사용해 양의 축척, 회전, 이동을 가진 proper Sim(3)를
최소제곱으로 추정하고, 정렬된 위치의 3차원 유클리드 오차 RMSE를 계산했다.
반사는 허용하지 않는다.

이 수치는 **정답 궤적에 축척·방향·위치를 맞춘 후의 위치 오차**다. 원래 모델이
GPS 좌표나 절대 축척을 추정한 성능을 의미하지 않는다. 거의 직선인 짧은 궤적이라
진행 방향 주위의 회전은 잘 구속되지 않는다. 기본 실행의 정렬 특이값 비율
(second/first)은 약 4.35e-5다.

기본 실행은 프레임 32↔16, 48↔32의 영상 쌍으로 루프 제약을 추가했다. 두 쌍은
전진 주행의 가까운 시점에 해당하므로 이를 실제 장소 재방문에 대한 성공 사례로
세면 안 된다. 가시 영역의 중첩으로 생긴 교차 제약과 실제 재방문은 구분해야 한다.
별도의 완전한 루프 경로로 검출 성능을 평가해야 한다.

## BEV와 높이 지도

두 실행 각각에 RGB BEV, 표면 높이, 추정 지면 등고선, 수치 격자 및 등고선 CSV를
생성했다. 위의 궤적 정렬에서 얻은 축척으로 m 단위로 환산했다. 변환의 출처는
각 BEV 폴더 `metadata.json`의 `scale_source`에 기록했다.

**높이 정확도는 검증되지 않았다.** 현재 BEV의 위쪽 방향은 추정 카메라의 평균
음의 Y축이다. 이 기준으로 계산한 카메라 높이 범위는 약 3.6m인 반면, 제공된
기준 자세의 world Z 범위는 약 0.157m다. 두 높이는 기준 방향이 다르며, 카메라
기울기·정렬·재구성 오차를 포함하므로 등고선의 변화가 실제 도로 경사라고
해석하면 안 된다. 계측용 지형도에는 중력 기준 정렬과 LiDAR 지면 검증이 필요하다.
정답 궤적의 축척을 맞추는 것만으로 이 문제가 해결되지는 않는다.

## 확인한 검증

- 두 실행의 모든 XYZ와 궤적이 유한값이며 PCD 헤더와 바이너리 크기가 일치한다.
- frame ID는 0~79이고 중복/누락이 없다. quaternion 길이는 1이다.
- BEV 격자의 점수 합계는 각 PCD 전체 점수와 일치한다. 지면 support가 부족한
  격자는 NaN으로 보존된다.
- Sim(3) 수학 검증 3개 통과: 알려진 변환 복원, 반사 배제, 정지 궤적 오류 처리.
- 새 평가 코드의 Ruff `E9,F63,F7,F82`, `git diff --check` 통과.
- 실제 Chrome에서 http://localhost:8081 연결, 30만 점 표시 및 JavaScript 오류
  없음 확인. 화면은 `logs/pandaset003_viewer.png`에 저장했다.

실제 영상은 약 10fps지만 이번 장치의 계산 속도는 약 1.1~1.3fps였다. 결과의
시간순 재생과 실시간 추론 성능을 구분해서 시연해야 한다.

## 재실행

기본 실행:

```bash
.venv/bin/python -u main.py \
  --image_folder /Users/hyunjae.kang/9000_Data/9002_ExpData/pandaset/003/camera/front_camera \
  --min_disparity 0 --max_loops 1 --vis_map --vis_voxel_size 0.01 \
  --log_results --log_path logs/pandaset003_poses.txt
```

비교 실행은 `--max_loops 0` 및
`--log_path logs/pandaset003_no_loops_poses.txt`로 변경한다.

평가:

```bash
.venv/bin/python scripts/evaluate_pandaset.py \
  --estimated_poses logs/pandaset003_no_loops_poses.txt \
  --camera_folder /Users/hyunjae.kang/9000_Data/9002_ExpData/pandaset/003/camera/front_camera \
  --output_dir logs/pandaset003_no_loops_evaluation
```

저장된 결과 표시:

```bash
.venv/bin/python scripts/view_saved_map.py \
  --point_cloud logs/pandaset003_no_loops_poses_points.pcd \
  --poses logs/pandaset003_no_loops_poses.txt --port 8081
```

## 산출물

- `logs/pandaset003_run.log`, `logs/pandaset003_no_loops_run.log`: 실제 실행 로그.
- `logs/pandaset003*_poses.txt`, `logs/pandaset003*_poses_points.pcd`: 궤적과 전체 점군.
- `logs/pandaset003_evaluation/`, `logs/pandaset003_no_loops_evaluation/`: 정렬·평가 JSON,
  프레임별 오차 CSV, 정렬된 궤적, 비교 그림.
- `logs/pandaset003_bev/`, `logs/pandaset003_no_loops_bev/`: BEV/높이/추정 등고선.
- `logs/pandaset003_validation.json`: 점수와 파일 유효성 검증 결과.
- `logs/pandaset003_viewer_validation.json`: 브라우저 검증 결과.

`logs/`는 git에서 제외되어 있으며 산출물은 이 워크스페이스에 존재한다.
