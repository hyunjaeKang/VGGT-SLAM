# YouTube 주행 영상 첫 90초 테스트

실행: 2026-11-06 UTC. [사용자 지정 영상](https://www.youtube.com/watch?v=2t1i5LYoZXo)의 첫 0–90초를 받아 실제 VGGT-SLAM 비디오 입력으로 처리했다.

## 입력

- 제목: KOREA DRIVE | Highway Driving Ambience 4K 2021 중부내륙고속도로 주행영상 백색소음 ASMR
- uploader: Godokhan Seoul Drive. 원 영상 길이: 3,597초.
- [다운로드한 clip.mp4](../logs/demo_inputs/youtube_2t1i5LYoZXo_90s_20261106/clip.mp4): **90.0초, 1280×720, 30fps, 2,700프레임, 약43MiB**.
- 영상 전용 H264 재인코딩 파일이며 원본 촬영 파일은 아니다. [출처·SHA256·조건](../logs/demo_inputs/youtube_2t1i5LYoZXo_90s_20261106/source.json), ffprobe.json, download.log 보존.
- 초기 검은 화면/fade를 확인해 추론에서는 frame 0–29를 제외했다. 실제 SLAM 범위는 **1–90초, source frame 30–2699**다. 다운로드한 90초 파일은 그대로 보존했다.

## 소량 확인과 최종 실행

처음 300프레임 smoke에서 disparity120은 키프레임4개만 선택하고 최대8.77초 간격을 만들어 입력이 성겼다. 한 번 낮춘45px를 전체 영상에 read-only 광류 검사해 474개, 최대1.6초/중앙0.133초 간격을 확인한 뒤 최종 실행했다. GT로 선택하거나 평가 결과에 맞춰 설정을 바꾼 것이 아니다.

```bash
.venv/bin/python main_realtime.py --camera video_file \
  --video logs/demo_inputs/youtube_2t1i5LYoZXo_90s_20261106/clip.mp4 \
  --video_start 30 --video_pacing offline --headless --device mps \
  --submap_size 8 --max_loops 0 --min_disparity 45
```

매 실행은 새 run ID를 만든다. 이번 결과: `logs/demo_runs/video_20261106T064802_616910000`.

| 항목 | 결과 |
|---|---:|
| 디코딩 프레임 | 2,670 |
| 선택·처리 키프레임 / 궤적 | 474 / 474 |
| backlog 드롭 | 0 |
| 서브맵 / 연결선 | 60 / 59 |
| RGB/depth 프레임 자산 | 533 (중첩59 포함) |
| 전체 색상 점군 | 43,058,292점, 모두 유한한 XYZ |
| PCD 크기 | 688,932,853 bytes (약657MiB) |
| capture+worker flush | 298.34초 |
| 모델 준비·최종 저장 포함 세션 | 313.86초 (약5분14초) |
| 서브맵 지연 p50 / p95 | 4.94 / 5.15초 |
| 루프 클로저 | OFF |
| GT / ATE | 없음 / N/A |

최종 키프레임 목록은 사전 flow 검사와 정확히 일치했다. [프레임 분할·pose ID·quaternion·PTS 검증](../logs/demo_runs/video_20261106T064802_616910000/evidence/video_integrity_01/validation.json) 통과. PTS 기반 `estimated_pts.tum`을 같은 폴더에 저장했다. [PCD 무결성](../logs/demo_runs/video_20261106T064802_616910000/evidence/pointcloud_integrity.json) 검사도 통과했다.

## 결과 보기

현재 캐시 뷰어: **http://localhost:8097**. 새 모델 추론이 아니라 저장된 결과를 표시한다.

```bash
.venv/bin/python demo.py view \
  --run logs/demo_runs/video_20261106T064802_616910000 --port 8097
```

전체 PCD는 보존하고 화면은 기본30만 점으로 제한한다. cache load1.09초/render5.08초를 별도로 측정했다. 이는 브라우저 최초 draw 지연이나 추론 속도가 아니다.

- [초기 지도 화면](../logs/demo_runs/video_20261106T064802_616910000/evidence/browser_youtube_01/initial.png)
- [궤적 미리보기](../logs/demo_runs/video_20261106T064802_616910000/evidence/trajectory_preview.png)
- [브라우저 검사](../logs/demo_runs/video_20261106T064802_616910000/evidence/browser_youtube_01/browser.json): WebSocket 연결, 타임라인/재생/끝 이동/점 수/전후 선택/Fit 성공, JS exception0.

큰 지도의 render가 수 초 걸리므로 browser 검사기는 고정2초 후 판정하는 대신 실제 끝 프레임·점 수 상태를 기다리도록 보강했다. 이 변경은 실제 Chrome으로 검증했고 Ruff 지정 검사·compileall·diff-check 통과. 이번 입력 실험 때문에 기존 전체 회귀/전체 모델 실험을 다시 반복하지 않았다.

## 판정과 한계

**비디오 입력→깊이·지도·서브맵→EOF 저장→캐시 재열기 경로는 성공했다.** 저장 수치와 파일 대응의 성공을 도로 지도 정확도 판정으로 해석하지 않는다. 독립적인 카메라 궤적/깊이 GT가 없어 실제 거리·위치·방향 오차나 누적 drift를 측정하지 않았다. 영상은 압축·재인코딩됐고 유리 반사/차량 보닛/움직이는 물체가 포함된다.

offline 처리이며 30fps 실시간 추론 증거가 아니다. 이 run의 객체 검색과 실제 루프 재방문은 검사하지 않았다. 해당 기능은 기존 별도 실험 증거를 유지한다.
