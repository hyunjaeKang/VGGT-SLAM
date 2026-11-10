from pathlib import Path
import html

ROOT = Path(__file__).parent
sections = []
def add(title, body):
    sections.append((title, body))
def table(headers, rows):
    def td(x): return f'<td>{x}</td>'
    return '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+x+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(td(x) for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def ul(items): return '<ul>'+''.join('<li>'+x+'</li>' for x in items)+'</ul>'

add('개발 방향과 완료 범위', '''
<p class="lead">VGGT-SLAM 2.0을 기하 복원의 기반으로 사용하고, 그 위에 의미 정보·확률적 점유 공간·주행 가능 영역·비용·연결성을 차례로 추가한다. 첫 완성 데모는 실시간 주행 제어보다, 영상 재생과 지도 생성의 시간적 일관성을 검증하는 연구용 프로그램으로 정의한다.</p>
<div class="callout"><b>이번에 제공하는 결과</b><p>공식 자료와 공개 소스 검토, 이 개발 계획서, 조작 가능한 웹 화면 시제품, 예시 격자에서 실제 실행되는 비용·연결성·경로 계산이다. 시제품의 영상 장면·객체·점군·관측 마스크·키프레임은 합성 예시이며 VGGT-SLAM을 실행한 결과가 아니다. 로컬 영상은 브라우저에서 재생할 수 있지만 지도 복원과 연결되어 있지 않다.</p></div>
<p>권장 순서는 ① 사용 조건·환경 확인 → ② 영상과 기하 복원 → ③ 거리·좌표 검증 → ④ 점유 지도 → ⑤ 평면 비용·연결성 → ⑥ 객체·동적 물체 → ⑦ 오프로드 지형과 차량 운동학이다. 하나의 단계가 불안정한 상태에서 다음 지도 레이어를 정상 결과로 표시하지 않는다.</p>
<p>개발 예상은 전담 개발자 1명 기준 핵심 데모 6~8주, 차량·오프로드 확장 포함 9~12주다. 실제 모델 사용 허가, 장비 예약, 데이터 수집에 걸리는 시간은 별도다. 아래 수치 목표는 구현 검증용 제안이며 측정된 성능 보장이 아니다.</p>''')

add('요구사항과 기존 기능의 경계', table(['요구 기능','VGGT-SLAM에서 확인한 범위','추가 개발과 완료 판정'],[
['영상 재생 중 3차원 장면 생성','이미지 폴더 처리와 온라인 카메라 진입점, 증분 점군 표시 [S1-S3]','파일 재생 시각 유지, 프레임 식별, 처리 지연 표시. 재생 시점 이후 관측을 지도에 섞지 않는다.'],
['사물 인식','텍스트 질의로 선택 프레임을 찾고 마스크와 3차원 상자를 생성하는 선택 기능 [S2]','연속 검출·추적·다중 시점 객체 결합·객체별 불확실성·동적 분리. 질의 검출과 전체 장면 인식은 구분한다.'],
['2차원 지도','3차원 점군·카메라 정보가 지도 생성 입력으로 사용 가능','관측된 지지면·차체 높이·장애물에 따라 free / occupied / unknown 격자를 만든다.'],
['비용 지도','주행용 비용 레이어는 별도 구현 대상으로 확인','차량 형상, 거리, 경사, 거칠기, 미관측, 관측 나이를 반영한다.'],
['연결성 검사','위치 그래프의 연결 관계와 이동 가능성은 다른 문제','차량이 통과 가능한 셀의 연결 성분과 실제 경로를 계산한다.'],
['3차원 점유 지도','점군 표시 자체는 자유 공간을 증명하지 않음','깊이 관측 광선으로 비점유·점유 증거를 누적하고 미관측은 보존한다.'],
['검증 가능한 데모','기하 결과 로그와 뷰어가 출발점','동일 지도 버전의 점유·비용·경로, 재생 기록, 설정, 지연, 검증 보고서를 함께 저장한다.']
]) + '<p>첫 버전의 2차원 지도는 단일 지지면을 가정한다. 다층 건물·교량·고가 아래·비탈길은 2.5차원 높이 지도 또는 층별 연결 그래프로 확장한다.</p>')

add('저장소 검토 결과와 확인 한계', '''
<p>검토 기준일은 2026-11-04이다. 현재 기본 브랜치는 2.0이며 1.0은 <code>version1.0</code>에 있다 [S1]. 아래 내용은 웹에서 확인한 공식 파일과 논문을 기반으로 한다. 이 환경에서는 저장소 전체 복제와 실제 모델 실행을 수행하지 못했다. 정확한 커밋 식별자는 구현 시작 시 확보해야 한다.</p>''' + table(['파일','확인한 동작','우리 프로그램의 연결 지점'],[
['<code>main.py</code> [S2]','광학 흐름 기반 키프레임 선택 → 예측 → 점 추가 → 그래프 최적화 → 시각화. 기본 새 프레임 16장, 겹침 1장.','<code>run_predictions</code>, <code>add_points</code>, <code>graph.optimize</code> 이후 불변 관측·변환 정보를 내보내는 어댑터를 둔다.'],
['<code>main_realtime.py</code> [S3]','카메라의 start/capture/stop 계약, 배경 처리 스레드, 공유 데이터 잠금과 백로그 제한.','파일 영상도 같은 FrameSource 인터페이스로 공급하되, 겹침 프레임 보존·종료 시 남은 묶음 처리를 명시한다.'],
['<code>vggt_slam/graph.py</code> [S4]','GTSAM의 SL4 변수와 요인을 사용한다. 보정 행렬을 포함한 get_homography가 있다.','이 변환을 강체 자세로 그대로 해석하지 않는다. 키프레임별 수정 목록과 지도 버전을 발행한다.'],
['<code>vggt_slam/map.py</code> [S5]','정렬된 서브맵과 의미 프레임 검색, 카메라·세계 점군 내보내기 경로가 확인된다.','외부 맵 저장소는 관측 식별자와 원시 깊이를 별도로 보존한다.'],
['<code>setup.sh</code> [S6]','SALAD 포크, VGGT_SPARK, Perception Encoder, SAM 3 등을 설치한다.','기하 전용 환경과 의미 처리 환경을 분리하고 정확한 의존성 버전을 잠근다.'],
['<code>requirements.txt</code> [S7]','torch 2.3.1, torchvision 0.18.1, viser 0.2.23 고정과 gtsam-develop 의존성이 있다.','Blackwell 장비에서는 기존 작업 환경을 덮어쓰지 않고 별도 환경에서 조합을 검증한다.'],
['README와 공식 논문 [S1,S8]','기존 기능·실험 조건·제약을 확인했다.','문서의 real-time을 모든 프레임의 즉시 지도 갱신으로 해석하지 않는다.']
]) + '''<div class="callout amber"><b>추가 소스 감사가 필요한 부분</b><p><code>solver.py</code>, <code>submap.py</code>, <code>viewer.py</code> 전체 내부 구현은 이 검토에서 확보하지 못했다. 텐서 모양, 카메라 축 방향, 색상 순서, 포즈 저장 방식, 신뢰도 필터와 복구 동작은 첫 단계에서 실제 코드와 예제로 확인한다.</p><p><code>graph.py:get_projection_matrix()</code>에는 <code>projection_matrix</code>를 정의한 뒤 <code>projection_matri</code>를 반환하는 철자 불일치가 보인다 [S4]. 해당 함수를 호출하는 최소 재현으로 확인하고, 호출 경로에서 필요한 경우 수정한다. 이 문서에서는 실행으로 재현한 결함으로 단정하지 않는다.</p></div>''')

