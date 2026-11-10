"""Read-only Viser browser for cached demo runs."""
import json
import re
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import viser
from PIL import Image
from scipy.linalg import rq
from scipy.spatial.transform import Rotation

from vggt_slam.demo.chase_camera import chase_pose, travel_scale
from vggt_slam.demo.semantic_store import visible_detections
from vggt_slam.demo.query_display import result_observations, overlay_query_rgb
from vggt_slam.demo.road import RoadLayer, best_road_query, raster_connectivity
from vggt_slam.demo.cache_live4 import IncrementalRun as CachedRun
from vggt_slam.demo.bev import raster_bev
from vggt_slam.demo.camera_view import rgb_camera, raster_camera, overview_distance, display_resolution, overview_axes
from vggt_slam.demo.main_panel import free_port
from vggt_slam.demo.panel_live5 import Slam5Panel as MainPanel
from vggt_slam.demo.gpu_scene_live4 import LiveGPUScene as DenseGPUScene
from vggt_slam.demo.smooth_runtime import frame_times, CameraPath
from vggt_slam.demo.playback5 import playback_clock
from vggt_slam.demo.search_models import MODEL_OPTIONS, MODEL_HELP, COMMON_HELP, worker_environment
from vggt_slam.demo.object_colors import class_color, query_legend
from vggt_slam.demo.saved_queries import saved_summary, saved_labels
from vggt_slam.demo.search_lifecycle import recover_search_status
from vggt_slam.demo.search_policy import outcome_text, parse_queries, query_label


def _image(path):
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"))


def _frustum(camera):
    P = camera[:3, :]
    M = P[:, :3]
    if np.linalg.det(M) < 0:
        P, M = -P, -M
    K, R = rq(M)
    signs = np.where(np.diag(K) < 0, -1., 1.)
    K, R = K @ np.diag(signs), np.diag(signs) @ R
    center = -np.linalg.solve(M, P[:, 3])
    quat = Rotation.from_matrix(R.T).as_quat()
    return center, quat[[3, 0, 1, 2]]


def _obb_segments(center, extent, rotation):
    center = np.asarray(center, dtype=float)
    half = np.asarray(extent, dtype=float) / 2
    rotation = np.asarray(rotation, dtype=float)
    local = np.array([[-half[0], -half[1], -half[2]], [half[0], -half[1], -half[2]],
                      [half[0], half[1], -half[2]], [-half[0], half[1], -half[2]],
                      [-half[0], -half[1], half[2]], [half[0], -half[1], half[2]],
                      [half[0], half[1], half[2]], [-half[0], half[1], half[2]]])
    corners = (rotation @ local.T).T + center
    indices = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6),
               (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7))
    return np.asarray([[corners[a], corners[b]] for a, b in indices], dtype=np.float32)


