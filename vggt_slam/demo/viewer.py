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

from vggt_slam.demo.query_display import result_observations, overlay_query_rgb
from vggt_slam.demo.road import RoadLayer, best_road_query, raster_connectivity
from vggt_slam.demo.cache import CachedRun
from vggt_slam.demo.bev import raster_bev
from vggt_slam.demo.camera_view import rgb_camera, raster_camera, overview_distance, display_resolution
from vggt_slam.demo.main_panel import MainPanel, free_port
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


def serve(run_dir, port=8090):
    run_dir = Path(run_dir).resolve()
    runs = {p.name: p for p in run_dir.parent.iterdir() if (p / "manifest.json").is_file()}
    if run_dir.name not in runs:
        raise ValueError(f"run manifest not found: {run_dir}")
    panel = MainPanel(port)
    server = viser.ViserServer(host="127.0.0.1", port=free_port())
    panel.viser_port = server.get_port()
    server.gui.configure_theme(control_layout="fixed", control_width="large", dark_mode=True,
                               brand_color=(34, 211, 238), show_logo=False, show_share_button=False)
    server.gui.add_markdown("### VGGT · Map Studio")
    run_select = server.gui.add_dropdown("Run", options=sorted(runs), initial_value=run_dir.name)
    state_text = server.gui.add_markdown("")
    frame = server.gui.add_slider("Frame", min=0, max=1, step=1, initial_value=0)
    play = server.gui.add_button("Play / Pause", color="cyan", icon=viser.Icon.PLAYER_PLAY)
    pause = server.gui.add_button("Pause playback", icon=viser.Icon.PLAYER_PAUSE)
    playback_status = server.gui.add_markdown("**Playback: Paused · 정지**")
    blank = np.full((80, 140, 3), (15, 23, 42), dtype=np.uint8)
    follow_rgb = server.gui.add_checkbox("RGB 시점 추적", initial_value=True)
    reset = server.gui.add_button("Reset RGB camera", color="cyan", icon=viser.Icon.CAMERA, visible=False)
    camera_status = server.gui.add_markdown("현재 RGB 카메라 시점을 기본으로 표시합니다.")
    tabs = server.gui.add_tab_group()
    with tabs.add_tab("지도 · Map", icon=viser.Icon.MAP):
        fit = server.gui.add_button("Fit map", color="cyan", icon=viser.Icon.FOCUS_2)
        colors = server.gui.add_dropdown("Colors", options=["RGB", "Submaps"], initial_value="RGB")
        budget = server.gui.add_slider("Displayed point limit", min=50_000, max=2_000_000, step=50_000, initial_value=600_000)
        point_size = server.gui.add_slider("Point size (점 크기 배율)", min=0.1, max=10.0, step=0.1, initial_value=1.0)
        mask_3d = server.gui.add_checkbox("3D segmentation mask", initial_value=True)
        box_rgb = server.gui.add_checkbox("RGB bounding boxes", initial_value=False)
        mask_bev = server.gui.add_checkbox("BEV segmentation mask", initial_value=False)
        box_bev = server.gui.add_checkbox("BEV bounding boxes", initial_value=False)
        mask_rgb = server.gui.add_checkbox("RGB segmentation mask", initial_value=True)
        show_road = server.gui.add_checkbox("Show road · 3D 도로", initial_value=True)
        road_info = server.gui.add_markdown("")
        hide_sky = server.gui.add_checkbox("Hide sky", initial_value=True)
        with server.gui.add_folder("하늘 제거 · Sky filter", expand_by_default=False):
            sky_threshold = server.gui.add_slider("Sky threshold", min=8, max=192, step=8, initial_value=32)
            sky_info = server.gui.add_markdown("")
            sky_image = server.gui.add_image(blank, label="Sky mask overlay")
        with server.gui.add_folder("실시간 2D 맵 · BEV"):
            bev_overlay = server.gui.add_checkbox("Overlay Road connectivity", initial_value=True)
            bev_trajectory = server.gui.add_checkbox("주행 기록 · BEV trajectory", initial_value=True)
            bev_zoom = server.gui.add_slider("BEV zoom", min=.5, max=8., step=.25, initial_value=1.)
            bev_plane = server.gui.add_dropdown("BEV plane", options=["XZ", "XY", "YZ"], initial_value="XZ")
            bev_image = server.gui.add_image(blank, label="BEV map", format="png", visible=False)
            bev_info = server.gui.add_markdown("")
        rgb_gui = server.gui.add_image(blank, label="RGB", visible=False)
        info = server.gui.add_markdown("")
    with tabs.add_tab("검색 · Search", icon=viser.Icon.SEARCH):
        server.gui.add_markdown("### 무엇을 찾으시나요?\n현재 run의 RGB에서 대상을 찾고 3D 위치를 표시합니다.")
        query_text = server.gui.add_text("Query", initial_value="car", hint="예: car, tree, truck, printer")
        search_modes = {"전구간 전수": "all", "전구간 표본": "sampled", "현재 RGB": "current", "PE 후보 찾기": "candidate"}
        search_mode = server.gui.add_dropdown("Search scope", options=list(search_modes), initial_value="전구간 전수")
        search_limit = server.gui.add_slider("표본 프레임 수", min=4, max=96, step=4, initial_value=24)
        server.gui.add_markdown("전수는 모든 고유 프레임을 검사합니다. CPU에서 수 분 이상 걸릴 수 있습니다. 결과 수는 프레임별 관측 수이며 고유 객체 수가 아닙니다.")
        search_button = server.gui.add_button("Search", color="cyan", icon=viser.Icon.SEARCH)
        search_status = server.gui.add_markdown("**검색 대기** · 텍스트를 입력하고 Search를 누르세요.")
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
    state = {"run": None, "cloud": None, "lines": None, "edges": None, "frustum": None,
             "bev_pan": [0.,0.], "semantic_layer": None, "semantic_query_id": None, "road_cloud": None, "road_layer": None, "road_query_id": None, "object_boxes": [], "searching": False, "query_labels": {}, "camera": None, "camera_shape": None, "observation_labels": {}, "legacy_query_target": 0,
             "center": np.zeros(3), "radius": 1.0, "loading": False, "playing": False,
             "pending_frame": None, "rendering": False, "render_signature": None}
    stopped = threading.Event()
    render_lock = threading.RLock()

    @point_size.on_update
    def resize_points(_):
        with render_lock:
            if state["cloud"] is not None:
                state["cloud"].point_size = state["radius"] / 2000 * point_size.value

    def fit_all():
        for client in server.get_clients().values():
            fov = np.radians(60)
            distance = overview_distance(state['radius'], fov, client.camera.aspect)
            direction = np.array([0.35, -0.5, -0.65])
            client.camera.up_direction = (0, -1, 0)
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

    def _update():
        if state["loading"] or state["run"] is None:
            return
        run = state["run"]
        frame_index = int(frame.value)
        # Searches can finish without reloading the run: keep the summary current.
        start, end = run.manifest.get('started_at'), run.manifest.get('finished_at')
        elapsed = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() if start and end else None
        state_text.content = (f"**저장된 지도 · {run.manifest.get('status', 'unknown')}**  \n"
                              f"{len(run.frames):,} 프레임 · {len(run.steps):,} 서브맵 갱신 · {len(run.object_queries)} 검색  \n"
                              "캐시 재생 · 목표 2fps")
        chosen_step = None if step.value == "Unavailable" else int(step.value)
        result = run.render(step=chosen_step, phase=phase.value,
                            frame_index=frame_index if run.frames else None,
                            budget=int(budget.value), color_mode=colors.value,
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
        if bev_selected:
            bev_observation = state['observation_labels'].get(observation_select.value)
            bev_detections = bev_selected.get('detections',[])
            if bev_observation:
                bev_file = run.path / Path(bev_selected['_asset_path']).parent / bev_observation['result']
                bev_detections = json.loads(bev_file.read_text()).get('detections',[])
            bev_snapshot = bev_selected.get('snapshot')
            compatible_bev = bev_snapshot is None or (bev_snapshot['step']==chosen_step and bev_snapshot['phase']==phase.value)
            bev_masks = None
            if compatible_bev and box_bev.value:
                bev_boxes = [_obb_segments(d['center'],d['extent'],d['rotation']) for d in bev_detections
                    if d.get('valid') and d.get('playback_index',bev_observation['playback_index'] if bev_observation else state['legacy_query_target']) <= frame_index]
            if mask_bev.value and bev_selected.get('search',{}).get('observations'):
                if state['semantic_query_id'] != bev_selected['query_id']:
                    state['semantic_layer'] = RoadLayer(run, bev_selected, prompt=None)
                    state['semantic_query_id'] = bev_selected['query_id']
                bev_masks = state['semantic_layer'].world(run,chosen_step,phase.value,frame_index,
                    only_frame=bev_observation['playback_index'] if bev_observation else None)
        bev_image.image, bev_stats = raster_bev(pts, result['colors'], trajectory, plane=bev_plane.value,
            zoom=bev_zoom.value, pan=state['bev_pan'], show_trajectory=bev_trajectory.value,
            road_points=road_points if bev_overlay.value and layer else None,
            mask_points=bev_masks, boxes=bev_boxes)
        bev_info.content = (f"**BEV · {bev_plane.value} · {bev_zoom.value:g}×** · {bev_stats['occupied_cells']:,} 관측 셀  \n휠: 줌 · 드래그: 이동 · 초록: 도로 연결 · 청록: 분할 · 빨강: 박스")
        for key in ("cloud", "lines", "edges", "frustum", "road_cloud"):
            if state[key] is not None:
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
            state["cloud"] = server.scene.add_point_cloud("/map", points=pts, colors=result["colors"],
                                                          point_size=state["radius"] / 2000 * point_size.value, point_shape="circle")
        road_display = road_points[np.linspace(0, len(road_points)-1, min(len(road_points), 150000), dtype=int)] if len(road_points) else road_points
        if mask_3d.value and show_road.value and len(road_display):
            state['road_cloud'] = server.scene.add_point_cloud('/road_surface', points=road_display,
                colors=(34,197,94), point_size=state['radius']/1800*point_size.value, point_shape='circle')
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
                                "실제 skyseg 분할 + 경계 2px · 낮은 threshold = 강한 제거")
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
        info.content = (f"**{result['source']}** · displayed {len(pts):,} points · full PCD {total} points  \n"
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
                                                  frame_index, state['legacy_query_target'], show_masks=mask_rgb.value, show_boxes=box_rgb.value)
            snapshot = selected_object.get('snapshot')
            compatible = snapshot is None or (snapshot['step']==chosen_step and snapshot['phase']==phase.value)
            for detection in detections if compatible and mask_3d.value else []:
                playback = detection.get('playback_index', observation['playback_index'] if observation else state['legacy_query_target'])
                if not detection.get('valid') or playback > frame_index: continue
                segments = _obb_segments(detection['center'], detection['extent'], detection['rotation'])
                projected_boxes.append(segments)
                state['object_boxes'].append(server.scene.add_line_segments(
                    f"/cached_object_{detection['index']}", points=segments, colors=(255,40,40), line_width=3))
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
                    object_info.content += f"  \n대표 이미지 frame {representative['source_frame_id'] if representative else '?'} · 전체 관측을 지도에 표시합니다. Result frame에서 각 RGB·마스크를 확인하세요."
            else:
                object_info.content = (f"Query **{selected_object['query']}** · frame {selected_object['frame_index']} · "
                                       f"submap {selected_object['submap_id']} · valid 3D boxes {len(state['object_boxes'])}  \n" +
                                       outcome_text(native_count,saved_valid,len(search.get('attempts',[])) or 1))
                object_info.content += '  \n이전 후보 검색 결과입니다. 전구간 검색 결과와 구분하세요.'
            if not compatible:
                object_info.content += '  \n박스 숨김: 기록된 optimization step/after를 선택하세요.'

        if camera_projection is not None:
            foreground, foreground_colors = run.camera_preview(frame_index, chosen_step, phase.value,
                    hide_sky.value, int(sky_threshold.value), budget=min(50000, int(budget.value)))
            remaining = max(0, int(budget.value) - len(foreground))
            idx = np.linspace(0, len(pts)-1, min(len(pts), remaining), dtype=int)
            camera_points = np.concatenate([pts[idx], foreground])
            camera_colors = np.concatenate([result['colors'][idx], foreground_colors])
            if mask_3d.value and show_road.value and len(road_display):
                camera_points = np.concatenate([road_display, camera_points])
                camera_colors = np.concatenate([np.tile(np.array([34,197,94], np.uint8), (len(road_display), 1)), camera_colors])
            camera_image, raster_stats = raster_camera(camera_points, camera_colors, camera_projection, camera_shape,
                                                       point_scale=point_size.value, boxes=projected_boxes,
                                                       output_shape=display_resolution(camera_shape, panel.viewport), antialias=1.5)
            if follow_rgb.value:
                apply_rgb_camera()
        else:
            camera_image, raster_stats = blank, {}
            camera_status.content = '현재 프레임 카메라가 없습니다. 다른 snapshot 또는 프레임을 선택하세요.'
        panel.publish(rgb_gui.image, bev_image.image, camera_image, {
            'frame_index': frame_index, 'frame_count': len(run.frames),
            'source_frame_id': current['source_frame_id'] if current else 'N/A',
            'timestamp_label': f"{meta['source_timestamp']:.2f} s" if current and isinstance(meta.get('source_timestamp'), (int, float)) else 'N/A',
            'playing': state['playing'], 'follow_rgb': follow_rgb.value,
            'camera_available': camera_projection is not None, 'aspect': camera_shape[1]/camera_shape[0],
            'road_points': len(road_points), 'road_visible': bool(mask_3d.value and show_road.value and len(road_points)), 'bev_mode': 'Road connectivity' if bev_overlay.value and layer else '표면 지도', 'connectivity': bev_stats['connectivity'],
            'bev_pan': state['bev_pan'], 'mask_bev': mask_bev.value, 'box_bev': box_bev.value, 'box_rgb': box_rgb.value, 'bev_box_count': len(bev_boxes),
            'bev_zoom': bev_zoom.value, 'bev_trajectory': bev_trajectory.value, 'mask_3d': mask_3d.value, 'mask_rgb': mask_rgb.value,
            'point_count': len(pts), 'bev_plane': bev_plane.value, 'raster': raster_stats,
            'camera_position': state['camera']['position'].tolist() if state['camera'] is not None else None,
        })

    def update(_=None):
        with render_lock:
            signature = (str(state["run"].path) if state["run"] is not None else None,
                         frame.value, step.value, phase.value, colors.value, budget.value,
                         tuple(state['bev_pan']), box_rgb.value, mask_bev.value, box_bev.value, panel.viewport, loop_select.value, object_select.value, observation_select.value, hide_sky.value, sky_threshold.value, bev_plane.value, bev_overlay.value, bev_trajectory.value, bev_zoom.value, mask_3d.value, mask_rgb.value, show_road.value, follow_rgb.value, point_size.value)
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
            state["semantic_layer"] = None
            state["semantic_query_id"] = None
            state["bev_pan"] = [0.,0.]
            state["road_layer"] = None
            state["road_query_id"] = None
            frame.max = max(1, len(run.frames) - 1)
            frame.disabled = not run.frames
            frame.value = max(0, len(run.frames) - 1)
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
            state["query_labels"] = {query_label(item): item["query_id"] for item in run.object_queries}
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
            search_button.disabled = state["searching"] or not run.frames or not run.steps
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
                                  "캐시 재생 · 목표 2fps")
        finally:
            state["loading"] = False
        update()
        if follow_rgb.value and state["camera"] is not None:
            apply_rgb_camera()
        else:
            fit_all()

    run_select.on_update(load_run)
    for control in (frame, step, phase, colors, budget, hide_sky, sky_threshold, bev_plane, bev_overlay, bev_trajectory, bev_zoom, mask_3d, mask_rgb, box_rgb, mask_bev, box_bev, show_road, follow_rgb, point_size):
        control.on_update(update)

    def selected_query():
        return next((q for q in state['run'].object_queries if q['query_id']==state['query_labels'].get(object_select.value,object_select.value)), None)

    def select_object(_=None):
        with render_lock:
            if state['loading'] or state['run'] is None:return
            run = state['run']; query = selected_query()
            if query:
                set_playing(False)
            records = query.get('search',{}).get('observations',[]) if query else []
            visible_records = result_observations(query) if query else []
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
                    target=max(o['playback_index'] for o in records)
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
            if query and not follow_rgb.value:fit_all()

    object_select.on_update(select_object)

    @observation_select.on_update
    def select_observation(_=None):
        with render_lock:
            if state['loading']:return
            set_playing(False)
            observation=state['observation_labels'].get(observation_select.value)
            if observation:
                frame.value=observation['playback_index']
                follow_rgb.value=True
            elif selected_query() and selected_query().get('search',{}).get('observations'):
                frame.value=max(o['playback_index'] for o in selected_query()['search']['observations'])
                follow_rgb.value=False
            update()
            if not follow_rgb.value:fit_all()

    def watch_search(run,job,query,process=None):
        def watcher():
            try:
                while not stopped.wait(.5):
                    status_file=job/'status.json'
                    if not status_file.is_file():
                        if process is not None and process.poll() is not None:raise RuntimeError(f'worker exit {process.returncode}; {job}/worker.log')
                        continue
                    progress=json.loads(status_file.read_text())
                    if state['run'] is run:
                        search_status.content=f"**검색 중 · {query}** · {progress['message']}  \n순차 CPU 처리 중입니다. 검색 결과 수는 프레임별 관측 수입니다."
                    if progress['state']=='failed':raise RuntimeError(progress['message'])
                    if progress['state']=='completed':break
                    if process is not None and process.poll() is not None:raise RuntimeError(f'worker exit {process.returncode}; {job}/worker.log')
                else:return
                if state['run'] is run:
                    run.refresh_queries()
                    state['query_labels']={query_label(item):item['query_id'] for item in run.object_queries}
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
                search_button.disabled=not state['run'].frames or not state['run'].steps
        threading.Thread(target=watcher,daemon=True).start()

    @search_button.on_click
    def search_cached(_):
        query=query_text.value.strip()
        try:parse_queries(query)
        except ValueError as exc:
            search_status.content=str(exc);return
        run=state['run']
        if state['searching'] or run is None:return
        worker_python=Path(__file__).resolve().parents[2]/'.venv-open-set'/'bin'/'python'
        if not worker_python.is_file() or not run.frames or not run.steps:
            search_status.content='검색 환경과 기록된 RGB/depth/snapshot이 필요합니다.';return
        state['searching']=True;search_button.disabled=True;set_playing(False)
        job=run.path/'evidence'/'query_jobs'/f'search_{time.time_ns()}'
        job.mkdir(parents=True,exist_ok=False)
        mode=search_modes[search_mode.value]
        search_status.content=f'**검색 시작 · {query}** · {search_mode.value}'
        environment=dict(os.environ,HF_HUB_OFFLINE='1',MPLCONFIGDIR=str(job/'mpl_cache'))
        script=Path(__file__).resolve().parents[2]/'scripts'/'demo_search_cached.py'
        try:
            with (job/'worker.log').open('w') as log:
                process=subprocess.Popen([str(worker_python),str(script),'--run',str(run.path),'--query',query,
                    '--mode',mode,'--max-frames',str(int(search_limit.value)),'--frame-index',str(int(frame.value)),
                    '--output',str(job)],stdout=log,stderr=subprocess.STDOUT,env=environment)
            watch_search(run,job,query,process)
        except Exception as exc:
            state['searching']=False;search_button.disabled=False;search_status.content=f'검색 실패 · {exc}'

    def select_loop(_=None):
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
            state['query_labels'] = {query_label(item): item['query_id'] for item in run.object_queries}
            object_select.options = ['None'] + list(state['query_labels'])
            object_select.value = 'None'
            object_select.disabled = not state['query_labels']
            select_object()
            search_status.content = '선택한 검색을 목록에서 삭제했습니다. 원본 검색 증거는 보존됩니다.'

    def reset_rgb(_=None):
        follow_rgb.value = True
        update()
        apply_rgb_camera()
        panel.update_status(follow_rgb=True)

    def free_view(_=None):
        follow_rgb.value = False
        camera_status.content = '**자유 3D 탐색** · Reset으로 현재 RGB 카메라 시점에 복귀합니다.'
        panel.update_status(follow_rgb=False)

    def fit_map(_=None):
        free_view()
        fit_all()

    fit.on_click(fit_map)
    reset.on_click(reset_rgb)
    panel.resize = update
    def panel_action(action, payload=None):
        payload = payload or {}
        if action == 'reset': reset_rgb()
        elif action == 'free': free_view()
        elif action == 'play': toggle_play()
        elif action == 'pause': set_playing(False)
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
                       'mask_3d': mask_3d, 'mask_rgb': mask_rgb, 'mask_bev': mask_bev, 'box_bev': box_bev, 'box_rgb': box_rgb}[action]
            control.value = not control.value
            update()
    panel.action = panel_action
    def set_playing(value):
        state["playing"] = value
        playback_status.content = "**Playback: Playing · ▶ 재생 중**" if value else "**Playback: Paused · ⏸ 정지**"
        pause.disabled = not value
        panel.update_status(playing=value)

    def toggle_play(_=None):
        if state["run"] is None or not state["run"].frames:
            return
        if state["playing"]:
            set_playing(False)
            return
        if int(frame.value) >= len(state["run"].frames) - 1:
            state["pending_frame"] = 0
            frame.value = 0
        set_playing(True)

    play.on_click(toggle_play)
    pause.on_click(lambda _: set_playing(False))
    pause.disabled = True

    def playback():
        while not stopped.wait(0.5):
            # Result selection and the next playback tick must not race: a queued
            # tick must recheck playing after the selection pauses the timeline.
            with render_lock:
                if not state["playing"] or state["run"] is None or not state["run"].frames:
                    continue
                if state["loading"] or state["rendering"] or state["pending_frame"] is not None:
                    continue
                if int(frame.value) >= len(state["run"].frames) - 1:
                    set_playing(False)
                    playback_status.content = "**Playback: Finished · 재생 완료** · 다시 누르면 처음부터 시작합니다."
                else:
                    target = int(frame.value) + 1
                    state["pending_frame"] = target
                    frame.value = target
                    update()

    thread = threading.Thread(target=playback, daemon=True)
    thread.start()
    server.on_client_connect(lambda client: apply_rgb_camera(client) if follow_rgb.value and state["camera"] is not None else fit_all())
    load_run()
    running=[]
    for status_file in (state['run'].path/'evidence'/'query_jobs').glob('*/status.json'):
        progress=json.loads(status_file.read_text())
        if progress.get('state')=='running':running.append((progress.get('total_frames',0),status_file.stat().st_mtime,status_file,progress))
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
        panel.close()
        server.stop()