add('2.0의 구조와 실시간 성능 해석', '''
<p>2.0은 키프레임별 그래프 제약 구조를 바꾸어 기존의 왜곡·평면 퇴화 문제를 줄인다. 내부는 여전히 SL(4) 최적화다. 이를 단순히 Sim(3) 기반으로 교체된 시스템이라고 설명하면 안 된다. 원 논문은 절대 거리 척도를 추정하지 않는다고 명시하며, 단색 벽과 재구성 불일치 등의 실패를 논의한다 [S8].</p>''' + table(['항목','공식 논문에서 제시한 조건 [S8]','데모에서의 해석'],[
['데스크톱 처리량','RTX 3090, 서브맵 16장: 의미 임베딩 제외 약 8.4 FPS, 포함 약 6.3 FPS','선택된 키프레임의 평균 처리량이다. 30 FPS 영상의 모든 프레임으로 30번씩 완전한 지도가 생성된다는 뜻이 아니다.'],
['온보드 처리량','Jetson Thor, 서브맵 4장: 약 3.5 FPS','12 GB 노트북 성능으로 전용할 수 없다.'],
['서브맵 추론 시간','서브맵 16장의 VGGT 추론 약 1,248 ms','묶음 처리 지연·프레임 수집 시간·통신·지도 통합을 합쳐 사용자 지연을 측정해야 한다.'],
['장면 품질','포즈 중심 최적화와 입력 장면에 따른 제한','시각적으로 그럴듯한 점군과 통행 가능한 지도 품질을 별도 평가한다.']
]) + '''<p>실제 프로그램에는 <b>입력률·화면 재생률·키프레임 처리률·지도 발행률</b>을 각각 표시한다. 30 FPS 영상 표시, 2~8 FPS 기하 처리, 0.5~2 Hz 지도 발행은 시작 실험 범위일 뿐이다. 측정 이후 목표를 확정한다. 빠른 화면 갱신을 모델 성능으로 표시하지 않는다.</p>''')

add('사용 조건과 실행 전 확인', '''
<p>외부 SLAM 저장소의 라이선스가 모든 코드·가중치·모델에 동일하게 적용되지는 않는다. 특히 회사 또는 국방 관련 연구에서는 아래 구성을 사용 가능하다고 가정하고 설치·재배포를 시작하지 않는다. 이 항목은 실제 사용 경로를 결정하기 위한 사전 확인이며 법률 해석을 대신하지 않는다.</p>''' + table(['구성 요소','확인한 조건','개발 결정'],[
['VGGT-SLAM 저장소 [S9]','BSD 2-Clause','원 저장소의 고지 의무와 다른 의존성 조건을 함께 기록한다.'],
['VGGT_SPARK 포크 [S10]','CC BY-NC 4.0','어텐션 검증에 쓰는 포크 코드 자체의 비상업 조건까지 확인한다.'],
['기본 facebook/VGGT-1B 가중치 [S11]','CC BY-NC 4.0','회사 내부 연구라는 이유만으로 허용된다고 가정하지 않는다.'],
['VGGT-1B-Commercial / 최신 VGGT 코드 [S12,S13]','별도 VGGT 라이선스와 허용 사용 정책. 군사·전쟁 관련 항목과 운송 기술 관련 제한 문구 존재.','체크포인트만 교체해 문제가 해결된다고 가정하지 않는다. 정확한 목적과 계약에 대한 권한을 확인한다.'],
['Perception Encoder [S14]','코드 LICENSE.PE: Apache 2.0','해당 모델 체크포인트·연관 구성의 조건도 기록한다.'],
['SAM 3 [S15]','별도 SAM 라이선스','모델 접근과 실제 적용 조건을 확인한다.'],
['SALAD 포크 [S6,S16]','원 프로젝트는 GPL v3, 설치 스크립트는 별도 포크를 받음','사용 포크·가중치 조건, 배포 범위와 결합 방식을 확인한다.']
]) + '''<div class="callout amber"><b>실행 계획의 분기</b><p>조건이 확인되면 VGGT 어댑터로 진행한다. 조건이 맞지 않으면 화면·지도·비용·연결성 모듈은 그대로 개발하면서, 사용 가능한 기하 백엔드를 같은 관측 계약에 연결한다. 대체 알고리즘과 의존성은 별도 검토한다. 이번 화면 시제품은 모델 가중치를 다운로드하거나 포함하지 않는다.</p></div>''')

add('시스템 구성과 모듈 경계', '''
<p>기하 엔진, 지도 엔진, 사용자 화면을 독립 프로세스로 나눈다. 첫 실제 연동은 원래 Viser 뷰어와 새 화면을 동시에 띄워 기하가 일치하는지 확인한다. 새 렌더러로의 완전 교체는 그 다음에 수행한다.</p>
<div class="architecture"><div><b>입력·시간</b><span>File / camera / simulator</span><span>FrameSource · ReplayClock</span><span>frame + timestamp + epoch</span></div><div><b>기하·의미</b><span>VGGT adapter · keyframes</span><span>metric / gravity validation</span><span>objects · dynamic observations</span></div><div><b>지도·탐색</b><span>3D occupancy · elevation</span><span>2D costs · free-space graph</span><span>route · revision snapshots</span></div><div><b>표시·기록</b><span>video · scene · maps</span><span>telemetry · quality state</span><span>export · reproducible replay</span></div></div>''' + table(['모듈','주요 책임','입출력'],[
['<code>FrameSource / ReplayClock</code>','파일·카메라·시뮬레이터 입력 통일, 재생 시계와 처리 시계 분리','시간·원본 번호·보정 정보가 붙은 FramePacket'],
['<code>GeometryAdapter</code>','기존 코드의 추론·그래프 최적화를 감싼다. 원시 깊이와 수정된 변환을 보존','ObservationBatch, PoseRevision, TrackingState'],
['<code>SemanticWorker</code>','질의 검출·객체 결합·동적 후보 처리','픽셀 마스크, 객체 후보, 연속 객체 기록'],
['<code>MetricAligner</code>','미터 척도·좌표·지지면 검증과 보정 이력','MetricState, WorldAlignment'],
['<code>OccupancyBuilder</code>','깊이 광선의 비점유·점유 증거 통합','3차원 희소 격자와 관측 상태'],
['<code>TerrainProjector / CostBuilder</code>','지지면·높이·차량 외형을 사용해 주행 레이어 계산','2차원 또는 2.5차원 격자와 비용 설명'],
['<code>ConnectivityService</code>','연결 성분·경로·차량 형상 검사','reachable / blocked / insufficient_evidence + 경로'],
['<code>SessionStore / Gateway</code>','관측 원본·지도 버전·실험 설정·지연 기록과 전달','불변 스냅샷, 이벤트, 다운로드']
]) + '''<p>실행 배치는 두 가지다. <b>개발 기준:</b> 서버의 기하·지도 프로세스 + 노트북 브라우저. <b>온디바이스 실험:</b> 동일한 인터페이스의 경량 설정을 노트북에서 측정. 제공한 호스팅 화면은 화면 시제품이며, GPU 추론 서버 역할을 하지 않는다.</p>''')

