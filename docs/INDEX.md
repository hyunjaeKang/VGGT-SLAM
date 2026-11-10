# 문서 찾아보기

현재 기준: 2026-11-09. 원래 날짜가 있는 실험 보고서는 당시 기록을 유지하며 현재 상태는 별도 요약한다.

## 다음 세션의 읽는 순서

1. [SESSION_HANDOFF.md](SESSION_HANDOFF.md) — branch/remote/미커밋·프로세스·데이터·재개 프롬프트.
2. [CURRENT_STATUS.md](CURRENT_STATUS.md) — 구현/실증/계획 및 실제 수치·미검증 사항.
3. [DEMO_PROGRESS.md](DEMO_PROGRESS.md) — S00 이후 시간순 작업·검증 증거.
4. [26.11.09.VGGT_SLAM.Plan.html](../26.11.09.VGGT_SLAM.Plan.html) — V4 동시 객체 지도 계획, 모델 비교·실시간 예산·수락 기준.
5. [조사 원장](research/2026-11-09_realtime_object_mapping.md) — 기준일·원문41개·선택 이유.

## 사용하는 방법

- **처음 사용자:** [쉬운 HTML 설명서](USER_GUIDE.html) / [PDF](USER_GUIDE.pdf) / [Markdown](USER_GUIDE.md). V1~V5 차이·구동·사용·영상·속도 설명.
- [LIVE_V5.md](LIVE_V5.md): VGGT-SLAM 전용 V5, 해상도 최적화·KITTI 영상·실측.
- [LIVE_V4.md](LIVE_V4.md): 생성 중 사전 객체 검색 V4, 지연·검증 한계.

- [DEMO_VERSIONS.md](DEMO_VERSIONS.md): V1/V2/V3 버전 선택과 실행.
- [LIVE_V3.md](LIVE_V3.md): 디스크 영상·실제 지도/ROAD 생성·완료 후 검색·회전 수정.
- [MAP_STUDIO.md](MAP_STUDIO.md): 지도·검색·RGB·BEV·ROAD·UI 조작, 과거 쿼리와 현재 삭제 목록 구분.
- [DEMO_GUIDE.md](DEMO_GUIDE.md): CLI·환경·평가·이전 GUI 지원 경로; 끝의 최신 버전 안내도 확인.

## 실험·검토 기록

- [DEMO_RESULTS.md](DEMO_RESULTS.md): 기존 run 보고서. 최신 V3 요약은 CURRENT_STATUS와 진행 기록을 함께 확인.
- [DEMO_ACCEPTANCE_REVIEW.md](DEMO_ACCEPTANCE_REVIEW.md): 11-06 인수·객체 기하 검토. 이후 버전의 정확도를 일괄 보증하지 않음.
- [CODE_REVIEW.md](CODE_REVIEW.md): 초기 코드 검토. 당시 SAM3/TUM 미실행 상태는 후속 실제 실험으로 갱신됨.
- [YOUTUBE_90S_TEST.md](YOUTUBE_90S_TEST.md): 11-06 disparity45/trim30 실험. 현재 V3 사용자 disparity10 실행과 구분.
- [PANDASET003_TEST.md](PANDASET003_TEST.md), [KITTI360_0000_RUN.md](KITTI360_0000_RUN.md): 해당 데이터/조건의 검증과 한계.

## 보존된 원계획

- [temp_VGGT_SLAM_Plans.26.10.30.md](../temp_VGGT_SLAM_Plans.26.10.30.md)
- [temp_VGGT_SLAM_Prompt.26.10.30.md](../temp_VGGT_SLAM_Prompt.26.10.30.md)

원계획은 현재 구현의 출발점 기록이다. 다음 세션은 현재 증거를 확인하고 다음 미완료 단계부터 진행한다.

- [CLOSED_LOOP_GUIDE.md](CLOSED_LOOP_GUIDE.md): 전체영상/키프레임구분,루프성립조건,실험해석,V5선택검색복원.
