# 실시간 객체 지도 조사 원장

조사 기준: 2026-11-08 UTC. 요청 파일명은 26.11.09이다. 공식 저장소·공식 문서·저자 논문/프로젝트를 우선 확인했다. 전체 인터넷의 모든 관련 논문을 빠짐없이 조사했다고 주장하지 않는다. 아래41개 핵심 원문을 구현 선택과 직접 연결해 검토했다. 링크의 main은 변하므로 구현 착수 시 commit·checkpoint hash·model card·license를 다시 고정한다. 이번에는 새 모델을 설치하거나 benchmark하지 않았다.

## 권고

기존 VGGT-SLAM 지도 backend 유지 + 상주 semantic worker + 고정 클래스 경량 검출(가능하면 mask) + 2D ByteTrack + 선택 프레임의 정밀 mask + 완료 depth 이후 local-anchor 3D 승격. ROAD/sky는 객체 탐색과 분리한다. 이 Mac에서는 YOLO26n/s-seg 또는 검증된 YOLO11n-seg로 고정 클래스 baseline을 먼저 측정하고, COCO 밖 대상은 YOLOE-26s/YOLOE-11s의 frozen vocabulary를 비교한다. SAM3 CPU는 드문 정밀 fallback으로 유지한다. EdgeTAM CoreML은 box→mask 전파의 추가 후보이며 영구 객체ID는 별도 관리한다.

SceneVGGT/ConceptGraphs는 2D→3D/ID 설계 참고, StreamVGGT·RetrieveVGGT·HorizonStream·LingBot-Map은 mapping latency가 남을 때 별도 geometry adapter로 비교한다. SceneBound/RT-DETR-World/MetricTrail/S2Tok은 최신 연구 후보이며 코드·가중치·완전한 SLAM 기능·장치 재현성을 먼저 확인한다. CUDA가 필요하면 로컬 UI를 유지한 별도 worker를 설계한다.

전체 구조·계약·단계·수락 기준·상호작용 계산기는 [HTML 계획서](../../26.11.09.VGGT_SLAM.Plan.html)에 있다.

## 1차 자료 목록