add('비디오 입력, 재생과 처리 지연', ul([
'파일 입력은 디코딩 프레임 번호와 원본 표시 시각을 함께 보존한다. 가변 프레임률, 회전 메타데이터, 크롭·리사이즈·왜곡 보정 후 카메라 행렬 갱신을 처리한다. 영상에 이미 그려진 경로·날짜·상자는 원 장면 복원 평가에서 분리한다.',
'<b>완전 처리 모드:</b> 선택한 관측을 버리지 않고 처리한다. 처리가 느리면 영상 재생을 기다리게 하거나, 재생과 지도 시각 차이를 표시한다. 저장 결과의 재현성이 우선이다.',
'<b>최신성 모드:</b> 입력 시각을 따라가며 큐를 제한하고 오래된 미처리 후보를 버린다. 이미 확정된 겹침 프레임·관측은 유지하고 프레임 누락과 구간 점프를 기록한다.',
'입력 큐 2~4 프레임, 대기 서브맵 1개를 시작 설정으로 둔다. 영상 해상도·키프레임 간격·서브맵 4/8/16장·의미 처리 빈도를 순서대로 조정한다. 영상 표시 큐와 기하 큐는 공유하지 않는다.',
'원본 시각 t_capture, 선택 시각 t_select, 기하 완료 t_geometry, 지도 발행 t_publish, 화면 표시 t_render를 측정한다. 지도 나이 = 현재 소스 시각 - 지도에 반영된 마지막 관측 시각으로 표시한다.',
'영상 탐색 시 새로운 processing_epoch를 발행한다. 과거 스냅샷을 불러와 그 시점까지 재실행하고, 이전 epoch의 늦게 도착한 결과를 버린다. 미래 관측을 과거 지도에 표시하지 않는다.',
'파일 종료·취소 시 마지막 불완전 서브맵의 처리 정책을 명시한다. 최소 입력 수가 충족되면 남은 관측을 처리하고, 그렇지 않으면 미처리로 기록한다. 일시정지·재시작·오류 상태를 화면과 로그에서 일치시킨다.'
]))

add('거리 척도와 좌표 보정', '''
<p>기하 결과의 미터 단위 정확성이 검증되기 전에는 차량 크기·경사·거리·경로 결과를 물리적 통과 가능성으로 해석하지 않는다. 화면에는 <code>scale_valid</code>, <code>gravity_valid</code>, <code>tracking_valid</code>를 별도로 둔다.</p>''' + table(['항목','실행 절차','권장 시작 판정 기준'],[
['카메라 좌표','카메라 x 오른쪽, y 아래, z 전방을 검증. 화면용 축 변환을 별도 관리한다.','가상 점의 투영·역투영 오차 1 px 이내인 단위 시험'],
['세계 좌표','세계 x 전방, y 왼쪽, z 위를 기본으로 정한다. 기하 맵과 세계 프레임의 변환 방향을 문서화한다.','축·단위·행렬 방향을 포함한 합성 장면 검사 통과'],
['절대 척도','실측 두 점 거리 또는 신뢰 가능한 깊이·LiDAR·시뮬레이터 정보로 유사 변환을 맞춘다.','보정에 쓰지 않은 거리 3개 이상에서 오차 5% 이하를 목표로 시작'],
['중력·지지면','알려진 수직 방향이나 관성 정보 사용. 초기 평면 적합은 신뢰도 있는 추정으로만 취급한다.','수평 기준면 법선 오차 3° 이내 목표, 비탈을 수평으로 강제하지 않음'],
['관측 품질','깊이 범위·신뢰도·재투영·다중 시점 일치성을 검사한다.','화면에 rejected / accepted 비율과 사유 표시'],
['보정 갱신','척도·방향 변경 시 모든 파생 지도와 경로를 무효화한다.','변경 이전 버전의 물리 단위 경로가 발행되지 않음']
]) + '''<p><code>H</code>를 키프레임 카메라 공간에서 맵으로 가는 보정된 동차 변환이라고 할 때, 표면점은 <code>X_map = dehom(H · [D K⁻¹ u, 1])</code> 형식으로 처리한다. <code>dehom</code>은 마지막 좌표로 나누는 연산이다. 실제 방향은 고정한 소스에서 확인한다. SL(4) 행렬을 강체 회전·이동 행렬처럼 사용하거나 동차 나눗셈을 생략하면 안 된다.</p>
<p>물리 광선 통합은 유클리드 기하로의 보정이 타당한지 검사한 뒤 수행한다. 변환한 광선 시작점과 끝점을 사용하고, 동차 분모가 0에 가까워지거나 광선 구간에서 부호가 바뀌는 경우 통합하지 않는다. 포즈·내부행렬을 분해해 사용하는 경로는 전체 점 변환과 재투영이 일치하는지 확인한다. 거리 척도를 단순히 맞추는 것만으로 모든 프로젝트 왜곡이 해결되었다고 가정하지 않는다.</p>''')

add('3차원 점유 지도 생성', '''
<p>첫 구현은 CPU 기반 희소 확률 격자 또는 OctoMap 어댑터를 사용한다. OctoMap은 비점유·점유·미관측을 표현하는 기준으로 적합하다 [S17]. GPU 기반 표면·거리장 가속이 필요해지면 nvblox를 별도 어댑터로 검토하되, 거리장과 점유 확률을 같은 값으로 취급하지 않는다 [S18].</p>''' + ul([
'깊이와 카메라 정보에서 관측 광선을 만든다. 관측 시작부터 신뢰 가능한 표면 앞까지는 비점유 증거, 끝점 주위의 불확실성 구간에는 점유 증거를 준다. 표면 뒤, 가려진 영역, 관측되지 않은 셀은 미관측으로 둔다.',
'희소 격자에는 log-odds, 관측 수, 마지막 관측 시각, 출처, 지도 버전, 동적 상태를 저장한다. 확률이 0.5라는 이유만으로 미관측이라고 판정하지 않고 observed 플래그를 별도로 둔다.',
'시작 설정: voxel 0.10~0.20 m 실내 / 0.20~0.40 m 실외, p_hit=0.65, p_miss=0.40, p_occ≥0.70, p_free≤0.35. 수치는 센서 모델 가정이며 학습 깊이에 맞춰 검증·보정한다.',
'L_new = clip(L_old + w·(logit(p_sensor)-L_prior), L_min, L_max). 보정되지 않은 모델 신뢰도를 점유 확률로 직접 복사하지 않는다. 동일 광선 묶음의 상관성과 반복 관측 과신을 제한한다.',
'관측 식별자 (session, frame_id, pixel_block)로 겹침 이미지·루프 폐쇄 이미지의 중복 증거를 제거한다. 시점별 마스크와 광선 원본을 보존해 재통합을 가능하게 한다.',
'하늘, 반사, 투명 물체, 먼 거리, 불안정한 깊이, 모션 경계는 별도 제외 또는 낮은 가중치로 처리한다. 무효 깊이를 최대거리 광선으로 바꾸어 자유 공간을 만들지 않는다.',
'표면만 복셀화한 결과는 occupied surface layer로 부른다. 이를 완성된 probabilistic occupancy라고 표시하지 않는다. 시제품의 3차원 점유 화면은 이 표면 예시 단계다.'
]) + '''<p>메모리는 지역 작업 영역과 전역 희소 타일로 제한한다. 활성 반경·해상도·타일 수·원시 관측 캐시 한도를 설정하고, 오래된 관측은 디스크로 내린다. 100×100×10 m 영역을 0.1 m 밀집 격자로 만들면 1억 셀이므로 작은 타입을 써도 다중 레이어의 비용이 빠르게 증가한다.</p>''')