def serve(run_dir, port=8108, source_fps=10., live_control=None, studio_label="SLAM V5"):
    run_dir = Path(run_dir).resolve()
    runs = {p.name: p for p in run_dir.parent.iterdir() if (p / "manifest.json").is_file() and json.loads((p / "manifest.json").read_text()).get("config",{}).get("slam_fast_start")}
    if run_dir.name not in runs:
        raise ValueError(f"run manifest not found: {run_dir}")
    live_control = Path(live_control) if live_control else None
    live_state = {"revision": None, "allow_search": live_control is None}
    panel = MainPanel(port)
    panel.studio_label=studio_label
    # macOS processes can exit between psutil iteration and cwd() in Viser's
    # development-server probe. Keep the installed dependency and V1-3 intact.
    import psutil
    import viser._client_autobuild as autobuild
    original_probe=autobuild._check_viser_yarn_running
    def stable_probe():
        try:return original_probe()
        except psutil.NoSuchProcess:return False
    autobuild._check_viser_yarn_running=stable_probe
    server = viser.ViserServer(host="127.0.0.1", port=free_port())
    panel.viser_port = server.get_port()
    server.gui.configure_theme(control_layout="fixed", control_width="large", dark_mode=True,
                               brand_color=(34, 211, 238), show_logo=False, show_share_button=False)
    server.gui.add_markdown(f"### VGGT · Map Studio · {studio_label}")
    run_select = server.gui.add_dropdown("Run", options=sorted(runs), initial_value=run_dir.name)
    state_text = server.gui.add_markdown("")
    frame = server.gui.add_slider("Map keyframe", min=0, max=1, step=1, initial_value=0)
    play = server.gui.add_button("Play / Pause", color="cyan", icon=viser.Icon.PLAYER_PLAY)
    pause = server.gui.add_button("Pause playback", icon=viser.Icon.PLAYER_PAUSE)
    playback_status = server.gui.add_markdown("**Playback: Paused · 정지**")
    blank = np.full((80, 140, 3), (15, 23, 42), dtype=np.uint8)
    follow_live=server.gui.add_checkbox("Follow new map frames",initial_value=True)
    follow_rgb = server.gui.add_checkbox("RGB 시점 추적", initial_value=True)
    chase_button=server.gui.add_button("Chase View · 뒤에서 추적", color="cyan",icon=viser.Icon.CAMERA)
    chase_distance=server.gui.add_slider("Chase 거리 배율",min=.5,max=8.,step=.25,initial_value=2.5)
    reset = server.gui.add_button("Reset RGB camera", color="cyan", icon=viser.Icon.CAMERA, visible=False)
    camera_status = server.gui.add_markdown("현재 RGB 카메라 시점을 기본으로 표시합니다.")
    tabs = server.gui.add_tab_group()
    with tabs.add_tab("지도 · Map", icon=viser.Icon.MAP):
        fit = server.gui.add_button("Fit map", color="cyan", icon=viser.Icon.FOCUS_2)
        colors = server.gui.add_dropdown("Colors", options=["RGB", "Submaps"], initial_value="RGB")
        budget = server.gui.add_slider("Displayed point limit", min=50_000, max=2_000_000, step=50_000, initial_value=200_000)
        playback_quality=server.gui.add_dropdown("재생 3D 품질",options=["자동", "높음", "균형", "가벼움"],initial_value="자동")
        point_size = server.gui.add_slider("Point size (점 크기 배율)", min=0.1, max=10.0, step=0.1, initial_value=1.0)
        mask_3d = server.gui.add_checkbox("3D segmentation mask", initial_value=True)
        box_3d = server.gui.add_checkbox("3D bounding boxes", initial_value=True)
        box_rgb = server.gui.add_checkbox("RGB bounding boxes", initial_value=True)
        mask_bev = server.gui.add_checkbox("BEV segmentation mask", initial_value=False)
        box_bev = server.gui.add_checkbox("BEV bounding boxes", initial_value=False)
        mask_rgb = server.gui.add_checkbox("RGB segmentation mask", initial_value=True)
        show_road = server.gui.add_checkbox("Show road · 3D 도로", initial_value=False, visible=False)
        road_info = server.gui.add_markdown("", visible=False)
        hide_sky = server.gui.add_checkbox("Hide sky", initial_value=False, visible=False)
        with server.gui.add_folder("하늘 제거 · Sky filter", expand_by_default=False, visible=False):
            sky_threshold = server.gui.add_slider("Sky threshold", min=8, max=192, step=8, initial_value=32)
            sky_info = server.gui.add_markdown("")
            sky_image = server.gui.add_image(blank, label="Sky mask overlay")
        with server.gui.add_folder("실시간 2D 맵 · BEV"):
            bev_overlay = server.gui.add_checkbox("Overlay Road connectivity", initial_value=False, visible=False)
            bev_trajectory = server.gui.add_checkbox("주행 기록 · BEV trajectory", initial_value=True)
            bev_zoom = server.gui.add_slider("BEV zoom", min=.5, max=8., step=.25, initial_value=1.)
            bev_plane = server.gui.add_dropdown("BEV plane", options=["XZ", "XY", "YZ"], initial_value="XZ")
            bev_image = server.gui.add_image(blank, label="BEV map", format="png", visible=False)
            bev_info = server.gui.add_markdown("")
        rgb_gui = server.gui.add_image(blank, label="RGB", visible=False)
        info = server.gui.add_markdown("")
    with tabs.add_tab("검색 · Search", icon=viser.Icon.SEARCH):
        server.gui.add_markdown("### 무엇을 찾으시나요?\n현재 run의 RGB에서 대상을 찾고 3D 위치를 표시합니다.")
        search_model = server.gui.add_dropdown("Search model", options=list(MODEL_OPTIONS), initial_value="SAM3")
        model_help = server.gui.add_markdown(MODEL_HELP['sam3'] + COMMON_HELP)
        @search_model.on_update
        def show_model_help(_):
            backend=MODEL_OPTIONS[search_model.value]
            fixed=backend in ('rfdetr','yolo26','yolo11')
            all_classes.visible=fixed
            query_text.disabled=fixed and all_classes.value
            query_text.visible=not query_text.disabled
            search_modes_now=[name for name in search_modes if not (fixed and all_classes.value and search_modes[name]=='candidate')]
            search_mode.options=search_modes_now
            if search_mode.value not in search_modes_now:search_mode.value='현재 RGB'
            model_help.content = MODEL_HELP[backend] + ('\n\n**전체 클래스 검출 ON** · Query 없이 학습된 모든 종류 중 검출한 객체를 표시합니다.' if fixed and all_classes.value else '') + COMMON_HELP
        all_classes=server.gui.add_checkbox("전체 클래스 검출",initial_value=True,visible=False)
        all_classes.on_update(show_model_help)
        query_text = server.gui.add_text("Query", initial_value="car", hint="예: car, tree, truck, printer")
        search_modes = {"전구간 전수": "all", "전구간 표본": "sampled", "현재 RGB": "current", "PE 후보 찾기": "candidate"}
        search_mode = server.gui.add_dropdown("Search scope", options=list(search_modes), initial_value="현재 RGB")
        search_limit = server.gui.add_slider("표본 프레임 수", min=4, max=96, step=4, initial_value=24)
        server.gui.add_markdown("전수는 모든 고유 프레임을 검사합니다. CPU에서 수 분 이상 걸릴 수 있습니다. 결과 수는 프레임별 관측 수이며 고유 객체 수가 아닙니다.")
        search_button = server.gui.add_button("Search", color="cyan", icon=viser.Icon.SEARCH)
        search_status = server.gui.add_markdown("**검색 대기** · 텍스트를 입력하고 Search를 누르세요.")
        with server.gui.add_folder("저장된 검색 결과 · Saved Objects",expand_by_default=True):
            saved_model_filter=server.gui.add_dropdown("저장 결과 모델",options=["전체","RF-DETR","YOLO26","YOLO11","SAM3","YOLOE"],initial_value="전체")
            saved_text_filter=server.gui.add_text("저장 결과 찾기",initial_value="",hint="예: person, car")
            saved_info=server.gui.add_markdown(saved_summary(None))
            object_select = server.gui.add_dropdown("Saved object query", options=["None"], initial_value="None")
            delete_query = server.gui.add_button("Delete selected query", icon=viser.Icon.TRASH, disabled=True)
            observation_select = server.gui.add_dropdown("Result frame", options=["전체 관측"], initial_value="전체 관측", disabled=True)
            clear_objects = server.gui.add_button("Clear object boxes", icon=viser.Icon.X)
            object_info = server.gui.add_markdown("")
    with tabs.add_tab("분석 · Inspect", icon=viser.Icon.CHART_DOTS):
        server.gui.add_markdown("### 복원 상태\n상대 좌표계입니다. 거리·지면 정확도는 검증되지 않았습니다.")
        step = server.gui.add_dropdown("Optimization step", options=["Unavailable"], initial_value="Unavailable")
        phase = server.gui.add_dropdown("Optimization view", options=["after", "before"], initial_value="after")
        depth_gui = server.gui.add_image(blank, label="Relative depth")
        confidence_gui = server.gui.add_image(blank, label="Confidence")
        loop_select = server.gui.add_dropdown("Loop candidate", options=["Unavailable"], initial_value="Unavailable")
        loop_info = server.gui.add_markdown("")
        loop_query = server.gui.add_image(blank, label="Loop query")
        loop_candidate = server.gui.add_image(blank, label="Loop candidate")
    state = {"view_mode":"rgb", "chase_scale":.04, "run": None, "cloud": None, "lines": None, "edges": None, "frustum": None,
             "bev_pan": [0.,0.], "semantic_layer": None, "semantic_query_id": None, "road_cloud": None, "road_layer": None, "road_query_id": None, "object_boxes": [], "searching": False, "query_labels": {}, "camera": None, "camera_shape": None, "observation_labels": {}, "legacy_query_target": 0,
             "center": np.zeros(3), "radius": 1.0, "loading": False, "playing": False,
             "pending_frame": None, "rendering": False, "render_signature": None}
    clock_box = {"clock": None, "times": None, "path": None, "path_key": None, "timing": "", "run_key": None, "generation": 0}
    gpu_scene=DenseGPUScene()
    panel.gpu_scene=gpu_scene
    stopped = threading.Event()
    render_lock = threading.RLock()

    def viser_point_size():
        scale=state['radius']/2000
        if state['view_mode']=='chase':scale=min(scale,state['chase_scale']/80)
        return scale*point_size.value

    @point_size.on_update
    def resize_points(_):
        with render_lock:
            if state["cloud"] is not None:
                state["cloud"].point_size = viser_point_size()

    def fit_all():
        for client in server.get_clients().values():
            fov = np.radians(60)
            distance = overview_distance(state['radius'], fov, client.camera.aspect)
            up, direction = overview_axes(state['camera'])
            client.camera.up_direction = up
            client.camera.fov = fov
            client.camera.position = state["center"] + distance * direction / np.linalg.norm(direction)
            client.camera.look_at = state["center"]

    def apply_rgb_camera(client=None):
        camera = state['camera']
        if camera is None:
            camera_status.content = '현재 프레임의 카메라가 선택한 snapshot에 없습니다.'
            return
        clients = [client] if client is not None else list(server.get_clients().values())
        for target in clients:
            with target.atomic():
                target.camera.position = camera['position']
                target.camera.up_direction = camera['up']
                target.camera.look_at = camera['position'] + camera['forward'] * max(state['radius']/20, .1)
                target.camera.wxyz = camera['wxyz']
                target.camera.fov = camera['fov']
                target.camera.near = .001
                target.camera.far = max(1000., state['radius']*50)
        camera_status.content = '**RGB 카메라 시점** · 메인 RGB와 동기화됨'

    def apply_chase_camera(camera=None,client=None):
        if camera is None and state['playing'] and clock_box['path'] is not None:
            camera=clock_box['path'].at(clock_box['clock'].position())
        camera=camera if camera is not None else state['camera']
        if camera is None:return
        pose=chase_pose(camera,state['chase_scale']*chase_distance.value)
        state['view_camera_position']=pose['position'].tolist()
        state['view_camera_source']=np.asarray(camera['position']).tolist()
        clients=[client] if client is not None else list(server.get_clients().values())
        for target in clients:
            with target.atomic():
                target.camera.position=pose['position'];target.camera.up_direction=pose['up']
                target.camera.look_at=pose['look_at'];target.camera.wxyz=pose['wxyz'];target.camera.fov=pose['fov']
                target.camera.near=max(state['chase_scale']*chase_distance.value*.2,1e-5)
                target.camera.far=max(1000.,state['radius']*50)
        message='**Chase View · 뒤에서 추적** · 현재 RGB 카메라의 뒤·위에서 따라갑니다.'
        if camera_status.content!=message:camera_status.content=message

    def _update():
        if state["loading"] or state["run"] is None:
            return
        render_started = time.monotonic()
        run = state["run"]
        frame_index = int(frame.value)
        # Searches can finish without reloading the run: keep the summary current.
        start, end = run.manifest.get('started_at'), run.manifest.get('finished_at')
        elapsed = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() if start and end else None
        state_text.content = (f"**저장된 지도 · {run.manifest.get('status', 'unknown')}**  \n"
                              f"{len(run.frames):,} 프레임 · {len(run.steps):,} 서브맵 갱신 · {len(run.object_queries)} 검색  \n"
                              f"{studio_label} · 원본 영상 / 지도 독립 갱신")
        chosen_step = None if step.value == "Unavailable" else int(step.value)
        result = run.render(step=chosen_step, phase=phase.value,
                            frame_index=frame_index if run.frames else None,
                            budget=min(120000,int(budget.value)) if state["playing"] and not state.get("gpu_fallback") else int(budget.value), color_mode=colors.value,
                            hide_sky=hide_sky.value, sky_threshold=int(sky_threshold.value))
        pts, trajectory = result["points"], result["trajectory"]
        road_query = best_road_query(run.object_queries)
        road_id = road_query['query_id'] if road_query else None
        if road_id != state['road_query_id']:
            state['road_layer'] = RoadLayer(run, road_query) if road_query else None
            state['road_query_id'] = road_id
        layer = state['road_layer']
        show_road.disabled = layer is None
        bev_overlay.disabled = layer is None
        road_points = layer.world(run, chosen_step, phase.value, frame_index) if layer and chosen_step is not None else np.empty((0, 3), np.float32)
        current_road_count = sum(len(p) for i, _, p in layer.groups if i == frame_index) if layer else 0
        road_info.content = (f"**Road** · 검사 {layer.coverage}/{layer.total_frames}장 · 누적 도로 {len(road_points):,}점 · 현재 프레임 {current_road_count:,}점  \n초록: road 마스크와 유효 깊이가 대응한 3D 표면. 주행 가능성을 검증한 지도는 아닙니다." if layer else '저장된 road 분할 결과가 없습니다. 전체 구간에서 road를 검색하세요.')
        bev_selected = selected_query()
        bev_boxes = []
        bev_masks = road_points if mask_bev.value else None
        bev_mask_colors=None
        semantic_points=np.empty((0,3),np.float32);semantic_colors=np.empty((0,3),np.uint8)
        if bev_selected:
            bev_observation = state['observation_labels'].get(observation_select.value)
            bev_detections = bev_selected.get('detections',[])
            if bev_observation:
                bev_file = run.path / Path(bev_selected['_asset_path']).parent / bev_observation['result']
                bev_detections = json.loads(bev_file.read_text()).get('detections',[])
            bev_detections=visible_detections(bev_detections,frame_index)
            bev_snapshot = bev_selected.get('snapshot')
            compatible_bev = bev_snapshot is None or (bev_snapshot['step']==chosen_step and bev_snapshot['phase']==phase.value)
            bev_masks = None
            if compatible_bev and box_bev.value:
                bev_boxes = [_obb_segments(d['center'],d['extent'],d['rotation']) for d in bev_detections
                    if d.get('valid') and d.get('playback_index',bev_observation['playback_index'] if bev_observation else state['legacy_query_target']) <= frame_index]
            if compatible_bev and chosen_step is not None and (mask_bev.value or mask_3d.value) and bev_selected.get('search',{}).get('observations'):
                if state['semantic_query_id'] != bev_selected['query_id']:
                    state['semantic_layer'] = RoadLayer(run, bev_selected, prompt=None)
                    state['semantic_query_id'] = bev_selected['query_id']
                semantic_points,semantic_colors = state['semantic_layer'].world_colored(run,chosen_step,phase.value,frame_index,
                    only_frame=bev_observation['playback_index'] if bev_observation else None)
                if mask_bev.value:bev_masks,bev_mask_colors=semantic_points,semantic_colors
        bev_image.image, bev_stats = raster_bev(pts, result['colors'], trajectory, plane=bev_plane.value,
            zoom=bev_zoom.value, pan=state['bev_pan'], show_trajectory=bev_trajectory.value,
            road_points=road_points if bev_overlay.value and layer else None,
            mask_points=bev_masks, boxes=bev_boxes,mask_colors=bev_mask_colors)
        bev_info.content = (f"**BEV · {bev_plane.value} · {bev_zoom.value:g}×** · {bev_stats['occupied_cells']:,} 관측 셀  \n휠: 줌 · 드래그: 이동 · 초록: 도로 연결 · 분할 색상: 객체 Legend 참조")
        for key in ("lines", "edges", "frustum"):
            if state[key] is not None:
                state[key].remove()
                state[key] = None
        for key in ("cloud", "road_cloud", "object_mask_cloud"):
            if state["playing"] and key=="road_cloud":continue
            if state.get(key) is not None:
                state[key].remove()
                state[key] = None
        for handle in state["object_boxes"]:
            handle.remove()
        state["object_boxes"] = []
        if len(pts):
            sample = pts[np.linspace(0, len(pts) - 1, min(len(pts), 50000), dtype=np.int64)]
            low, high = np.quantile(sample, [0.02, 0.98], axis=0)
            state["center"] = (low + high) / 2
            state["radius"] = max(float(np.linalg.norm(high - low)), 0.1)
            if not state["playing"] and not follow_rgb.value:
                state["cloud"] = server.scene.add_point_cloud("/map", points=pts, colors=result["colors"],
                                                          point_size=viser_point_size(), point_shape="circle")

        if mask_3d.value and len(semantic_points) and not follow_rgb.value:
            ids=np.linspace(0,len(semantic_points)-1,min(150000,len(semantic_points)),dtype=int)
            state['object_mask_cloud']=server.scene.add_point_cloud('/object_masks',points=semantic_points[ids],colors=semantic_colors[ids],point_size=state['radius']/1500*point_size.value,point_shape='circle')
        road_display = road_points[np.linspace(0, len(road_points)-1, min(len(road_points), 150000), dtype=int)] if len(road_points) else road_points
        if mask_3d.value and show_road.value and len(road_display) and not follow_rgb.value:
            if state['road_cloud'] is None:
                state['road_cloud'] = server.scene.add_point_cloud('/road_surface', points=road_display,colors=(34,197,94),point_size=state['radius']/1800*point_size.value,point_shape='circle')
            else:
                state['road_cloud'].points=road_display
                state['road_cloud'].visible=True
        elif state['road_cloud'] is not None:
            state['road_cloud'].visible=False
        if len(trajectory) > 1:
            state["lines"] = server.scene.add_line_segments("/trajectory", points=np.stack([trajectory[:-1], trajectory[1:]], axis=1),
                                                           colors=(255, 120, 40), line_width=2)
        if len(result["edges"]):
            state["edges"] = server.scene.add_line_segments("/graph_edges", points=result["edges"],
                                                            colors=result["edge_colors"][:, None, :], line_width=3)
        current = run.frame(frame_index)
        state["camera"] = None
        camera_projection = None
        camera_shape = (294, 518)
        sky_image.image = blank
        sky_info.content = "이 run에는 하늘 분할 캐시가 없습니다. 원본 점군을 표시합니다."
        if run.sky_index is not None:
            sky_info.content = (f"**{'하늘 제거 켜짐' if hide_sky.value else '원본 비교'}** · "
                                "하늘 분할 + 경계 2px · 낮은 threshold = 강한 제거")
            name = run.sky_index['frames'].get(current['asset_paths']['metadata']) if current else None
            if name:
                image = _image(run.path / current['asset_paths']['rgb'])
                probability = np.asarray(Image.open(run.sky_dir / name))
                from scipy.ndimage import maximum_filter
                mask = maximum_filter(probability, size=5) >= sky_threshold.value
                overlay = image.copy()
                overlay[mask] = (image[mask] * .4 + np.array([34, 211, 238]) * .6).astype(np.uint8)
                sky_image.image = overlay
        rgb_gui.image = blank
        depth_gui.image = blank
        confidence_gui.image = blank
        if current:
            paths = current["asset_paths"]
            for widget, key in ((rgb_gui, "rgb"), (depth_gui, "depth_preview"),
                                (confidence_gui, "confidence_preview")):
                if key in paths and (run.path / paths[key]).is_file():
                    widget.image = _image(run.path / paths[key])
            meta = json.loads((run.path / paths["metadata"]).read_text())
            node = int(current["submap_id"]) + int(meta["submap_frame_index"])
            if node in result["cameras"]:
                try:
                    camera_shape = tuple(meta["resolution_hw"])
                    camera_projection = result["cameras"][node]
                    state["camera"] = rgb_camera(camera_projection, camera_shape)
                    pos, quat = _frustum(camera_projection)
                    state["frustum"] = server.scene.add_camera_frustum("/selected_camera", fov=np.radians(60), aspect=1.5,
                                                                        scale=state["radius"] / 35, position=pos, wxyz=quat, color=(255, 195, 48))
                except (ValueError, np.linalg.LinAlgError):
                    pass
            frame_text = f"frame ID {current['source_frame_id']} · submap {current['submap_id']} · timestamp {meta.get('source_timestamp')} ({meta.get('source_timestamp_type', 'unknown')})"
            if result["step"] is not None and node not in result["cameras"]:
                frame_text += " · frame is not present in the selected snapshot"
        else:
            frame_text = "RGB / depth / timeline unavailable in this cached result."
        total = f"{len(run.cloud):,}" if run.cloud is not None else "unknown"
        info.content = (f"**{result['source']}** · BEV sample {len(pts):,} points · full PCD {total} points  \n"
                        f"{frame_text} · playback index {frame_index + 1 if current else 0}/{len(run.frames)}  \n"
                        "Coordinates: reconstruction units (metric scale unverified). "
                        "Camera frustum is a decomposition of the projective camera; orientation is illustrative.")
        loops = [event for event in run.events if event["event_type"] == "loop_validation"]
        loop_info.content = (f"Recorded loop validations: **{len(loops)}**, accepted: **{sum(bool(x['payload']['accepted']) for x in loops)}**.  \n"
                             "Loop evidence covers the full run and is not filtered by the selected timeline or snapshot.")
        if run.evaluations:
            summaries = []
            for metrics in run.evaluations:
                value = metrics.get("ate_rmse_m")
                name = metrics.get("reference_camera_folder", metrics.get("reference", "trajectory"))
                summaries.append(f"{name}: **{value:.3f} m RMSE** ({metrics.get('matched_frames', '?')} matched)"
                                 if isinstance(value, (int, float)) else f"{name}: ATE unavailable")
            loop_info.content += "  \nEvaluation after recorded alignment: " + "; ".join(summaries)
        loop_query.image = blank
        loop_candidate.image = blank
        candidates = [event for event in run.events if event["event_type"] == "loop_candidate"
                      and event["payload"].get("match_id") == loop_select.value]
        if candidates:
            candidate = candidates[0]
            for widget, key in ((loop_query, "query"), (loop_candidate, "candidate")):
                path = candidate.get("asset_paths", {}).get(key)
                if path and (run.path / path).is_file():
                    widget.image = _image(run.path / path)
            decision = next((event["payload"] for event in loops
                             if event["payload"].get("match_id") == loop_select.value), None)
            info_text = f"L2 distance: {candidate['payload']['retrieval_distance']:.4f}"
            if decision:
                info_text += f" · match ratio: {decision['image_match_ratio']} · accepted: {decision['accepted']}"
            loop_info.content += f"  \n{info_text}"
        projected_boxes = []
        selected_object = next((item for item in run.object_queries
                                if item.get('query_id') == state['query_labels'].get(object_select.value, object_select.value)), None)
        if selected_object is None:
            object_info.content = ('No saved object query selected. · 저장된 검색을 선택하세요.' if run.object_queries else
                                   '아직 이 run에서 실행한 검색이 없습니다. Search로 검색을 시작하세요.')
        else:
            base = run.path / Path(selected_object['_asset_path']).parent
            search = selected_object.get('search', {})
            observation = state['observation_labels'].get(observation_select.value)
            detail = json.loads((base / observation['result']).read_text()) if observation else selected_object
            detail_base = (base / observation['result']).parent if observation else base
            image_path = detail_base / detail['frame_image']
            detections = detail.get('detections', [])
            representative = None
            if observation:
                overlay_detections = detections
            elif search.get('observations'):
                representative = next((o for o in search['observations'] if (base/o['result']).parent == image_path.parent), None)
                overlay_detections = [d for d in detections if representative and d.get('source_frame_id')==representative['source_frame_id'] and d.get('query')==representative['query']]
            else:
                overlay_detections = detections
            if current and (mask_rgb.value or box_rgb.value):
                rgb_gui.image = overlay_query_rgb(rgb_gui.image, run.path, selected_object,
                                                  frame_index, state['legacy_query_target'], show_masks=mask_rgb.value, show_boxes=box_rgb.value, source_frame_id=current['source_frame_id'],class_colors=True)
            snapshot = selected_object.get('snapshot')
            compatible = snapshot is None or (snapshot['step']==chosen_step and snapshot['phase']==phase.value)
            for detection in detections if compatible and box_3d.value else []:
                playback = detection.get('playback_index', observation['playback_index'] if observation else state['legacy_query_target'])
                if not detection.get('valid') or playback > frame_index: continue
                if detection.get('dynamic_state')=='possible' and playback!=frame_index:continue
                segments = _obb_segments(detection['center'], detection['extent'], detection['rotation'])
                projected_boxes.append(segments)
                state['object_boxes'].append(server.scene.add_line_segments(
                    f"/cached_object_{playback}_{detection['index']}", points=segments, colors=class_color(detection.get('class_name') or detection.get('query') or selected_object['query']), line_width=3))
            saved_valid = sum(bool(d.get('valid')) for d in selected_object.get('detections', []))
            native_count = sum(bool(d.get('native_mask_pixels',d.get('mask_pixels',0))) for d in selected_object.get('detections', []))
            if search.get('schema_version',0)>=3:
                object_info.content = (f"**Query {selected_object['query']}** · {search['mode']} · "
                    f"검사 {search['inspected_frames']}/{search['total_frames']} 고유 프레임  \n"
                    f"2D 관측 {native_count}건 · 유효 3D 관측 {saved_valid}건 · 고유 객체 수 아님  \n"
                    f"valid 3D boxes {len(state['object_boxes'])} · 현재 타임라인까지의 표시 수")
                if observation:
                    object_info.content += f"  \n선택 frame {observation['source_frame_id']} · {observation['query']} · 2D {observation['mask_count']} / 3D {observation['valid_boxes']}"
                else:
                    object_info.content += '  \nRGB는 현재 프레임에서 검출된 결과만 표시합니다. RGB Mask/Box가 켜져 있으면 재생 중에도 지도 키프레임 기준으로 표시합니다. Result frame에서 개별 결과를 확인하세요.'
            else:
                object_info.content = (f"Query **{selected_object['query']}** · frame {selected_object['frame_index']} · "
                                       f"submap {selected_object['submap_id']} · valid 3D boxes {len(state['object_boxes'])}  \n" +
                                       outcome_text(native_count,saved_valid,len(search.get('attempts',[])) or 1))
                object_info.content += '  \n이전 후보 검색 결과입니다. 전구간 검색 결과와 구분하세요.'
            if not compatible:
                object_info.content += '  \n박스 숨김: 기록된 optimization step/after를 선택하세요.'

        gpu_info=gpu_scene.snapshot()
        if chosen_step is not None:
            playback_budget=min(int(budget.value),{'자동':int(budget.value),'높음':int(budget.value),'균형':300000,'가벼움':120000}[playback_quality.value])
            gpu_lines=list(projected_boxes)
            if len(trajectory)>1:gpu_lines.append(np.stack([trajectory[:-1],trajectory[1:]],axis=1))
            lines=np.concatenate(gpu_lines) if gpu_lines else None
            gpu_info=gpu_scene.update(run,chosen_step,phase.value,result['nodes'],frame_index,playback_budget,
                hide_sky.value,int(sky_threshold.value),colors.value,point_scale=point_size.value,
                road_points=np.concatenate(([road_display] if mask_3d.value and show_road.value else [])+([semantic_points] if mask_3d.value else [])+[np.empty((0,3))]),
                road_colors=np.concatenate(([np.tile([34,197,94],(len(road_display),1))] if mask_3d.value and show_road.value else [])+([semantic_colors] if mask_3d.value else [])+[np.empty((0,3))]),lines=lines)
            gpu_scene.sync_viser(server.scene,state['playing'] and not follow_rgb.value,viser_point_size())
        if camera_projection is not None and follow_rgb.value and (not state["playing"] or state.get("gpu_fallback")):
            path_key=(clock_box['run_key'],step.value,phase.value)
            if follow_rgb.value and clock_box['clock'] is not None:
                if path_key!=clock_box['path_key']:
                    clock_box['path']=CameraPath(run,chosen_step,phase.value,clock_box['times']);clock_box['path_key']=path_key
                pose=clock_box['path'].at(clock_box['clock'].position())
                if pose is not None and 'projection' in pose:
                    camera_projection=pose['projection'];camera_shape=tuple(pose['shape']);state['camera']=pose
            foreground, foreground_colors = run.camera_preview(frame_index, chosen_step, phase.value,
                    hide_sky.value, int(sky_threshold.value), budget=min(50000, int(budget.value)))
            remaining = max(0, int(budget.value) - len(foreground))
            idx = np.linspace(0, len(pts)-1, min(len(pts), remaining), dtype=int)
            camera_points = np.concatenate([pts[idx], foreground])
            camera_colors = np.concatenate([result['colors'][idx], foreground_colors])
            if mask_3d.value and show_road.value and len(road_display):
                camera_points = np.concatenate([road_display, camera_points])
                camera_colors = np.concatenate([np.tile(np.array([34,197,94], np.uint8), (len(road_display), 1)), camera_colors])
            if mask_3d.value and len(semantic_points):
                camera_points=np.concatenate([semantic_points,camera_points]);camera_colors=np.concatenate([semantic_colors,camera_colors])
            camera_image, raster_stats = raster_camera(camera_points, camera_colors, camera_projection, camera_shape,
                                                       point_scale=point_size.value, boxes=projected_boxes,
                                                       output_shape=display_resolution(camera_shape, (960,540,1.)), antialias=1.0)
            if follow_rgb.value:
                apply_rgb_camera()
        else:
            camera_image, raster_stats = blank, {}
            if camera_projection is None:camera_status.content = '현재 프레임 카메라가 없습니다.'
        if state['view_mode']=='chase':apply_chase_camera()
        info.content += f"  \n3D 표시 대상 {gpu_info.get('map_points',0):,}점 · 자동 모드의 실제 표시 점 수는 상단에 표시됩니다."
        panel.publish(rgb_gui.image, bev_image.image, camera_image, {
            'selected_query_id':selected_object['query_id'] if selected_object else None,'object_legend':query_legend(selected_object),'object_mask_points':len(semantic_points) if mask_3d.value else 0,'object_box_count':len(state['object_boxes']),
            'viewer_version': 'slam-v5', 'quality_mode': 'balanced' if state['playing'] else 'high', 'selected_query': selected_object is not None, 'render_seconds': time.monotonic()-render_started, 'chunk_uploads': gpu_scene.uploads, 'scene_point_count':gpu_info.get('map_points',0), 'playback_quality':playback_quality.value,
            'frame_index': frame_index, 'frame_count': len(run.frames),
            'source_frame_id': current['source_frame_id'] if current else 'N/A',
            'timestamp_label': f"{meta['source_timestamp']:.2f} s" if current and isinstance(meta.get('source_timestamp'), (int, float)) else 'N/A',
            'playing': state['playing'], 'follow_rgb': follow_rgb.value, 'view_mode':state['view_mode'], 'chase_distance':state['chase_scale']*chase_distance.value,
            'camera_available': camera_projection is not None, 'aspect': camera_shape[1]/camera_shape[0],
            'road_points': len(road_points), 'road_visible': bool(mask_3d.value and show_road.value and len(road_points)), 'bev_mode': 'Road connectivity' if bev_overlay.value and layer else '표면 지도', 'connectivity': bev_stats['connectivity'],
            'bev_pan': state['bev_pan'], 'mask_bev': mask_bev.value, 'box_bev': box_bev.value, 'box_rgb': box_rgb.value, 'bev_box_count': len(bev_boxes),
            'bev_zoom': bev_zoom.value, 'bev_trajectory': bev_trajectory.value, 'mask_3d': mask_3d.value, 'box_3d':box_3d.value, 'mask_rgb': mask_rgb.value,
            'point_count': len(pts), 'bev_plane': bev_plane.value, 'raster': raster_stats,
            'camera_position': state['camera']['position'].tolist() if state['camera'] is not None else None,
        })

    def update(_=None):
        with render_lock:
            if clock_box['clock'] is not None and clock_box.get('last_index') != int(frame.value):
                if not state['playing']:
                    clock_box['generation']+=1
                    clock_box['clock'].seek(clock_box['times'][int(frame.value)],False)
                clock_box['last_index']=int(frame.value)
            signature = (str(state["run"].path) if state["run"] is not None else None,
                         frame.value, step.value, phase.value, colors.value, budget.value,
                         tuple(state['bev_pan']), box_rgb.value, mask_bev.value, box_bev.value, playback_quality.value, panel.viewport, loop_select.value, object_select.value, observation_select.value, hide_sky.value, sky_threshold.value, bev_plane.value, bev_overlay.value, bev_trajectory.value, bev_zoom.value, mask_3d.value, box_3d.value, mask_rgb.value, show_road.value, follow_rgb.value, state["view_mode"], chase_distance.value, point_size.value)
            if not state["loading"] and signature == state["render_signature"]:
                state["pending_frame"] = None
                return
            state["rendering"] = True
            try:
                _update()
                if not state["loading"]:
                    state["render_signature"] = signature
            finally:
                state["rendering"] = False
                state["pending_frame"] = None

    def load_run(_=None):
        state["loading"] = True
        try:
            run = CachedRun(runs[run_select.value])
            state["run"] = run
            if run.steps:
                initial_path=CameraPath(run,run.steps[-1],'after',frame_times(run,source_fps)[0])
                state['chase_scale']=travel_scale([sample['position'] for sample in initial_path.samples])
            times,timing=frame_times(run,source_fps)
            clock_box.update(last_index=None,clock=playback_clock(run,times),times=times,timing=timing,path=None,path_key=None,run_key=str(run.path))
            panel.media=None
            for index_path in sorted((run.path/'evidence').glob('smooth_media_*/index.json'),reverse=True):
                index=json.loads(index_path.read_text())
                if index.get('status')=='completed' and index.get('source_run')==str(run.path.resolve()) and index.get('source_fps')==source_fps:
                    panel.media=index_path.parent/index['video'];break
            state["semantic_layer"] = None
            state["semantic_query_id"] = None
            state["bev_pan"] = [0.,0.]
            state["road_layer"] = None
            state["road_query_id"] = None
            frame.max = max(1, len(run.frames) - 1)
            frame.disabled = not run.frames
            frame.value = 0
            options = [str(value) for value in run.steps] or ["Unavailable"]
            step.options = options
            step.value = options[-1]
            step.disabled = not run.steps
            phase.disabled = not run.steps
            loop_options = [event["payload"]["match_id"] for event in run.events
                            if event["event_type"] == "loop_candidate" and "match_id" in event["payload"]]
            loop_options = loop_options or ["Unavailable"]
            loop_select.options = loop_options
            loop_select.value = loop_options[0]
            loop_select.disabled = loop_options == ["Unavailable"]
            state["query_labels"] = saved_labels(run,saved_model_filter.value,saved_text_filter.value)
            state['observation_labels'] = {}
            observation_select.options = ['전체 관측']
            observation_select.value = '전체 관측'
            observation_select.disabled = True
            object_options = ["None"] + list(state["query_labels"])
            object_select.options = object_options
            object_select.value = "None"
            delete_query.disabled = True
            object_select.disabled = object_options == ["None"]
            hide_sky.disabled = run.sky_index is None
            sky_threshold.disabled = run.sky_index is None
            search_button.disabled = not live_state["allow_search"] or state["searching"] or not run.frames or not run.steps
            play.disabled = not run.frames
            state["playing"] = False
            state["pending_frame"] = None
            playback_status.content = "**Playback: Paused · ⏸ 정지**"
            pause.disabled = True
            start, end = run.manifest.get("started_at"), run.manifest.get("finished_at")
            elapsed = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() if start and end else None
            elapsed_text = f"{elapsed:.1f} s wall time" if elapsed is not None else "not recorded"
            state_text.content = (f"**저장된 지도 · {run.manifest.get('status', 'unknown')}**  \n"
                                  f"{len(run.frames):,} 프레임 · {len(run.steps):,} 서브맵 갱신 · "
                                  f"{len(run.object_queries)} 검색  \n"
                                  f"{studio_label} · 원본 영상 / 지도 독립 갱신")
        finally:
            state["loading"] = False
        update()
        if follow_rgb.value and state["camera"] is not None:
            apply_rgb_camera()
        else:
            fit_all()

    def refresh_live():
        map_revision=None
        while not stopped.wait(.35):
            try:
                control=json.loads(live_control.read_text())
                if control['revision']==live_state['revision']:continue
                with render_lock:
                    live_state.update(revision=control['revision'],allow_search=False)
                    selected=state['query_labels'].get(object_select.value)
                    changed=control.get('map_revision')!=map_revision
                    if changed:
                        state['loading']=True
                        try:
                            run=state['run'];run.refresh_committed()
                            old_frame=int(frame.value)
                            frame.max=max(1,len(run.frames)-1)
                            step.options=[str(i) for i in run.steps];step.value=step.options[-1]
                            times,timing=frame_times(run,source_fps)
                            clock_box.update(times=times,timing=timing,path=None,path_key=None,last_index=None,clock=playback_clock(run,times))
                            frame.value=max(0,len(run.frames)-1) if follow_live.value else min(old_frame,len(run.frames)-1)
                            clock_box['clock'].seek(times[int(frame.value)],False)
                            map_revision=control.get('map_revision')
                        finally:state['loading']=False
                    run=state['run']
                    run.refresh_sky(control.get('sky_groups',{}),control.get('sky_frames',{}))
                    hide_sky.disabled=run.sky_index is None;sky_threshold.disabled=run.sky_index is None
                    known={q['query_id']:q for q in run.object_queries if not q['query_id'].startswith('v4_live_')}
                    deleted_path=run.path/'evidence/deleted_queries.json'
                    deleted=set(json.loads(deleted_path.read_text())) if deleted_path.exists() else set()
                    for name,path in control.get('semantic_results',{}).items():
                        query=json.loads((run.path/path).read_text());query['_asset_path']=path
                        if query['query_id'] not in deleted:known[query['query_id']]=query
                    run.object_queries=list(known.values())
                    state['query_labels']=saved_labels(run,saved_model_filter.value,saved_text_filter.value)
                    object_select.options=['None']+list(state['query_labels'])
                    if selected and selected in state['query_labels'].values():
                        object_select.value=next(k for k,v in state['query_labels'].items() if v==selected)
                    elif object_select.value=='None' and run.object_queries and not live_state.get('auto_selected'):
                        live_state['auto_selected']=True
                        preferred=next((q for q in run.object_queries if q['query']=='car'),run.object_queries[0])
                        object_select.value=next(k for k,v in state['query_labels'].items() if v==preferred['query_id'])
                    object_select.disabled=not run.object_queries
                    state['road_layer']=None;state['road_query_id']=None
                    state['semantic_layer']=None;state['semantic_query_id']=None
                    state['render_signature']=None
                    search_button.disabled=False
                    update()
                    search_status.content='사전 대상은 생성 중에도 조회할 수 있습니다. 임의 텍스트 정밀 검색은 지도 생성 완료 후 실행합니다.'
            except (OSError,ValueError,KeyError) as exc:
                print(f'SLAM V5 refresh deferred: {exc}',flush=True)

    run_select.disabled = live_control is not None
    run_select.on_update(load_run)
    for control in (frame, step, phase, colors, budget, hide_sky, sky_threshold, bev_plane, bev_overlay, bev_trajectory, bev_zoom, mask_3d, box_3d, mask_rgb, box_rgb, mask_bev, box_bev, playback_quality, show_road, follow_rgb, point_size):
        control.on_update(update)

    def selected_query():
        return next((q for q in state['run'].object_queries if q['query_id']==state['query_labels'].get(object_select.value,object_select.value)), None)

    def select_object(_=None):
        with render_lock:
            if state['loading'] or state['run'] is None:return
            run = state['run']; query = selected_query()
            if query:
                set_playing(False)
            saved_info.content=saved_summary(query)
            records = query.get('search',{}).get('observations',[]) if query else []
            visible_records = [o for o in records if o.get('mask_count',0)>0]
            delete_query.disabled = query is None
            state['observation_labels'] = {f"{o['source_frame_id']} · {o['query']} · 2D {o['mask_count']} / 3D {o['valid_boxes']}":o for o in visible_records}
            observation_select.options = ['전체 관측']+list(state['observation_labels'])
            observation_select.value = '전체 관측'
            observation_select.disabled = not visible_records
            if query:
                snapshot=query.get('snapshot')
                if snapshot and str(snapshot['step']) in step.options:
                    step.value=str(snapshot['step']);phase.value=snapshot['phase']
                if records:
                    target=max(o['playback_index'] for o in records if o.get('mask_count',0)) if any(o.get('mask_count',0) for o in records) else max(o['playback_index'] for o in records)
                else:
                    target=0
                    for i,event in enumerate(run.frames):
                        if event['submap_id']!=query['submap_id']:continue
                        meta=json.loads((run.path/event['asset_paths']['metadata']).read_text())
                        if meta['submap_frame_index']==query['frame_index']:
                            target=i;break
                state['legacy_query_target']=target
                frame.value=target
                if query.get('search',{}).get('mode') in ('all','sampled'):
                    follow_rgb.value=False
            update()
            if query and not follow_rgb.value and state['view_mode']!='chase':fit_all()

    def filter_saved(_):
        with render_lock:
            if state['loading'] or state['run'] is None:return
            previous=state['query_labels'].get(object_select.value)
            state['query_labels']=saved_labels(state['run'],saved_model_filter.value,saved_text_filter.value)
            object_select.options=['None']+list(state['query_labels'])
            object_select.value=next((label for label,ident in state['query_labels'].items() if ident==previous),'None')
            object_select.disabled=not state['query_labels']
            select_object()
    saved_model_filter.on_update(filter_saved)
    saved_text_filter.on_update(filter_saved)
    object_select.on_update(select_object)

    @observation_select.on_update
    def select_observation(_=None):
        with render_lock:
            if state['loading']:return
            set_playing(False)
            observation=state['observation_labels'].get(observation_select.value)
            if observation:
                frame.value=observation['playback_index']
                if state['view_mode']!='chase':follow_rgb.value=True
            elif selected_query() and selected_query().get('search',{}).get('observations'):
                frame.value=state['legacy_query_target']
                follow_rgb.value=False
            update()
            if not follow_rgb.value and state['view_mode']!='chase':fit_all()

    def watch_search(run,job,query,process=None):
        def watcher():
            try:
                while not stopped.wait(.5):
                    status_file=job/'status.json'
                    if not status_file.is_file():
                        if process is not None and process.poll() is not None:raise RuntimeError(f'worker exit {process.returncode}; {job}/worker.log')
                        continue
                    progress=json.loads(status_file.read_text())
                    if process is None:
                        progress=recover_search_status(status_file,progress)
                    elif progress.get('state')=='running' and process.poll() is not None:
                        raise RuntimeError(f'검색 프로세스 종료 ({process.returncode}). 다시 검색할 수 있습니다. {job}/worker.log')
                    if state['run'] is run:
                        search_status.content=f"**검색 중 · {query}** · {progress['message']}  \n순차 CPU 처리 중입니다. 검색 결과 수는 프레임별 관측 수입니다."
                    if progress['state']=='failed':raise RuntimeError(progress['message'])
                    if progress['state']=='completed':break
                    if process is not None and process.poll() is not None:raise RuntimeError(f'worker exit {process.returncode}; {job}/worker.log')
                else:return
                if state['run'] is run:
                    run.refresh_queries()
                    if saved_model_filter.value!='전체':saved_model_filter.value='전체'
                    if saved_text_filter.value:saved_text_filter.value=''
                    state['query_labels']=saved_labels(run,saved_model_filter.value,saved_text_filter.value)
                    object_select.options=['None']+list(state['query_labels']);object_select.disabled=False
                    result=json.loads((run.path/progress['result']).read_text())
                    object_select.value=next(label for label,ident in state['query_labels'].items() if ident==result['query_id'])
                    select_object()
                    search_status.content=(f"**검색 완료 · {query}** · 검사 {progress.get('attempted_frames','?')}/{progress.get('total_frames','?')} 프레임  \n"+
                        outcome_text(progress.get('mask_count',0),progress['valid_boxes'],progress.get('attempted_frames',1))+
                        '  \n누적 관측 수입니다. 동일 객체의 여러 프레임 관측을 포함합니다.')
            except Exception as exc:
                search_status.content=f'**검색 실패** · {exc}'
            finally:
                state['searching']=False
                search_button.disabled=not live_state['allow_search'] or not state['run'].frames or not state['run'].steps
        threading.Thread(target=watcher,daemon=True).start()

    @search_button.on_click
    def search_cached(_):
        detect_all=MODEL_OPTIONS[search_model.value] in ('rfdetr','yolo26','yolo11') and all_classes.value
        query='전체 객체' if detect_all else query_text.value.strip()
        try:
            if not detect_all:parse_queries(query)
        except ValueError as exc:
            search_status.content=str(exc);return
        run=state['run']
        if not live_state['allow_search']:
            search_status.content='지도 생성이 끝난 뒤 검색할 수 있습니다. 생성 중에는 SLAM 계산에 집중합니다.';return
        if state['searching'] or run is None or not live_state['allow_search']:return
        backend=MODEL_OPTIONS[search_model.value]
        try:
            worker_python=worker_environment(Path(__file__).resolve().parents[2],backend)
        except ValueError as exc:
            search_status.content=str(exc);return
        if not worker_python.is_file() or not run.frames or not run.steps:
            search_status.content='검색 환경과 기록된 RGB/depth/snapshot이 필요합니다.';return
        state['searching']=True;search_button.disabled=True;set_playing(False)
        job=run.path/'evidence'/'query_jobs'/f'search_{time.time_ns()}'
        job.mkdir(parents=True,exist_ok=False)
        mode=search_modes[search_mode.value]
        search_status.content=f'**검색 시작 · {query}** · {search_model.value} · {search_mode.value}'
        environment=dict(os.environ,HF_HUB_OFFLINE='1',MPLCONFIGDIR=str(job/'mpl_cache'))
        script=Path(__file__).resolve().parents[2]/'scripts'/'demo_search_cached.py'
        try:
            with (job/'worker.log').open('w') as log:
                process=subprocess.Popen([str(worker_python),str(script),'--run',str(run.path),'--query',query,
                    '--backend',backend,'--mode',mode,'--max-frames',str(int(search_limit.value)),'--frame-index',str(int(frame.value)),
                    '--output',str(job)]+(['--all-classes'] if detect_all else []),stdout=log,stderr=subprocess.STDOUT,env=environment)
            watch_search(run,job,query,process)
        except Exception as exc:
            state['searching']=False;search_button.disabled=False;search_status.content=f'검색 실패 · {exc}'


    def select_loop(_=None):
        if _ is not None and getattr(_,'client',None) is None:return
        run = state["run"]
        if run is None:
            return
        candidate = next((event for event in run.events
                          if event["event_type"] == "loop_candidate"
                          and event.get("payload", {}).get("match_id") == loop_select.value), None)
        if candidate is not None:
            source = candidate.get("payload", {}).get("query_source", "")
            match = re.search(r"(\d+)$", Path(source).stem)
            frame_id = str(int(match.group(1))) if match else ""
            index = next((i for i, event in enumerate(run.frames)
                          if str(event.get("source_frame_id")) == frame_id), None)
            if index is not None:
                frame.value = index
        update()

    loop_select.on_update(select_loop)
    def clear_saved_objects(_=None):
        with render_lock:
            object_select.value = "None"
            select_object()

    clear_objects.on_click(clear_saved_objects)

    @delete_query.on_click
    def delete_selected_query(_=None):
        with render_lock:
            query = selected_query()
            if query is None:
                return
            run = state['run']
            run.delete_query(query['query_id'])
            state['query_labels'] = saved_labels(run,saved_model_filter.value,saved_text_filter.value)
            object_select.options = ['None'] + list(state['query_labels'])
            object_select.value = 'None'
            object_select.disabled = not state['query_labels']
            select_object()
            search_status.content = '선택한 검색을 목록에서 삭제했습니다. 원본 검색 증거는 보존됩니다.'

    def reset_rgb(_=None):
        state["view_mode"]="rgb"
        follow_rgb.value = True
        update()
        apply_rgb_camera()
        panel.update_status(follow_rgb=True,view_mode="rgb")

    def free_view(_=None):
        state["view_mode"]="free"
        follow_rgb.value = False
        camera_status.content = '**자유 3D 탐색** · Reset으로 현재 RGB 카메라 시점에 복귀합니다.'
        panel.update_status(follow_rgb=False,view_mode="free")

    def chase_view(_=None):
        state['view_mode']='chase';follow_rgb.value=False
        update();apply_chase_camera()
        panel.update_status(view_mode='chase',follow_rgb=False)
    chase_button.on_click(chase_view)
    chase_distance.on_update(lambda _: (update(),apply_chase_camera()) if state['view_mode']=='chase' else None)
    def follow_mode(_):
        if follow_rgb.value:state['view_mode']='rgb'
        elif state['view_mode']=='rgb':state['view_mode']='free'
        update()
    follow_rgb.on_update(follow_mode)

    def fit_map(_=None):
        free_view()
        fit_all()

    fit.on_click(fit_map)
    reset.on_click(reset_rgb)
    panel.resize = update
    def panel_action(action, payload=None):
        payload = payload or {}
        if action=='gpu_fallback':
            state['gpu_fallback']=bool(payload.get('enabled',True));state['render_signature']=None;update();return
        if action=='video_clock':
            return  # V5 server clock is authoritative; late decoders/tabs cannot rewind it.
        if action == 'chase': chase_view()
        elif action == 'reset': reset_rgb()
        elif action == 'free': free_view()
        elif action == 'play': toggle_play()
        elif action == 'pause':
            if payload.get('generation') is not None and payload['generation']!=clock_box['generation']:return
            set_playing(False)
        elif action in ('frame','previous_frame','next_frame'):
            if not state['run'].frames:return
            target = float(payload.get('frame', frame.value + (-1 if action == 'previous_frame' else 1)))
            if not np.isfinite(target): raise ValueError('Invalid frame')
            set_playing(False)
            frame.value = int(np.clip(target,0,len(state['run'].frames)-1))
            update()
        elif action == 'bev_view':
            zoom = float(payload.get('zoom',bev_zoom.value))
            pan = np.asarray(payload.get('pan',state['bev_pan']),float)
            if not np.isfinite(zoom) or not .5 <= zoom <= 8 or pan.shape != (2,) or not np.isfinite(pan).all() or np.abs(pan).max()>10:
                raise ValueError('Invalid BEV view')
            state['bev_pan'] = pan.tolist()
            bev_zoom.value = round(zoom*4)/4
            update()
        elif action in ('zoom_in' , 'zoom_out', 'zoom_reset'):
            if action == 'zoom_reset': state['bev_pan'] = [0.,0.]
            bev_zoom.value = 1. if action == 'zoom_reset' else min(8., max(.5, bev_zoom.value + (.5 if action == 'zoom_in' else -.5)))
            update()
        else:
            control = {'road_overlay': bev_overlay, 'trajectory': bev_trajectory,
                       'mask_3d': mask_3d, 'box_3d':box_3d, 'mask_rgb': mask_rgb, 'mask_bev': mask_bev, 'box_bev': box_bev, 'box_rgb': box_rgb}[action]
            control.value = not control.value
            update()
    panel.action = panel_action
    def set_playing(value):
        if value != state['playing']:clock_box['generation']+=1
        if clock_box['clock'] is not None:
            if value and not state['playing']:
                clock_box['clock'].seek(clock_box['times'][int(frame.value)],True)
            else:clock_box['clock'].set_playing(value)
        state["playing"] = value
        state['render_signature']=None
        update()
        playback_status.content = "**Playback: Playing · ▶ 재생 중**" if value else "**Playback: Paused · ⏸ 정지**"
        pause.disabled = not value
        panel.update_status(playing=value)

    def toggle_play(_=None):
        if state["run"] is None or not state["run"].frames:
            return
        if state["playing"]:
            set_playing(False)
            return
        if int(frame.value) >= len(state["run"].frames) - 1 or (clock_box["clock"] and clock_box["clock"].position() >= clock_box["clock"].duration-.02):
            state["pending_frame"] = 0
            frame.value = 0
            update()
        set_playing(True)

    play.on_click(toggle_play)
    pause.on_click(lambda _: set_playing(False))
    pause.disabled = True

    def smooth_status():
        clock=clock_box['clock']
        index=int(frame.value)
        return {'view_camera_position':state.get('view_camera_position'),'view_camera_source':state.get('view_camera_source'),'version':'slam-v5','clock_source':'server-monotonic','view_mode':state['view_mode'],'chase_distance':state['chase_scale']*chase_distance.value,'generation':clock_box['generation'],'playing':state['playing'],'time':clock.position() if clock else 0,
                'duration':clock.duration if clock else 0,'rendered_time':float(clock_box['times'][index]) if clock else 0,
                'frame_index':index,'media': '/native.mp4?run='+run_select.value if panel.media else None,
                'camera_path_key':[clock_box['run_key'],step.value,phase.value],'gpu_scene':gpu_scene.snapshot(), 'point_scale':point_size.value,'playback_quality':playback_quality.value, 'run':run_select.value,'timing':clock_box['timing'],'follow_rgb':follow_rgb.value,
                'selected_query':state['run'] is not None and selected_query() is not None,'mask_rgb':mask_rgb.value,'box_rgb':box_rgb.value}
    def camera_path_packet():
        if state['run'] is None or step.value=='Unavailable':return {}
        key=(clock_box['run_key'],step.value,phase.value)
        if key!=clock_box['path_key']:
            clock_box['path']=CameraPath(state['run'],int(step.value),phase.value,clock_box['times']);clock_box['path_key']=key
        return {'key':list(key),'samples':clock_box['path'].packet()}
    panel.camera_path=camera_path_packet
    panel.status=smooth_status

    def playback():
        last_render=0.
        while not stopped.wait(.01):
            clock=clock_box['clock']
            if not state['playing'] or clock is None:continue
            if clock.position()>=clock.duration:
                with render_lock:
                    if state['playing'] and clock is clock_box['clock']:
                        frame.value=len(state['run'].frames)-1
                        set_playing(False)
                continue
            target=clock.target()
            if target==int(frame.value) or time.monotonic()-last_render<.20:continue
            with render_lock:
                if not state['playing'] or state['loading']:continue
                target=clock.target()
                frame.value=target
                update()
                last_render=time.monotonic()

    def interpolate_camera():
        while not stopped.wait(.05):
            if not state['playing'] or state['view_mode'] not in ('rgb','chase') or state['loading'] or clock_box['clock'] is None:continue
            key=(clock_box['run_key'],step.value,phase.value)
            if step.value=='Unavailable':continue
            if key!=clock_box['path_key']:
                clock_box['path']=CameraPath(state['run'],int(step.value),phase.value,clock_box['times'])
                clock_box['path_key']=key
            camera=clock_box['path'].at(clock_box['clock'].position())
            if camera is None:continue
            if state['view_mode']=='chase':
                apply_chase_camera(camera);continue
            for client in server.get_clients().values():
                with client.atomic():
                    client.camera.position=camera['position'];client.camera.wxyz=camera['wxyz'];client.camera.up_direction=camera['up'];client.camera.fov=camera['fov']
    camera_thread=threading.Thread(target=interpolate_camera,daemon=True);camera_thread.start()

    thread = threading.Thread(target=playback, daemon=True)
    thread.start()
    server.on_client_connect(lambda client: apply_chase_camera(client=client) if state["view_mode"]=="chase" else (apply_rgb_camera(client) if follow_rgb.value and state["camera"] is not None else fit_all()))
    load_run()
    if live_control:
        search_button.disabled=True
        threading.Thread(target=refresh_live,daemon=True).start()
    running=[]
    for status_file in (state['run'].path/'evidence'/'query_jobs').glob('*/status.json'):
        progress=recover_search_status(status_file,json.loads(status_file.read_text()))
        if progress.get('state')=='running':running.append((progress.get('total_frames',0),status_file.stat().st_mtime,status_file,progress))
    if not running and live_state['allow_search']:
        search_status.content='검색 준비 완료 · 모델과 범위를 선택한 뒤 Search를 누르세요.'
    if running:
        _,_,status_file,progress=max(running,key=lambda v:(v[0],v[1]))
        state['searching']=True;search_button.disabled=True
        watch_search(state['run'],status_file.parent,progress.get('query',status_file.parent.name))
    print(f"Demo main viewer: http://127.0.0.1:{port} (Viser: {server.get_port()})", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stopped.set()
        thread.join(timeout=2)
        camera_thread.join(timeout=2)
        panel.close()
        server.stop()
