# TerraScene · Mapping Studio / 매핑 스튜디오

An interactive interface prototype and Korean engineering plan for a VGGT-SLAM 2.0 mapping demo. The interface, help and this README show English and Korean together.
VGGT-SLAM 2.0 매핑 데모를 위한 조작 가능한 화면 시제품과 한국어 개발 계획서입니다. 화면·도움말·이 README는 영어와 한국어를 함께 표시합니다.

## Open the app / 실행 방법

Open `web_app/dist/index.html` directly in a modern desktop browser. No package installation, external assets, inference server or model download is required. Open `dist/plan.html` for the development plan; the plan body remains in Korean. Standalone copies are in `standalone/`.
데스크톱 브라우저에서 `web_app/dist/index.html`을 직접 여세요. 패키지 설치, 외부 리소스, 추론 서버나 모델 다운로드가 필요하지 않습니다. 개발 계획서는 `dist/plan.html`이며 본문은 한국어로 유지합니다. 단일 파일 버전은 `standalone/`에 있습니다.

## Controls and features / 조작 방법과 기능

- **Replay / 재생:** Play, pause, seek and change speed. Use Open video to play a local file without upload. / 재생·정지·위치 이동·속도 조절을 지원합니다. 영상 열기로 로컬 파일을 업로드 없이 재생합니다.
- **3D view / 3차원 뷰:** Drag to orbit, scroll to zoom, and reset the view. Switch color, semantic and height layers. / 끌어서 회전하고 스크롤로 확대하며 시점을 초기화할 수 있습니다. 색상·의미 분류·높이 레이어를 전환합니다.
- **Navigation / 경로 탐색:** Select start or goal, click the map, and adjust the circular footprint radius. The second scenario blocks the passage. / 출발점 또는 목표점 지정 후 지도를 클릭하고 원형 점유 반경을 조절하세요. 두 번째 시나리오는 통로를 차단합니다.
- **Maps / 지도:** Inspect occupancy, footprint-inflated costs, connected components and occupied surface voxels. Adjust the height slice and unknown-space policy. / 점유·점유 반경을 반영한 비용·연결 영역·점유 표면 복셀을 확인하고 높이 범위와 미관측 공간 정책을 조절합니다.
- **Objects / 객체:** Filter sample objects by English or Korean names and click an object to highlight it. / 영어 또는 한국어 이름으로 예시 객체를 검색하고 클릭하여 강조합니다.
- **Export / 내보내기:** Save the synthetic session/map as JSON or visible points as PLY. / 합성 세션·지도를 JSON으로, 표시된 점군을 PLY로 저장합니다.

## Prototype boundary / 시제품의 범위

All reconstruction geometry, semantic objects, observed regions, keyframes and revisions are synthetic. Local video playback does not reconstruct the video and is unrelated to the sample maps. Exports explicitly record `synthetic=true` and `inference_connected=false`.
복원 형상·의미 객체·관측 영역·키프레임·지도 버전은 모두 합성 예시입니다. 로컬 영상은 복원하지 않으며 예시 지도와 무관합니다. 내보내기에는 `synthetic=true`와 `inference_connected=false`를 명시합니다.

A-star search uses eight-connected grid movement without corner cutting. Circular footprint search does not model car-like steering or dynamics. The 3D occupancy view shows occupied surfaces; probabilistic free/occupied/unknown volumes are planned. No model timing, confidence or GPU memory measurements are claimed.
A-star는 8방향 격자 이동을 사용하고 모서리 통과를 금지합니다. 원형 점유 반경 탐색은 차량 조향이나 동역학을 모델링하지 않습니다. 3차원 점유 화면은 점유 표면만 표시하며 확률적 비점유·점유·미관측 체적은 계획 단계입니다. 모델 처리 시간·신뢰도·GPU 메모리 실측 결과를 주장하지 않습니다.

The plan separates inspected upstream behavior from engineering proposals. Real engine integration needs a pinned source audit, license/weight compatibility checks, metric/gravity calibration and measurement. No third-party model weights are included.
계획서는 확인한 원본 동작과 설계 제안을 구분합니다. 실제 엔진 연동에는 고정된 소스 검토, 라이선스·가중치 호환성 확인, 미터 단위·중력 보정과 실측이 필요합니다. 외부 모델 가중치는 포함하지 않습니다.

## Folder and packaging / 폴더와 패키징

The folder is `web_app/` (formerly `TerraScene/`); the TerraScene brand and standalone HTML filenames are retained. Run the commands below from `web_app/`.
폴더명은 `web_app/`이며 이전 이름은 `TerraScene/`입니다. TerraScene 브랜드와 단일 HTML 파일명은 유지합니다. 아래 명령은 `web_app/`에서 실행하세요.

```sh
python package_deliverables.py
```

Output goes to `web_app/deliverables/`. The ZIP root is `web_app/`. Packaging refreshes `validation.json` and embeds the current scripts in the standalone page. The development plan body is unchanged.
결과는 `web_app/deliverables/`에 생성되며 ZIP 내부 최상위 폴더는 `web_app/`입니다. 패키징은 `validation.json`을 갱신하고 최신 스크립트를 단일 페이지에 포함합니다. 개발 계획서 본문은 변경하지 않습니다.

## Verification / 검증

```sh
node --check dist/core.js
node --check dist/app.js
node tests/core.test.js
node tests/interface.test.js
python build_plan.py
```

The interface test uses DOM/canvas stubs to check state changes, bilingual messages, Korean object search, dialogs and local-video boundaries. It does not replace visual browser checks. Building the plan regenerates `dist/plan.html` from `build_plan.py`.
인터페이스 테스트는 DOM·캔버스 대역으로 상태 전환, 영한 문구, 한국어 객체 검색, 대화상자와 로컬 영상의 범위를 확인합니다. 시각적 브라우저 검증을 대체하지 않습니다. 계획서 빌드는 `build_plan.py`에서 `dist/plan.html`을 다시 생성합니다.

## Abbreviations / 약어

- **VGGT:** Visual Geometry Grounded Transformer / 여러 영상의 기하 구조를 예측하는 모델.
- **SLAM:** Simultaneous Localization and Mapping / 동시 위치 추정 및 지도 작성.
- **JSON:** JavaScript Object Notation / 구조화된 데이터 형식.
- **PLY:** Polygon File Format / 점군·표면 저장 형식.
- **GPU:** Graphics Processing Unit / 그래픽 처리 장치.
- **DOM:** Document Object Model / 문서 객체 모델.

See the in-app Help and glossary for full explanations.
자세한 설명은 화면의 Help and glossary / 사용법 및 용어 설명을 여세요.