add('객체 인식과 의미 지도', '''
<p>기존 선택 기능은 텍스트 질의를 이용한 객체 검색의 출발점이다. 데모의 연속 의미 지도에는 프레임 검출과 세계 공간 결합을 추가한다. 초기 객체 집합은 차량·사람·수목·기둥·울타리·벽·큰 장애물로 한정하고, 지면·하늘은 별도 영역 클래스로 다룬다.</p>''' + ul([
'1단계: 공식 질의 경로를 감싸고 입력 텍스트, 선택 프레임, 마스크, 3차원 상자를 저장한다. 검색 결과의 3차원 위치를 영상과 동시에 강조한다.',
'2단계: 선택 키프레임에서만 분할을 수행한다. 마스크 안의 신뢰 가능한 깊이로 3차원 점을 올리고 경계 혼합을 제거한 뒤, 다중 시점 연관으로 영속 객체 식별자를 부여한다.',
'3단계: 객체별 클래스 분포, 위치·크기 불확실성, 관측 프레임 목록, 첫·마지막 시각, 동적 여부를 보존한다. 한 장의 질의 응답만으로 전체 객체가 인식되었다고 표시하지 않는다.',
'의미 모델은 기하 처리보다 낮은 우선순위로 실행한다. 12 GB 환경에서 동시에 적재되지 않으면 별도 프로세스·서버 또는 순차 로딩을 사용한다. 먼저 기하 전용 측정으로 한계를 찾는다.',
'움직이는 사람·차량은 일시 레이어에 보존하고 정적 점유에 누적하지 않는다. 충분히 정지한 물체만 정책에 따라 정적 레이어에 승격하며, 사라진 객체는 관측 나이와 재관측으로 제거한다.',
'표면 분류와 물리 통과 가능성을 구분한다. 식생이라는 의미만으로 통과 가능하다고 판정하지 않고, 높이·밀도·지지면·차량 외형의 근거와 함께 평가한다.'
]) + '''<p>같은 연구진의 FOUND-IT은 주행 가능 영역과 계층적 3차원 장면 그래프를 더하는 직접적인 후속 연구다 [S19]. 그러나 이 계획에서는 코드·가중치의 현재 공개 범위와 사용 조건을 확인하기 전까지 필수 의존성으로 두지 않는다.</p>''')

add('2차원·2.5차원 지형과 비용 지도', '''
<p>색상 점군을 위에서 본 이미지는 주행 지도가 아니다. 차량의 바닥 지지와 차체·천장 간격을 고려해 주행 레이어를 만든다. 경사 지형에서는 단일 전역 높이 컷 대신 지역 지지면을 기준으로 높이를 계산한다.</p>''' + table(['레이어','계산','통행 판정'],[
['관측 상태','깊이 광선으로 관측된 공간과 시각·신뢰도','미관측은 기본 차단, 탐사 모드에서만 잠정 허용'],
['지지면 / 높이','관측된 지면의 높이와 법선·분산','지지면 근거가 없으면 unknown 또는 unsupported'],
['장애물 / 차체 공간','지지면부터 차량 높이와 여유까지의 점유 공간 검사','충돌 또는 천장 간격 부족은 hard block'],
['경사 / 단차','지역 평면의 기울기와 인접 지지면 높이 차이','차량 제한을 넘으면 hard block'],
['거칠기','지역 높이 잔차의 강건한 분산·범위','허용 범위 안에서는 soft cost'],
['낭떠러지 / 음의 장애물','기대 지지면 부재·급격한 하강·관측 불확실성','보이는 구멍과 가려진 지면을 구분, 근거 부족 시 보수적 차단'],
['거리 / 여유','장애물 거리장과 차량 형상·위치 불확실성','가까울수록 비용 증가, 충돌 영역은 차단'],
['일시 장애물 / 노후화','동적 객체 예측·마지막 관측 시각','시간에 따라 재검사·감쇠']
]) + '''<p>먼저 hard_feasible을 결정하고, 통과 가능한 셀에서만 <code>C = w_d C_distance + w_s C_slope + w_r C_roughness + w_u C_uncertainty + w_t C_age</code>를 계산한다. 가중치 합은 1로 정규화하고 원 레이어를 모두 저장한다. 서로 다른 단위의 값을 보정 없이 합산하지 않는다.</p>
<p>시작 예시는 2차원 해상도 0.20 m, 실내 최대 경사 8° / 오프로드 15°, 단차 0.15 m이다. 실제 차량 한계가 아니며 차량 프로필의 실측 제약으로 교체한다. 차량 반경은 여유·위치 오차를 더한 값으로 사용한다. 원형 근사는 개발 1단계에만 쓰고 실제 차량은 회전된 다각형과 높이로 검사한다.</p>
<p>비용 출력 계약 예시: 0~252 soft cost, 253 여유 한계, 254 충돌, 255 미관측. Nav2의 팽창 비용과 unknown 공간 설정을 참고할 수 있다 [S20,S21]. 우리 내부 데이터에는 observed/support 상태를 별도 보존하여 숫자 하나로 의미를 잃지 않게 한다.</p>''')

add('연결성 검사와 경로 검증', '''
<p>연결성의 질문은 “지도 그래프가 이어져 있는가”가 아니라 “이 차량이 관측된 공간에서 출발점부터 목적지까지 통과 가능한가”다. 화면에 서로 다른 의미의 그래프를 함께 표시할 때는 위치 그래프, 자유 공간 연결 성분, 의미 장소 그래프를 구분한다.</p>''' + ul([
'평면 기준 버전: 장애물 팽창 후 통행 가능한 셀의 연결 성분을 계산한다. 시작·목적 셀이 유효하고 같은 성분이면 A* 경로를 계산한다. 8방향 탐색에서 대각선으로 두 장애물 모서리 사이를 통과하지 못하게 한다.',
'출력은 reachable / blocked / insufficient_evidence / stale_map으로 나눈다. 미관측 때문에 실패한 경우 장애물이 관측되어 실패한 경우와 다른 사유를 표시한다.',
'첫 경로는 위치만 고려한 원형 로봇 경로다. 차량용 단계에서는 방향·최소 회전 반경·후진 허용·최대 경사·차체 높이를 상태에 포함하는 Hybrid A* 또는 상태 격자 탐색을 사용한다.',
'모든 경로는 차체 외형과 이동 중 휩쓸리는 영역을 다시 검사한다. 경로를 부드럽게 만드는 후처리 이후에도 충돌·커브 한계를 다시 확인한다.',
'객체를 목적지로 지정할 때 객체 중심이 아니라 관측된 접근 지지면에서 후보를 만든다. 후보별 접근 방향·여유·관측 상태를 검사한다.',
'다층 공간에서는 층별 지지면 노드와 물리 연결 경계를 사용한다. 같은 평면 좌표를 공유한다는 이유로 다른 층을 연결하지 않는다.'
]) + '''<p>시험 장면은 열린 통로, 완전 차단, 차량보다 좁은 문, 대각선 틈, 낮은 천장, 미관측 통로, 비탈·단차, 막다른 길을 포함한다. 제공한 시제품은 원형 점유 영역과 8방향 격자 경로를 검토하는 단계이며 차량 운동학은 구현하지 않았다.</p>''')