| ID | 원문 | 공개/수정 시점 | 검토 결과 |
|---|---|---|---|
| S01 | [VGGT-SLAM 2.0](https://github.com/MIT-SPARK/VGGT-SLAM) | 2026-01 / 현재 README | 기존 submap·SL(4)·open-set 경로의 기준. Jetson 실시간 결과를 Mac에 전용하지 않음. |
| S02 | [VGGT-SLAM 2.0 논문](https://arxiv.org/abs/2601.19887) | 2026-01-27 | feed-forward 지도와 factor graph, Jetson Thor online 실증. 현재 로컬 환경의 성능 보장은 아님. |
| S03 | [SAM 3 공식 저장소](https://github.com/facebookresearch/sam3) | 현재 공식 안내 | 텍스트 기반 image/video segmentation. 공식 최신 설치는 Python≥3.12 / Torch≥2.7 / CUDA 환경 중심. |
| S04 | [SAM 3.1 release notes](https://github.com/facebookresearch/sam3/blob/main/RELEASE_SAM3p1.md) | 2026-03-27 | Object Multiplex와 공동 메모리. 128객체/H100에서 약7배라는 공식 조건; Mac CPU 측정값 아님. |
| S05 | [YOLOE 원저자 코드](https://github.com/THU-MIG/yoloe) | ICCV 2025 | 텍스트/시각 prompt로 box+instance mask. 고정 vocabulary 사전 계산 후보. |
| S06 | [YOLOE 최신 공식 문서](https://docs.ultralytics.com/models/yoloe/) | 현재, YOLOE-26 포함 | set_classes·prompt 종류·텍스트 encoder 사전 준비. prompt-free 모델은 set_classes 대상 아님. |
| S07 | [YOLO26 공식 문서](https://docs.ultralytics.com/models/yolo26/) | 2026 / 현재 문서 | 고정 클래스 경량 검출·분할 baseline. 공개 범위와 체크포인트 클래스 확인. |
| S08 | [Ultralytics model release](https://github.com/ultralytics/assets/releases) | v8.4.0, 2026-01-13 | YOLO26/YOLOE-26 공개 모델 존재 확인. 발표일·현재 문서 날짜를 구분. |
| S09 | [YOLO-World](https://github.com/AILab-CVC/YOLO-World) | CVPR 2024 | offline vocabulary의 prompt-then-detect. 빠른 box 대안이며 기본적으로 mask 없음. |
| S10 | [Grounding DINO](https://github.com/IDEA-Research/GroundingDINO) | 원저자 현재 코드 | text grounding box. 느린 정밀 확인 또는 희귀 클래스 fallback. |
| S11 | [SAM 2](https://github.com/facebookresearch/sam2) | 2024 / 현재 코드 | box/point prompt 이후 video mask propagation. 자체 텍스트 검출기는 아님. |
| S12 | [EdgeTAM](https://github.com/facebookresearch/EdgeTAM) | CVPR 2025 / 현재 코드 | on-device promptable tracking, CoreML export 제공. iPhone16fps는 이 Mac 측정값 아님. |
| S13 | [EdgeTAM CoreML 안내](https://github.com/facebookresearch/EdgeTAM/blob/main/tools/README.md) | 현재 export 안내 | encoder/prompt/mask decoder 경로와 compute-unit 선택. 메모리 전파까지 전체 Python 경로가 자동 ANE가 되는 것은 아님. |
| S14 | [ByteTrack](https://github.com/ifzhang/ByteTrack) | ECCV 2022 / 현재 코드 | 검출 box association과 track ID. 장거리 재방문3D 객체ID는 별도 필요. |
| S15 | [PIDNet](https://github.com/XuJiacong/PIDNet) | CVPR 2023 / 현재 코드 | road·sky 등 semantic segmentation 후보. Cityscapes 지식의 해변·실내 일반화는 별도 검증. |
| S16 | [CoreML export](https://docs.ultralytics.com/integrations/coreml/) | 현재 공식 문서 | Mac 배포 경로 참고. 선택 YOLOE checkpoint·frozen vocabulary export는 실제 parity 검사 필요. |
| S17 | [ONNX Runtime CoreML EP](https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html) | 현재 공식 문서 | provider와 operator 지원·partitioning 점검. provider 선택만으로 모든 연산 ANE 실행을 보장하지 않음. |
| S18 | [SceneVGGT 원저자 코드](https://github.com/HBVC-AI/SceneVGGT) | 2026-02 공개, 04 ICIP 수락 | 2D mask→3D와 VGGT tracking head/시간별 객체ID. README의 evaluation coming soon과 paper 링크 placeholder 확인. |
| S19 | [SceneVGGT 논문](https://arxiv.org/abs/2602.15899) | v2 2026-02-19 | sliding-window semantic SLAM. 저자 <17GB GPU 주장과 로컬 지원은 별개. |
| S20 | [ConceptGraphs](https://github.com/concept-graphs/concept-graphs) | 2023 / 현재 ali-dev 안내 | 다중 관측을 객체 map/scene graph로 통합. RGB-D 기반 경로를 단안 projective 좌표에 그대로 적용하지 않음. |
| S21 | [ConceptFusion](https://github.com/concept-fusion/concept-fusion) | RSS 2023 | 3D feature map에 open-set 특징 통합. dense feature 메모리 비용을 별도 측정. |
| S22 | [StreamVGGT](https://github.com/wzzheng/StreamVGGT) | 2025-07 / ICLR 2026 | causal attention과 KV cache로 streaming. loop graph·기존 VGGT 중간 feature 호환은 별도. |
| S23 | [FastVGGT](https://github.com/mystorm16/FastVGGT) | 2025-09 / ICLR 2026 | training-free token pruning. 긴 입력 가속을 현재 4~9 view submap에 그대로 기대하지 않음. |
| S24 | [InfiniteVGGT](https://github.com/AutoLab-SAI-SJTU/InfiniteVGGT) | 2026-01-06 | rolling memory와 장기 스트림. streaming state의 품질/자원 비교 후보. |
| S25 | [XStreamVGGT](https://github.com/ywh187/XStreamVGGT) | 2026-01 | KV pruning·quantization. CUDA kernel/정밀도 차이에 따른 이식 위험. |
| S26 | [RetrieveVGGT](https://github.com/zzctmd/RetrieveVGGT) | 2026-05 공개 / 10 수락 안내 | 고정 개수 frame retrieval로 context budget 제어. README clone URL과 실제 repo 경로 차이도 점검 필요. |
| S27 | [HorizonStream](https://arxiv.org/abs/2605.23889) | v2 2026-10-24 | 장기 causal geometric state. 기존 loop closure와 map correction adapter 별도. |
| S28 | [SceneBound](https://arxiv.org/abs/2611.00756) | 제출 2026-10-31 | pose coverage 기반 write budget와 drift에 따른 submap 종료. 코드/가중치 즉시 재현성 미확인. |
| S29 | [CUT3R](https://github.com/CUT3R/CUT3R) | CVPR 2025 | persistent-state 3D 대안. 기본 demo가 offline encoder batching을 쓰는 점·CUDA 설치 조건 구분. |
| S30 | [MASt3R-SLAM](https://github.com/rmurai0610/MASt3R-SLAM) | CVPR 2025 | 별도 SLAM baseline. 공식 CUDA/RTX4090 중심, Mac drop-in으로 보지 않음. |
| S31 | [Depth Anything 3](https://github.com/ByteDance-Seed/Depth-Anything-3) | 2025-11 / 현재 코드 | depth-ray/multi-view pose 대안. 모델 계열별 기능·license 다르며 새 depth만으로 loop SLAM이 완성되지는 않음. |
| S32 | [Video Depth Anything](https://github.com/DepthAnything/Video-Depth-Anything) | CVPR 2025 | video-consistent depth. 상대/metric 모델·temporal windows의 latency와 별도 pose backend 필요. |
| S33 | [VGGT-Segmentor](https://arxiv.org/abs/2604.13596) | v3 2026-05-22 | cross-view mask 대응 연구. VGGT attention만으로 pixel-perfect mask라고 가정하지 않는 근거. |
| S34 | [DART / DARTF](https://github.com/mkturkcan/DART) | 2026-03 / 현재 코드 | SAM3 backbone 공유·batched prompt decode, TensorRT와 학생 모델. fast path는 box 중심. |
| S35 | [RT-DETR-World](https://arxiv.org/abs/2610.09502) | v2 2026-11-05 | 최신 compact OVD 비교 후보. 초록은 code will be released라고 하므로 즉시 구현 후보에서 제외. |
| S36 | [S2Tok](https://arxiv.org/abs/2610.08978) | 2026-10-06 | persistent spatial tokens→3D Gaussians, 렌더 품질 연구. loop SLAM/semantic3D 완제품으로 보지 않음. |
| S37 | [LingBot-Map](https://github.com/Robbyant/lingbot-map) | 2026-04 / SDPA수정06-28 | streaming GCT와 reference/trajectory memory. CUDA/FlashInfer 경로를 Mac에 직접 전용하지 않음. |
| S38 | [MetricTrail](https://research.nvidia.com/labs/sil/projects/metrictrail/) | 게시일 미표시, 11-08 조회 | metric depth+sparse local optimization+DINOv3. intrinsics 조건·체크포인트·실행 의존성 확인 후 연구 후보. |
| S39 | [SAM3 LICENSE](https://github.com/facebookresearch/sam3/blob/main/LICENSE) | 현재 원문 | SAM License. 코드와 가중치 조건을 pin 단계에서 별도 기록. |
| S40 | [EdgeTAM LICENSE](https://github.com/facebookresearch/EdgeTAM/blob/main/LICENSE) | 현재 원문 | Apache-2.0 표기 확인. 사용 모델 전체 의존성/가중치 조건을 이 한 파일로 일반화하지 않음. |
| S41 | [YOLOE LICENSE](https://github.com/THU-MIG/yoloe/blob/main/LICENSE) | 현재 원문 | AGPL-3.0 표기. 제품 배포 시 선택 패키지와 가중치 조건 검토 대상으로 기록. |