add('루프 폐쇄, 재통합과 지도 버전', '''
<p>루프 폐쇄로 과거 키프레임의 변환이 수정되면 이미 쌓인 점유 증거·객체 위치·비용·경로도 수정되어야 한다. 표시 점군만 옮기면 지도에 유령 장애물과 오래된 경로가 남을 수 있다.</p>''' + ul([
'원본 깊이, 카메라 정보, 마스크, 광선 식별자와 키프레임별 변환을 보존한다. 서브맵의 단일 강체 변환만 저장하는 방식으로 제한하지 않는다.',
'새 포즈 최적화 결과는 PoseRevision(epoch, pose_revision, changed_frame_ids)으로 전달한다. 변경된 관측이 영향을 준 타일과 새로 영향을 받는 타일을 모두 찾는다.',
'첫 정확성 기준은 전체 원시 관측으로의 결정론적 재생성이다. 부분 타일 재생성은 이 결과와 일치하는지 검증한 뒤 도입한다.',
'대수적 증거 제거를 구현할 경우 원시 비포화 기여를 보존한다. 누적값을 잘라 저장한 log-odds에서 단순히 반대 값을 빼는 방법은 정확한 역통합이 아니다.',
'새 점유·지형·비용·연결성 스냅샷을 배경에서 만들고 준비가 완료되면 하나의 map_revision으로 원자적으로 교체한다. UI는 작업 중 상태와 이전 결과의 시각을 표시한다.',
'경로는 (epoch, map_revision, robot_profile_revision)을 참조한다. 어느 하나가 바뀌면 기존 경로를 stale 처리하고 재계산한다. 이전 버전의 경로를 새 지도 위에 정상 결과로 표시하지 않는다.'
]))

add('데이터 계약과 서비스 인터페이스', '''
<p>아래 이름과 형식은 이번 계획에서 제안하는 신규 계약이다. VGGT-SLAM의 기존 공개 인터페이스라고 해석하지 않는다. 첫 단계에서는 실제 텐서·포즈 구조를 조사해 어댑터에서 검증·변환한다.</p>''' + table(['계약','필수 필드','검증'],[
['FramePacket','session_id, processing_epoch, frame_id, timestamp_ns, original_size, processed_size, image_ref, K, preprocessing_transform','시간 단조성, 이미지·내부행렬 크기 일치, 파일 해시'],
['GeometryObservation','observation_id, frame_id, submap_id, depth_ref, confidence_ref, corrected_H, accepted_mask_ref, pose_revision','유한값, 변환 방향, 재투영·중복 제거'],
['MetricState','scale_valid, gravity_valid, anchor_source, scale, world_alignment, uncertainty, revision','미터 결과 발행 가능 여부'],
['MapSnapshot','epoch, map_revision, source_time_ns, valid_through_frame, metric_revision, voxel_resolution, grid_origin, bounds, observed_mask, quality_state','일관된 버전·시간·축·단위'],
['RouteResult','map_revision, robot_profile_revision, status, reason, path, length, min_clearance, provisional','지도 버전·차량 제약·불확실성 일치'],
['Telemetry','input_rate, render_rate, keyframe_rate, map_publish_rate, queue_depth, dropped_frames, map_age, peak_memory, stage_latency','측정 창·단위·측정 방법 보존']
]) + '''<pre>POST /sessions                 세션·설정 생성
POST /sessions/{id}/source      파일 또는 입력 장치 지정
POST /sessions/{id}/playback    play / pause / seek / speed
GET  /sessions/{id}/snapshot    버전이 고정된 지도 메타데이터
POST /sessions/{id}/route       시작·목표·차량 프로필·지도 버전
POST /sessions/{id}/query       객체 텍스트 질의
GET  /sessions/{id}/export      설정·결과·측정 기록
WS   /sessions/{id}/events      진행·지도 교체·오류·지연 이벤트</pre>
<p>메타데이터는 작은 JSON, 영상은 별도 스트림, 큰 점군·격자는 타일 단위 이진 데이터로 전달한다. 먼저 스냅샷을 받고 순번이 붙은 변경분을 적용하며 누락 시 다시 동기화한다. UI에 모든 깊이·점군을 매 프레임 JSON으로 전송하지 않는다.</p>''')

add('화면 설계와 실제 연동 상태', '''
<p>화면 이름은 <b>TerraScene / Mapping Studio</b>다. 주요 조작은 영상 재생, 장면 회전, 지도 레이어 선택, 출발·목표 지정, 차량 크기 조정이다. 데이터 종류와 연결 상태를 항상 상단에 표시한다.</p>''' + table(['영역','표시 내용','현재 시제품 / 실제 연동 계획'],[
['상단 상태','입력 선택, 예시 표시, 모델 연결 상태, 결과 내보내기','합성 상태를 명시. 실제 연동은 source / processing / published 시각을 추가한다.'],
['지표 카드','보이는 점 수, 관측 면적, 키프레임, 연결성','점 수·면적·성분은 예시 데이터에서 계산. 키프레임과 버전은 재생 시간으로 생성한다.'],
['좌상단 영상','입력 영상, 프레임 번호, 시각, 인식 오버레이','생성된 장면 또는 로컬 영상. 로컬 영상에는 합성 검출 상자를 덧씌우지 않는다.'],
['중앙 3차원 장면','색상·의미·높이 보기, 궤적, 객체 선택','실제 3차원 좌표의 합성 점군을 회전·확대한다. 실제 엔진 출력은 후속 연결한다.'],
['좌하단 지도','점유·비용·연결성 탭, 시작·목표·경로','예시 격자에서 실제 비용과 A* 경로를 계산한다.'],
['중하단 3차원 점유','높이 구간, 관측·미관측 구분, 해상도','합성 표면 복셀을 표시. 완성 엔진에서는 비점유·미관측 절단면 보기를 추가한다.'],
['우측 검사기','경로 가능 여부·길이·성분·객체 검색','예시 객체 필터·강조와 연결성 계산. 언어 모델 질의는 아니다.'],
['아래 재생 막대','재생·일시정지·속도·탐색','로컬 파일 재생과 합성 예시를 지원. 모델 추론과의 동기화는 후속 작업이다.']
]) + '''<p>완성 버전은 scale invalid, tracking lost, mapping delayed, rebuilding, disconnected, insufficient evidence를 명확한 문구와 색상·아이콘으로 표현한다. 의미 검색과 객체 추적 결과에는 근거 프레임으로 이동하는 기능을 붙인다. 색상만으로 상태를 전달하지 않는다.</p>
<p>화면 시제품은 단일 HTML로도 실행할 수 있게 별도로 제공한다. 전체 소스 묶음의 <code>dist/index.html</code>을 직접 열면 조작할 수 있고, 같은 폴더의 <code>plan.html</code>에서 계획서를 볼 수 있다. 원격 모델·외부 글꼴·외부 스크립트에 의존하지 않는다.</p>''')

add('장비와 메모리 실험 계획', '''
<p>주 실험은 서버에서 시작하고, 노트북은 화면과 재생·소규모 기하 검증에 사용한다. 12 GB 환경에서 기하·의미 모델 전체가 동시에 실시간으로 동작한다고 가정하지 않는다.</p>''' + table(['설정','목적','기록할 항목'],[
['Geometry only, submap 4/8/16','처리량과 업데이트 지연·품질의 기준점 확보','최대 장치 메모리, 호스트 메모리, 입력·키프레임률, 서브맵 시간'],
['동일 영상의 해상도·선택 간격 변화','정확도와 큐 지연의 절충 측정','지도 나이의 중앙값·95·99백분위, 누락 프레임'],
['Semantic off / low-rate / on-demand','객체 기능의 추가 비용 분리','객체 처리 시간, 기하 지연 증가, 동시 적재 메모리'],
['CPU occupancy / 가속 대안','추론과 지도 작업의 자원 경합 확인','통합·재구성 시간, 타일 수, 전송량'],
['10분 연속 재생과 재방문','캐시·메모리·루프 폐쇄 안정성','장치·호스트 메모리 추이, 재통합 최고 지연, 재생 탐색 정확성']
]) + '''<p>서버에서 공유 장치를 사용할 경우 작업 스케줄러 정책에 맞춰 자원을 예약한다. 12 GB 상당의 한도는 그 장치에서 검증된 설정만 허용하고, 메모리 실패 시 자동으로 해상도나 데이터 일부를 몰래 바꾸지 않는다. 변경 설정을 새 실행으로 기록한다. 화면 점군 다운샘플링은 전송·렌더링 비용만 줄이며 기하 엔진의 내부 메모리를 직접 줄이지 않는다 [S1].</p>''')

add('구현 일정과 산출물', table(['단계 / 기간','작업','장치 사용','단계 종료 조건'],[
['P0 / 2~3일','사용 조건, 정확한 커밋, 환경 잠금, 공개 예제 실행, 좌표·소스 감사','서버 GPU 필요: 첫 추론만','실행·사용 가능 경로, 재현 명령, 입력·출력 계약과 오류 재현 기록'],
['P1 / 1주','FileSource, ReplayClock, 키프레임·기하 어댑터, 원래 뷰어와 대조','GPU 필요','한 영상에서 프레임·깊이·좌표·점군 동기 표시, 종료 시 남은 입력 처리'],
['P2 / 1주','척도·중력 보정, 관측 보존, 3차원 확률 점유 기준 구현','GPU: 기하 / CPU: 지도','가려진 공간 unknown, 광선 앞 free, 끝점 occupied; 중복 관측 불변'],
['P3 / 1주','평면 지지면, 2차원 지도, 팽창 비용, 연결 성분·A*','저장 관측 사용 시 GPU 불필요','차단·좁은 문·대각선·미관측 사례의 기대 결과 통과'],
['P4 / 1주','텍스트 질의, 객체 다중 시점 결합, 동적 레이어','GPU 필요: 의미 작업','객체 선택과 영상 근거 연결, 이동 객체의 정적 잔상 방지'],
['P5 / 1주','루프 폐쇄 재통합, 스냅샷 교체, 역방향 탐색','기록 재생·일부 GPU','수정 관측의 전체 재생성과 일치, 오래된 경로 차단'],
['P6 / 1~2주','통합 측정, 실제 영상 검증, 메모리·지연 조정, 데모 패키징','서버·노트북 각각 측정','10분 재생, 결과 내보내기, 동기화·성능·품질 보고서'],
['P7 / 추가 3~4주','오프로드 2.5차원 지도, 차량 다각형, 운동학 경로, 음의 장애물','GPU: 기하 / 지도·경로 별도 측정','경사·낭떠러지·차량 통과성의 독립 검증']
]) + '''<p>핵심 6~8주 추정에는 단계 간 통합·수정 여유를 포함한다. 각 단계는 마지막 열의 종료 조건이 충족된 뒤 확장한다. 작은 영상에서 실패하는 동안 데이터 규모를 키우지 않는다. 별도 서버 환경과 반복 가능한 관측 재생 덕분에 지도·화면 개발 대부분은 GPU 없이 진행할 수 있다.</p>''')

add('시험 데이터와 정량 평가', '''
<p>첫 데이터는 짧고 기준이 명확해야 한다. 30~90초의 정적 장면으로 시작해 닫힌 루프가 있는 3~5분 영상, 마지막에 10분 연속 재생으로 확장한다. 주간·야간·가림·동적 물체·울타리·나무·단색 벽·급회전은 실패 조건으로 포함한다.</p>''' + table(['검증 범주','자료 / 시험','평가와 제안 기준'],[
['투영·좌표','알려진 카메라·상자·평면의 합성 기하','투영 오차 1 px 이내, 축·단위·척도 일관'],
['궤적·표면','공식 공개 예제 후 TUM 계열 또는 기준 깊이가 있는 자료','상대·절대 궤적 오차, 표면 정확도·완전도. 척도 정렬 여부를 명시'],
['점유','광선 앞·표면·뒤 영역이 알려진 작은 장면','점유/비점유 정밀도·재현율과 unknown 유지율; 가려진 공간을 free로 만들지 않음'],
['주행 가능성','벽·문·천장·지지면·낭떠러지의 독립 사례','물리 충돌 경로 0건인 고정 회귀 세트, 미관측 실패의 사유 구분'],
['객체','수동 검증한 소수 클래스·다중 시점','검출·3차원 위치·객체 식별 유지·동적 잔상 비율'],
['루프 폐쇄','동일 수정 관측의 전체 재생성과 증분 재생성','점유 값·비용·경로 유효성의 허용 오차 내 일치'],
['재생 탐색','앞·뒤 반복 탐색과 세션 재시작','미래 관측 혼입 0건, epoch 및 revision 불일치 0건'],
['실시간성','입력·기하·지도·화면의 개별 타임스탬프','큐가 계속 증가하지 않음. 지도 나이 95백분위 목표 2초는 장비 측정 후 확정'],
['안정성','10분 장면·연속 질의·루프 폐쇄','메모리 한도 준수, 오류·재시작·미처리 관측 기록 완전']
]) + '''<p>BeamNG를 사용할 경우 영상·깊이·자세·의미 정답의 실제 노출 기능과 좌표계를 먼저 확인한다. 정답을 척도 보정에 사용한 실험은 “보정 보조 입력 사용”으로 표시하고, 카메라 단독 실험과 분리한다. 보정용 경로와 검증용 경로·장면을 나누며, 정답을 비용 지도 생성에 몰래 넣지 않는다.</p>''')

add('시연 시나리오와 실패 대응', '''
<p>발표용 시연은 5분 내외로 구성한다. 실행 영상과 처리 상태는 언제나 같은 시각·지도 버전을 가리켜야 한다.</p>''' + table(['순서','조작','보여줄 증거'],[
['0:00~1:00','입력 영상 재생, 점군·카메라 궤적 확인','소스 시각·처리 시각·척도 상태, 새 관측만 증가'],
['1:00~2:00','객체 질의 후 해당 위치·근거 영상 표시','객체 마스크·깊이·3차원 결합의 연결'],
['2:00~3:00','점유·높이·비용 레이어 전환, 차량 크기 변경','unknown / free / occupied 차이, 차체 여유에 따른 비용 변화'],
['3:00~4:00','출발·목표 선택, 차단·좁은 통로 사례 전환','연결·차단·근거 부족 사유와 실제 경로'],
['4:00~5:00','루프 폐쇄·과거 탐색·결과 내보내기','지도 버전 교체, 경로 재계산, 재현 가능한 설정·관측 기록']
]) + '''<p>처리 지연은 마지막 정상 지도의 나이와 백로그로 표시한다. 추적 실패는 통행 판정을 중단하고 마지막 유효 지도와 실패 시작 시각을 남긴다. 척도 무효 시 물리 단위 경로는 잠근다. 메모리 한도 도달 시 조용히 일부 지도를 삭제하지 않고 활성 영역 제한과 내려둔 타일을 표시한다.</p>
<p>허용되지 않는 모델 구성이나 필수 환경 실패가 발생해도 화면·관측 계약·지도 시험은 합성 또는 허용된 기록 데이터로 계속 개발할 수 있다. 실제 모델 데모의 성공 여부와 화면 시제품의 완성 여부는 별도 보고한다.</p>''')

add('권장 코드 구성과 재현 기록', '''
<pre>terrascene/
  sources/         파일·카메라·시뮬레이터 입력
  geometry/        VGGT 어댑터·좌표·품질 검증
  semantics/       질의·분할·객체 결합·동적 후보
  mapping/         광선 통합·점유·높이·타일 재생성
  navigation/      비용·연결 성분·경로·차체 검사
  session/         원시 관측·스냅샷·재생 시계·내보내기
  gateway/         명령·이벤트·타일 전달
  web/             영상·3차원·지도·상태 화면
  configs/         장비·차량·입력·실험 프로필
  tests/fixtures/  작은 기준 장면과 실패 회귀 자료
  reports/         측정·오차·메모리·실패 원인</pre>
<p>실행 디렉터리에는 manifest, 정확한 저장소 커밋, 모델 식별·해시, 환경 잠금, 카메라·척도 보정, 원본 영상 해시, 선택·누락 프레임, 원시 깊이·마스크, 키프레임 변환 이력, 지도 타일, 객체, 경로, 성능 기록을 저장한다. 모델 가중치를 결과 묶음에 자동 포함하지 않는다.</p>
<p>이번 소스 묶음은 <code>dist/index.html</code>, <code>dist/core.js</code>, <code>dist/app.js</code>, <code>dist/plan.html</code>, 계획서 생성기와 검증 코드를 포함한다. 서버 모델 구현은 이 묶음의 완료 범위가 아니다. 첫 실제 연결 작업은 P0의 소스 감사와 공개 예제 재현이다.</p>''')

glossary=[
('VGGT','Visual Geometry Grounded Transformer','영상에서 카메라·깊이·점 등 기하 구조를 예측하는 변환기 모델'),
('SLAM','Simultaneous Localization and Mapping','동시 위치 추정과 지도 작성'),
('3D / 2D / 2.5D','Three-dimensional / Two-dimensional / Two-and-a-half-dimensional','3차원 / 2차원 / 평면 좌표에 높이·지형 정보를 붙인 표현'),
('UI','User Interface','사용자 조작 화면'),('RGB / RGB-D','Red, Green, Blue / RGB plus Depth','색상 영상 / 색상과 깊이'),
('SL(4)','Special Linear group of degree four','행렬식 1인 4×4 행렬의 군'),('SE(3)','Special Euclidean group in three dimensions','3차원 강체 회전·이동'),('Sim(3)','Similarity transformation group in three dimensions','3차원 회전·이동·균일 척도 변환'),
('GTSAM','Georgia Tech Smoothing and Mapping','요인 그래프 기반 추정 라이브러리'),
('SAM','Segment Anything Model','범용 분할 모델'),('PE','Perception Encoder','영상·언어 의미 표현 모델'),('CLIP','Contrastive Language-Image Pretraining','영상·언어의 대조 학습 방식'),('SALAD','Sinkhorn Algorithm for Locally Aggregated Descriptors','장소 영상 검색용 표현 집계 방법'),('RAFT','Recurrent All-Pairs Field Transforms','광학 흐름 추정 모델'),
('GPU / CPU','Graphics Processing Unit / Central Processing Unit','그래픽 처리 장치 / 중앙 처리 장치'),('CUDA','Compute Unified Device Architecture','NVIDIA 병렬 계산 플랫폼'),('GB','Gigabyte','10억 바이트 단위. 장치 메모리 표기 관례에 주의'),
('FPS / Hz / ms / ns / px','Frames Per Second / Hertz / millisecond / nanosecond / pixel','초당 프레임 / 초당 주기 / 밀리초 / 나노초 / 화소'),
('LiDAR','Light Detection and Ranging','빛으로 거리와 공간을 측정하는 센서'),
('A* / Hybrid A*','A-star / Hybrid A-star','휴리스틱 격자 탐색 / 연속 차량 운동학을 결합한 탐색'),
('TSDF / ESDF','Truncated Signed Distance Function / Euclidean Signed Distance Function','절단 부호 거리 함수 / 유클리드 부호 거리 함수. 점유 확률과는 다른 표현'),
('JSON','JavaScript Object Notation','구조화 데이터 텍스트 형식'),('PLY / PCD','Polygon File Format / Point Cloud Data','점군·표면 형식 / 점군 저장 형식'),('HTML / CSS','HyperText Markup Language / Cascading Style Sheets','웹 문서 구조 / 화면 스타일 언어'),('WS','WebSocket','지속 연결 기반 양방향 통신'),('POST / GET','HTTP method names; Hypertext Transfer Protocol','서버 명령·조회에 쓰는 웹 전송 방식'),
('MP4','MPEG-4 Part 14; Moving Picture Experts Group','영상·음성 컨테이너 형식'),('BSD','Berkeley Software Distribution','소프트웨어 라이선스 계열'),('CC BY-NC','Creative Commons Attribution-NonCommercial','저작자 표시·비상업 조건'),('GPL','GNU General Public License; GNU is Not Unix','자유 소프트웨어 공개 라이선스'),('TUM','Technical University of Munich','관련 공개 영상·깊이 평가 데이터의 제공 기관'),('SHA','Secure Hash Algorithm','커밋·파일 무결성 식별에 쓰이는 해시 계열')]
glossary.extend([('MIT / SPARK','Massachusetts Institute of Technology / Sensing, Perception, Autonomy, and Robot Kinetics','저장소 제공 기관 / 연구실 이름'),('m / m² / s / °','meter / square meter / second / degree','미터 / 제곱미터 / 초 / 각도'),('RTX / Jetson / Blackwell','NVIDIA product and architecture names','장치 제품·구조의 고유명으로 취급하며 별도 표준 축약어 풀이를 가정하지 않는다')])
add('용어와 축약어', '<p>화면과 계획서에서 사용한 축약어를 아래에 풀어 썼다. 설정 필드와 소스 함수명은 원문 식별자를 유지한다.</p>'+table(['표기','원어','뜻'],glossary))

sources=[
('S1','공식 저장소와 README','https://github.com/MIT-SPARK/VGGT-SLAM'),
('S2','이미지 폴더 처리 main.py','https://github.com/MIT-SPARK/VGGT-SLAM/blob/main/main.py'),
('S3','온라인 처리 main_realtime.py','https://github.com/MIT-SPARK/VGGT-SLAM/blob/main/main_realtime.py'),
('S4','위치 그래프 graph.py','https://github.com/MIT-SPARK/VGGT-SLAM/blob/main/vggt_slam/graph.py'),
('S5','서브맵 관리 map.py','https://github.com/MIT-SPARK/VGGT-SLAM/blob/main/vggt_slam/map.py'),
('S6','설치 스크립트','https://github.com/MIT-SPARK/VGGT-SLAM/blob/main/setup.sh'),
('S7','의존성 목록','https://github.com/MIT-SPARK/VGGT-SLAM/blob/main/requirements.txt'),
('S8','VGGT-SLAM 2.0 논문','https://arxiv.org/html/2601.19887v2'),
('S9','VGGT-SLAM 라이선스','https://github.com/MIT-SPARK/VGGT-SLAM/blob/main/LICENSE'),
('S10','VGGT_SPARK 라이선스','https://github.com/MIT-SPARK/VGGT_SPARK/blob/main/LICENSE.txt'),
('S11','기본 VGGT-1B 모델 카드','https://huggingface.co/facebook/VGGT-1B'),
('S12','VGGT 공식 저장소와 상업용 체크포인트 안내','https://github.com/facebookresearch/vggt'),
('S13','최신 VGGT 라이선스·허용 사용 정책','https://github.com/facebookresearch/vggt/blob/main/LICENSE.txt'),
('S14','Perception Encoder 코드 라이선스','https://github.com/facebookresearch/perception_models/blob/main/LICENSE.PE'),
('S15','SAM 3 라이선스','https://github.com/facebookresearch/sam3/blob/main/LICENSE'),
('S16','원 SALAD 라이선스; 설치 포크의 조건은 별도 확인','https://github.com/serizba/salad/blob/main/LICENSE'),
('S17','OctoMap 공식 문서','https://octomap.github.io/'),
('S18','nvblox 공식 저장소','https://github.com/nvidia-isaac/nvblox'),
('S19','FOUND-IT 후속 연구','https://arxiv.org/abs/2605.25371'),
('S20','Nav2 비용 지도 설정','https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/costmap_2d/'),
('S21','Nav2 장애물 팽창 레이어','https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/costmap_2d/costmap_plugins/inflation/')]
add('공식 자료와 근거', '<p>확인일: 2026-11-04. 본문의 기존 동작은 아래 공식 소스에 근거하며, 그 외 모듈 구성·수치 목표·일정·인터페이스는 이번 데모를 위한 설계 제안이다. 공개 페이지의 내용은 구현 시점의 고정 커밋과 비교해 갱신한다.</p>'+ '<div class="sources">'+''.join(f'<p id="{sid}"><b>[{sid}] {title}</b><br><a href="{url}" target="_blank" rel="noopener">{url}</a></p>' for sid,title,url in sources)+'</div>')

style='''
:root{--ink:#162a3b;--muted:#627385;--green:#116955;--line:#dce5eb;--pale:#eef6f3}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f3f6f8;color:var(--ink);font:14px/1.95 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",Arial,sans-serif}a{color:var(--green);text-decoration:none}a:hover{text-decoration:underline}.cover{background:#0e1b28;color:#e7f0f6;padding:64px 8% 55px}.cover .eyebrow{color:#7ce0bf;font-size:12px;letter-spacing:3px}.cover h1{font-size:46px;line-height:1.25;font-weight:600;letter-spacing:-1.5px;max-width:850px;margin:18px 0}.cover h1 span{display:block;font-size:25px;color:#a7bdca;letter-spacing:-.6px;margin-top:14px}.cover p{color:#afc3ce;max-width:860px}.meta{display:flex;gap:25px;margin-top:28px;color:#86b1a4;font-size:12px}.shell{display:grid;grid-template-columns:245px minmax(0,1fr);max-width:1500px;margin:0 auto;align-items:start}.toc{position:sticky;top:0;padding:30px 20px 30px 26px;max-height:100vh;overflow:auto;font-size:11px;line-height:1.7}.toc a{display:block;padding:6px 0;color:#526879}.toc .label{font-size:10px;letter-spacing:2px;color:#8094a2;margin-bottom:10px}.content{background:white;min-width:0;padding:12px 48px 65px}.section{padding-top:36px;padding-bottom:14px;border-bottom:1px solid var(--line);scroll-margin-top:20px}.section h2{font-size:23px;line-height:1.5;letter-spacing:-.6px;margin:0 0 20px}.section h2 .num{display:inline-block;font:12px ui-monospace,monospace;color:#0d8c6a;margin-right:12px;vertical-align:middle}.lead{font-size:18px;line-height:1.9;font-weight:500}.callout{padding:17px 20px;background:var(--pale);border-left:3px solid #44ad8b;border-radius:0 5px 5px 0;margin:22px 0}.callout.amber{background:#fff7e9;border-color:#d3a04b}.callout p:last-child{margin-bottom:0}p{margin:12px 0 16px}b{font-weight:650}ul{padding-left:22px}li{margin-bottom:12px}.table-wrap{overflow-x:auto;margin:20px 0}table{width:100%;border-collapse:collapse;font-size:12px;line-height:1.85}th{background:#edf2f5;color:#425d70;padding:12px 11px;text-align:left;font-weight:650;border-bottom:2px solid #cbd9e0}td{padding:12px 11px;border-bottom:1px solid #e0e8ed;vertical-align:top}td:first-child{min-width:125px;font-weight:550}tr:nth-child(even) td{background:#fafcfd}code{background:#edf2f5;padding:2px 4px;border-radius:3px;font:11px/1.8 ui-monospace,Consolas,monospace;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#152735;color:#d7e5ed;padding:20px;border-radius:8px;font:12px/1.9 ui-monospace,Consolas,monospace}.architecture{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:22px 0}.architecture>div{border:1px solid #c9ddd5;background:#f3f9f6;padding:15px 12px;border-radius:7px}.architecture b{display:block;color:#116955;font-size:14px}.architecture span{display:block;font-size:10px;color:#536f68;line-height:1.8;margin-top:7px}.sources p{font-size:12px;overflow-wrap:anywhere}.back{display:inline-block;color:#80e5bf;margin-top:16px}.print{position:fixed;bottom:24px;right:24px;border:0;background:#176e57;color:white;padding:12px 18px;border-radius:8px;cursor:pointer;box-shadow:0 4px 20px #163d392d}footer{padding-top:30px;color:#78909c;font-size:11px}.section:last-child{border-bottom:0}@media(max-width:1000px){.shell{grid-template-columns:190px minmax(0,1fr)}.content{padding:12px 28px 50px}.architecture{grid-template-columns:1fr 1fr}}@media(max-width:700px){.cover{padding:35px 24px}.cover h1{font-size:31px}.cover h1 span{font-size:20px}.shell{display:block}.toc{position:static;max-height:260px;padding:24px}.content{padding:5px 20px 40px}.meta{flex-wrap:wrap;gap:10px}table{min-width:620px}.section h2{font-size:21px}.print{bottom:12px;right:12px}}@media print{@page{size:A4;margin:18mm 15mm}body{background:white;font-size:10pt;line-height:1.75}.cover{padding:25mm 5mm;background:white;color:#162a3b;break-after:page}.cover h1{font-size:32pt}.cover p,.cover h1 span,.cover .eyebrow,.meta{color:#486875}.toc,.print,.back{display:none}.shell{display:block}.content{padding:0}.section{padding:15pt 0;break-before:page}.section h2{font-size:18pt}table{font-size:8.3pt;min-width:0}thead{display:table-header-group}tr{break-inside:avoid}pre,.callout,.architecture{break-inside:avoid}.table-wrap{overflow:visible}.architecture{grid-template-columns:repeat(4,1fr)}a{color:#21614d}footer{font-size:8pt}}
'''
toc=''.join(f'<a href="#s{i}">{i:02d} · {html.escape(title)}</a>' for i,(title,_) in enumerate(sections,1))
body=''.join(f'<section class="section" id="s{i}"><h2><span class="num">{i:02d}</span>{title}</h2>{content}</section>' for i,(title,content) in enumerate(sections,1))
document=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TerraScene · VGGT-SLAM 데모 개발 계획서</title><style>{style}</style></head><body><header class="cover"><div class="eyebrow">TERRASCENE / ENGINEERING PLAN</div><h1>영상에서 공간 이해까지<span>VGGT-SLAM 기반 데모 프로그램 개발 계획서</span></h1><p>실시간 영상 재생 · 3차원 장면 · 객체 인식 · 2차원 지도 · 비용 지도 · 연결성 · 3차원 점유 공간</p><div class="meta"><span>2026-11-04</span><span>Design revision 1.0</span><span>Research prototype</span></div><a class="back" href="index.html">← 조작 가능한 화면으로</a></header><div class="shell"><aside class="toc"><div class="label">CONTENTS / {len(sections)} SECTIONS</div>{toc}</aside><main class="content">{body}<footer>TerraScene development plan · 기존 기능과 제안 기능을 구분하며, 실제 모델 벤치마크는 후속 구현에서 수행한다.</footer></main></div><button class="print" onclick="window.print()">인쇄 / 파일로 저장</button></body></html>'''
(ROOT/'dist'/'plan.html').write_text(document,encoding='utf-8')
print(f'Generated plan: {len(sections)} sections, {len(document):,} characters')
