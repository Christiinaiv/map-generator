import random
import warnings
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from collections import deque
from dataclasses import dataclass
from enum import Enum
from shapely.errors import ShapelyError
from shapely.geometry import (Point, Polygon, MultiPoint,
                              MultiPolygon, LineString, MultiLineString)
from shapely.ops import voronoi_diagram, unary_union, nearest_points
from scipy.interpolate import splprep, splev

warnings.filterwarnings("ignore")

SCALE = 1.0
PLAYER_POSITIONS = [(0.04, 0.04), (0.96, 0.96)]
CORNER_ISLANDS   = [(0.04, 0.96), (0.96, 0.04)]
CENTRAL_MIN = 0.22
CENTRAL_MAX = 0.78
MIN_AREA         = 0.008
PLAYER_MIN_AREA  = 0.050
PLAYER_AREA_DIFF = 0.12
MAX_ATTEMPTS = 20000
POISSON_MIN_DIST = 0.065

class RegionType(Enum):
    PLAYER            = "player"
    ISLAND            = "island"
    CLUSTER_CENTER    = "cluster_center"
    CLUSTER_SATELLITE = "cluster_satellite"

@dataclass
class Region:
    poly:      object
    type:      str
    area:      float
    point_idx: int

def safe_polygon(geom):
    if isinstance(geom, MultiPolygon):
        return max(geom.geoms, key=lambda g: g.area)
    return geom

def random_central(pad=0.06):
    cx = random.uniform(CENTRAL_MIN + pad, CENTRAL_MAX - pad)
    cy = random.uniform(CENTRAL_MIN + pad, CENTRAL_MAX - pad)
    return cx, cy

def poisson_disc_central(n_points, min_dist=POISSON_MIN_DIST, pad=0.07, max_tries=500):
    fixed = list(PLAYER_POSITIONS) + list(CORNER_ISLANDS)
    placed = []
    for _ in range(max_tries * n_points):
        cx = random.uniform(CENTRAL_MIN + pad, CENTRAL_MAX - pad)
        cy = random.uniform(CENTRAL_MIN + pad, CENTRAL_MAX - pad)
        too_close = any(np.hypot(cx - ex, cy - ey) < min_dist for ex, ey in placed + fixed)
        if not too_close:
            placed.append((cx, cy))
        if len(placed) == n_points:
            return placed
    while len(placed) < n_points:
        placed.append(random_central(pad=pad))
    return placed

def build_island_graph(all_islands, max_dist=0.14):
    n = len(all_islands)
    graph = {i: [] for i in range(n)}
    polys = [isl for _, isl, _, _c in all_islands]
    for i in range(n):
        for j in range(i + 1, n):
            try:
                if polys[i].distance(polys[j]) < max_dist:
                    graph[i].append(j)
                    graph[j].append(i)
            except Exception:
                pass
    return graph

def is_connected(graph):
    if not graph:
        return True
    start = next(iter(graph))
    visited = set()
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                queue.append(neighbor)
    return len(visited) == len(graph)

def graph_stats(graph):
    if not graph:
        return {}
    degrees = [len(neighbors) for neighbors in graph.values()]
    return {
        "nodes":      len(graph),
        "edges":      sum(degrees) // 2,
        "avg_degree": round(sum(degrees) / len(degrees), 2),
        "max_degree": max(degrees),
        "min_degree": min(degrees),
        "connected":  is_connected(graph),
    }

def make_cluster_points(cx, cy, n_satellites=None, max_sat=2):
    if n_satellites is None:
        n_satellites = random.randint(1, max_sat)
    pts = [Point(cx, cy)]
    for _ in range(n_satellites):
        a = random.uniform(0, 2 * np.pi)
        r = random.uniform(0.028, 0.052)
        px = np.clip(cx + r * np.cos(a), 0.02, 0.98)
        py = np.clip(cy + r * np.sin(a), 0.02, 0.98)
        pts.append(Point(px, py))
    return pts

def _try_generate(island_number, cluster_number, player_min_area, player_area_diff, min_area, attempts):
    boundary = Polygon([(0, 0), (SCALE, 0), (SCALE, SCALE), (0, SCALE)])
    free_islands = island_number - 2

    for attempt in range(attempts):
        points = []
        for px, py in PLAYER_POSITIONS:
            points.append((Point(px, py), "player"))
        for gx, gy in CORNER_ISLANDS:
            points.append((Point(gx, gy), "island"))

        n_central = max(0, free_islands) + cluster_number
        central_coords = poisson_disc_central(n_central)

        for i in range(max(0, free_islands)):
            cx, cy = central_coords[i]
            points.append((Point(cx, cy), "island"))

        cluster_groups = []
        max_sat = 2 if (island_number + cluster_number) >= 8 else 3
        for i in range(cluster_number):
            cx, cy = central_coords[max(0, free_islands) + i]
            cpts = make_cluster_points(cx, cy, max_sat=max_sat)
            indices = []
            for j, pt in enumerate(cpts):
                tag = "cluster_center" if j == 0 else "cluster_satellite"
                indices.append(len(points))
                points.append((pt, tag))
            cluster_groups.append(indices)

        mp = MultiPoint([p[0] for p in points])
        envelope = Polygon([(-1, -1), (2, -1), (2, 2), (-1, 2)])
        try:
            vor = voronoi_diagram(mp, envelope=envelope)
        except Exception:
            continue

        regions  = []
        assigned = set()

        for poly in vor.geoms:
            clipped = poly.intersection(boundary)
            if clipped.is_empty:
                continue
            clipped = safe_polygon(clipped)
            if clipped.area < 1e-7:
                continue

            best_dist, best_type, best_idx = float('inf'), None, None
            for idx, (pt, t) in enumerate(points):
                if idx in assigned:
                    continue
                d = clipped.distance(pt)
                if d < best_dist:
                    best_dist, best_type, best_idx = d, t, idx

            if best_type is not None:
                regions.append(Region(
                    poly=clipped, type=best_type, area=clipped.area, point_idx=best_idx,
                ))
                assigned.add(best_idx)

        if sum(1 for r in regions if r.type == "player")            != 2:              continue
        if sum(1 for r in regions if r.type == "island")            != island_number:  continue
        if sum(1 for r in regions if r.type == "cluster_center")    != cluster_number: continue
        if any(r.area < min_area for r in regions):
            continue

        players = [r for r in regions if r.type == "player"]
        p1, p2  = players[0].area, players[1].area

        if p1 < player_min_area or p2 < player_min_area:
            continue

        max_non_player = max(r.area for r in regions if r.type != "player")
        if min(p1, p2) <= max_non_player:
            continue
        if abs(p1 - p2) > player_area_diff:
            continue

        for cluster_indices in cluster_groups:
            cr = [r for r in regions if r.point_idx in cluster_indices]
            if not cr:
                continue
            largest = max(cr, key=lambda r: r.area)
            for r in cr:
                r.type = "cluster_satellite"
            largest.type = "cluster_center"

        print(f"    OK за {attempt+1} спроб | гравці {p1:.3f}/{p2:.3f} | макс.інший {max_non_player:.3f}")
        return regions, cluster_groups

    return None, None

def generate_map(island_number, cluster_number, seed=None):
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    print("  [1/3] Суворий режим…")
    r, cg = _try_generate(island_number, cluster_number, PLAYER_MIN_AREA, PLAYER_AREA_DIFF, MIN_AREA, MAX_ATTEMPTS)
    if r: return r, cg

    print("  [2/3] Резервний режим (пом'якшені обмеження)…")
    r, cg = _try_generate(island_number, cluster_number, 0.038, 0.20, 0.005, MAX_ATTEMPTS)
    if r:
        print("    (резервні параметри)")
        return r, cg

    print("  [3/3] Мінімальний режим…")
    r, cg = _try_generate(island_number, cluster_number, 0.030, 0.28, 0.003, MAX_ATTEMPTS)
    if r:
        print("    (мінімальні параметри)")
        return r, cg

    return None, None

def smooth_island(cx, cy, avg_r, sector, n_pts=20, spiky=0.30, min_cov=0.20):
    for _ in range(25):
        angles = np.sort(np.linspace(0, 2*np.pi, n_pts, endpoint=False)
                         + np.random.uniform(-np.pi/n_pts*0.4, np.pi/n_pts*0.4, n_pts))
        radii  = avg_r * np.clip(1 + np.random.uniform(-spiky, spiky, n_pts), 0.4, 1.6)
        x = np.append(cx + radii*np.cos(angles), cx + radii[0]*np.cos(angles[0]))
        y = np.append(cy + radii*np.sin(angles), cy + radii[0]*np.sin(angles[0]))
        try:
            tck, _ = splprep([x, y], s=0, per=True, k=3)
            xs, ys = splev(np.linspace(0, 1, 180), tck)
            isl = Polygon(zip(xs, ys))
            if not isl.is_valid: isl = isl.buffer(0)
            if isl.is_empty: continue
            clipped = safe_polygon(isl.intersection(sector))
            if not clipped.is_empty and clipped.area >= min_cov * isl.area:
                return clipped
        except Exception:
            continue
    return None

def archipelago_for_sector(sector_poly, sector_type="player"):
    inner = sector_poly.buffer(-0.010)
    if inner.is_empty or inner.area < 0.005:
        inner = sector_poly.buffer(-0.004)
    if inner.is_empty:
        inner = sector_poly
    inner = safe_polygon(inner)

    rep     = inner.representative_point()
    r_scale = 0.70 if sector_type == "cluster_satellite" else 1.0
    main_r  = np.sqrt(inner.area) * 0.44 * r_scale
    result  = []

    main = smooth_island(rep.x, rep.y, main_r, inner, n_pts=22, spiky=0.28)
    if main is not None:
        result.append(('main', main))

    if sector_type in ("player", "cluster_satellite"):
        if sector_type == "player":
            n_small  = random.randint(1, 3)
            size_min, size_max = 0.18, 0.32
        else:
            n_small  = random.randint(1, 2)
            size_min, size_max = 0.22, 0.38

        small_r  = main_r * random.uniform(size_min, size_max)
        existing = [isl for _, isl in result]
        minx, miny, maxx, maxy = inner.bounds

        for _ in range(n_small):
            for _ in range(80):
                rx = random.uniform(minx, maxx)
                ry = random.uniform(miny, maxy)
                if not inner.contains(Point(rx, ry)):
                    continue
                s = smooth_island(rx, ry, small_r * random.uniform(0.6, 1.5),
                                  inner, n_pts=14, spiky=0.35, min_cov=0.25)
                if s is None:
                    continue
                if not any(s.intersects(e) for e in existing):
                    result.append(('small', s))
                    existing.append(s)
                    break
    return result

def draw_roads(ax, island, zorder=5):
    try:
        cx, cy = island.centroid.x, island.centroid.y
        coords = list(island.exterior.coords)[:-1]
        n_coords = len(coords)
        if n_coords < 6: return

        n_roads = random.randint(3, 4)
        step = n_coords // n_roads
        offset = random.randint(0, step - 1)
        road_starts = [coords[(offset + k * step) % n_coords] for k in range(n_roads)]

        for (bx, by) in road_starts:
            seg = LineString([(bx, by), (cx, cy)]).intersection(island)
            if seg.is_empty: continue
            segs = [seg] if isinstance(seg, LineString) else list(seg.geoms)
            for s in segs:
                if s.length < 0.005: continue
                xs, ys = s.xy
                ax.plot(xs, ys, color="#2C1810", lw=5.0, alpha=0.45, solid_capstyle="round", zorder=zorder)
                ax.plot(xs, ys, color="#D7CCC8", lw=3.0, solid_capstyle="round", zorder=zorder + 0.1)
                ax.plot(xs, ys, color="#FFEB3B", lw=0.9, linestyle=(0, (6, 5)), alpha=0.85, zorder=zorder + 0.2)
    except Exception:
        pass

def draw_bridge(ax, isl_a, isl_b, zorder=6):
    try:
        pa, pb = nearest_points(isl_a.boundary, isl_b.boundary)
        x1, y1 = pa.x, pa.y
        x2, y2 = pb.x, pb.y
        length = np.hypot(x2 - x1, y2 - y1)

        if length < 0.025: return
        if isl_a.contains(Point(x2, y2)) or isl_b.contains(Point(x1, y1)): return
        mid_check = Point((x1 + x2) / 2, (y1 + y2) / 2)
        if isl_a.contains(mid_check) or isl_b.contains(mid_check): return

        ux, uy           = (x2 - x1) / length, (y2 - y1) / length
        px_perp, py_perp = -uy, ux

        ramp = min(0.003, length * 0.03)
        ax1, ay1 = x1 - ux * ramp, y1 - uy * ramp
        ax2, ay2 = x2 + ux * ramp, y2 + uy * ramp

        sag   = min(length * 0.07, 0.012)
        mid_x = (ax1 + ax2) / 2 + px_perp * sag
        mid_y = (ay1 + ay2) / 2 + py_perp * sag

        if isl_a.contains(Point(mid_x, mid_y)) or isl_b.contains(Point(mid_x, mid_y)):
            mid_x = (ax1 + ax2) / 2 - px_perp * sag
            mid_y = (ay1 + ay2) / 2 - py_perp * sag
            if isl_a.contains(Point(mid_x, mid_y)) or isl_b.contains(Point(mid_x, mid_y)):
                mid_x = (ax1 + ax2) / 2
                mid_y = (ay1 + ay2) / 2

        N      = 40
        t_vals = np.linspace(0, 1, N)
        bx = (1 - t_vals)**2 * ax1 + 2*t_vals*(1-t_vals)*mid_x + t_vals**2 * ax2
        by = (1 - t_vals)**2 * ay1 + 2*t_vals*(1-t_vals)*mid_y + t_vals**2 * ay2

        for ti in range(2, N - 2):
            if isl_a.contains(Point(bx[ti], by[ti])) or isl_b.contains(Point(bx[ti], by[ti])):
                return

        ax.plot(bx, by, color="#1A0A00", lw=13, alpha=0.28, solid_capstyle="round", zorder=zorder)
        ax.plot(bx, by, color="#5D3A1A", lw=8, solid_capstyle="round", zorder=zorder + 0.1)
        ax.plot(bx, by, color="#A1887F", lw=5.5, solid_capstyle="round", zorder=zorder + 0.2)
        ax.plot(bx, by, color="#D7CCC8", lw=1.8, linestyle="--", alpha=0.85, zorder=zorder + 0.3)

        n_cross = max(2, int(length / 0.018))
        for tc in np.linspace(0.08, 0.92, n_cross):
            dBx  = 2*(1-tc)*(mid_x - ax1) + 2*tc*(ax2 - mid_x)
            dBy  = 2*(1-tc)*(mid_y - ay1) + 2*tc*(ay2 - mid_y)
            dlen = np.hypot(dBx, dBy) + 1e-9
            nx_c, ny_c = -dBy/dlen, dBx/dlen
            bcx = (1-tc)**2*ax1 + 2*tc*(1-tc)*mid_x + tc**2*ax2
            bcy = (1-tc)**2*ay1 + 2*tc*(1-tc)*mid_y + tc**2*ay2
            hw  = 0.0065
            ax.plot([bcx - nx_c*hw, bcx + nx_c*hw], [bcy - ny_c*hw, bcy + ny_c*hw],
                    color="#4E342E", lw=2.2, solid_capstyle="round", zorder=zorder + 0.4)

        if length > 0.06:
            for tp in (0.25, 0.75):
                bpx = (1-tp)**2*ax1 + 2*tp*(1-tp)*mid_x + tp**2*ax2
                bpy = (1-tp)**2*ay1 + 2*tp*(1-tp)*mid_y + tp**2*ay2
                dBx  = 2*(1-tp)*(mid_x - ax1) + 2*tp*(ax2 - mid_x)
                dBy  = 2*(1-tp)*(mid_y - ay1) + 2*tp*(ay2 - mid_y)
                dlen = np.hypot(dBx, dBy) + 1e-9
                nx_p, ny_p = -dBy/dlen, dBx/dlen
                pil_h = max(0.015, length * 0.14)
                ax.plot([bpx, bpx + nx_p*pil_h], [bpy, bpy + ny_p*pil_h],
                        color="#3E2723", lw=4.5, solid_capstyle="round", zorder=zorder + 0.45)
                cap_hw = 0.009
                ax.plot([bpx + nx_p*pil_h - px_perp*cap_hw, bpx + nx_p*pil_h + px_perp*cap_hw],
                        [bpy + ny_p*pil_h - py_perp*cap_hw, bpy + ny_p*pil_h + py_perp*cap_hw],
                        color="#3E2723", lw=3.5, solid_capstyle="round", zorder=zorder + 0.46)

        for ex, ey in [(ax1, ay1), (ax2, ay2)]:
            ax.plot(ex, ey, "o", ms=7, color="#3E2723", markeredgecolor="#D7CCC8", markeredgewidth=1.0, zorder=zorder + 0.5)

        mx = (1-0.5)**2*ax1 + 2*0.5*(1-0.5)*mid_x + 0.5**2*ax2
        my = (1-0.5)**2*ay1 + 2*0.5*(1-0.5)*mid_y + 0.5**2*ay2
        ax.text(mx, my, "🌉", fontsize=8, ha="center", va="center", zorder=zorder + 0.6, alpha=0.90)

    except Exception:
        pass

def bridges_between_islands(ax, all_islands, max_dist=0.10, max_bridges=6):
    polys = [isl for _, isl, _, _c in all_islands]
    pairs = []
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            d = polys[i].distance(polys[j])
            if 0 < d < max_dist:
                pairs.append((d, i, j))
    pairs.sort()

    drawn      = set()
    count      = 0
    per_island = {}

    for d, i, j in pairs:
        if count >= max_bridges: break
        if (i, j) in drawn: continue
        if per_island.get(i, 0) >= 2 or per_island.get(j, 0) >= 2: continue

        try:
            pa, pb = nearest_points(polys[i].boundary, polys[j].boundary)
            bridge_len = np.hypot(pa.x - pb.x, pa.y - pb.y)

            if abs(bridge_len - d) > 0.005: continue
            if bridge_len < 0.025: continue
            if bridge_len > 0.10: continue

            bridge_line = LineString([(pa.x, pa.y), (pb.x, pb.y)])
            crosses_other = False
            for k, poly_k in enumerate(polys):
                if k == i or k == j: continue
                if bridge_line.intersects(poly_k):
                    crosses_other = True
                    break
            if crosses_other: continue
        except Exception:
            continue

        drawn.add((i, j))
        per_island[i] = per_island.get(i, 0) + 1
        per_island[j] = per_island.get(j, 0) + 1
        draw_bridge(ax, polys[i], polys[j])
        count += 1

def draw_port(ax, island, port_color="#FFD600", zorder=8):
    try:
        cx, cy = island.centroid.x, island.centroid.y
        coords = list(island.exterior.coords)[:-1]

        pier_len = 0.024
        pier_hw  = 0.0045

        best_pt    = None
        best_score = -1
        for (bx_, by_) in coords:
            ddx, ddy = bx_ - cx, by_ - cy
            dist = np.hypot(ddx, ddy)
            if dist < 1e-6: continue
            nnx, nny = ddx / dist, ddy / dist
            end_x = bx_ + pier_len * nnx
            end_y = by_ + pier_len * nny
            if not (0.015 <= end_x <= 0.985 and 0.015 <= end_y <= 0.985): continue
            if island.contains(Point(end_x, end_y)): continue
            if dist > best_score:
                best_score = dist
                best_pt    = (bx_, by_)

        if best_pt is None: return

        px, py = best_pt
        dx, dy = px - cx, py - cy
        ln = np.hypot(dx, dy) + 1e-9
        nx, ny = dx / ln, dy / ln
        tx, ty = -ny, nx

        ex, ey = px + pier_len * nx, py + pier_len * ny

        corners = [
            (px + tx * pier_hw,  py + ty * pier_hw),
            (px - tx * pier_hw,  py - ty * pier_hw),
            (ex - tx * pier_hw,  ey - ty * pier_hw),
            (ex + tx * pier_hw,  ey + ty * pier_hw),
        ]
        plank = plt.Polygon(corners, closed=True, fc="#6D4C41", ec="#3E2723", lw=0.8, alpha=0.85, zorder=zorder - 0.2)
        ax.add_patch(plank)

        for k in (-1, 0, 1):
            ox, oy = k * pier_hw * 0.6 * tx, k * pier_hw * 0.6 * ty
            ax.plot([px + ox, ex + ox], [py + oy, ey + oy], color="#4E342E", lw=2.0, solid_capstyle="round", zorder=zorder)

        for fk in (0.25, 0.55, 0.85, 1.0):
            bx = px + fk * pier_len * nx
            by = py + fk * pier_len * ny
            ax.plot([bx - tx * pier_hw * 1.5, bx + tx * pier_hw * 1.5], [by - ty * pier_hw * 1.5, by + ty * pier_hw * 1.5],
                    color="#3E2723", lw=2.5, solid_capstyle="round", zorder=zorder + 0.1)

        for fk in (0.3, 0.7):
            pilx = px + fk * pier_len * nx
            pily = py + fk * pier_len * ny
            ax.plot(pilx, pily, "v", ms=5, color="#5D4037", markeredgecolor="#212121", markeredgewidth=0.5, zorder=zorder + 0.1)

        ax.text(ex, ey, "⚓", fontsize=10, ha="center", va="center", color=port_color,
                path_effects=[pe.withStroke(linewidth=2, foreground="black")], zorder=zorder + 1)

        fx = px + tx * pier_hw * 2.5
        fy = py + ty * pier_hw * 2.5
        pole_h = 0.020
        ax.plot([fx, fx - nx * 0.002], [fy, fy + pole_h], color="#ECEFF1", lw=1.8, solid_capstyle="round", zorder=zorder + 1)
        flag_pts = [
            [fx - nx * 0.002,          fy + pole_h],
            [fx - nx * 0.002 + nx * 0.012 + ty * 0.006, fy + pole_h - 0.006],
            [fx - nx * 0.002,          fy + pole_h - 0.012],
        ]
        flag_patch = plt.Polygon(flag_pts, closed=True, fc=port_color, ec="none", alpha=0.92, zorder=zorder + 2)
        ax.add_patch(flag_patch)

    except Exception:
        pass

def draw_tree(ax, x, y, sz=0.010, color="#2E7D32", zorder=9):
    trunk_h = sz * 0.9
    ax.plot([x, x], [y - trunk_h, y], color="#5D4037", lw=2.0, solid_capstyle='round', zorder=zorder)
    tri = plt.Polygon([[x, y+sz*1.5], [x-sz, y-sz*0.2], [x+sz, y-sz*0.2]], closed=True, fc=color, ec="#1B5E20", lw=0.7, alpha=0.93, zorder=zorder)
    ax.add_patch(tri)
    ax.plot(x + sz*0.2, y + sz*0.7, '.', ms=2, color="white", alpha=0.5, zorder=zorder+0.1)

def draw_building(ax, x, y, sz=0.010, wall="#CFD8DC", roof="#E53935", zorder=9):
    rect = plt.Polygon([[x-sz, y-sz*0.8],[x+sz, y-sz*0.8],[x+sz, y+sz*0.6],[x-sz, y+sz*0.6]], closed=True, fc=wall, ec="#37474F", lw=0.9, alpha=0.95, zorder=zorder)
    ax.add_patch(rect)
    tri = plt.Polygon([[x-sz*1.15, y+sz*0.6],[x, y+sz*1.55],[x+sz*1.15, y+sz*0.6]], closed=True, fc=roof, ec="#B71C1C", lw=0.6, alpha=0.95, zorder=zorder+0.1)
    ax.add_patch(tri)
    win = plt.Polygon([[x-sz*0.4, y-sz*0.1],[x+sz*0.4, y-sz*0.1],[x+sz*0.4, y+sz*0.45],[x-sz*0.4, y+sz*0.45]], closed=True, fc="#B3E5FC", ec="#0277BD", lw=0.5, alpha=0.80, zorder=zorder+0.2)
    ax.add_patch(win)

def draw_rock(ax, x, y, sz=0.008, zorder=9):
    c = plt.Circle((x, y), sz, fc="#78909C", ec="#37474F", lw=0.8, alpha=0.90, zorder=zorder)
    ax.add_patch(c)
    shadow = plt.Circle((x+sz*0.25, y-sz*0.25), sz*0.55, fc="#546E7A", ec="none", alpha=0.60, zorder=zorder+0.1)
    ax.add_patch(shadow)
    ax.plot(x-sz*0.3, y+sz*0.35, '.', ms=2.5, color="white", alpha=0.7, zorder=zorder+0.2)

def draw_lighthouse(ax, x, y, beam_color="#FFD600", zorder=10):
    h, w = 0.030, 0.008
    shadow = plt.Polygon([[x-w*1.1, y-0.003],[x+w*1.1, y-0.003],[x+w*0.7, y+h+0.005],[x-w*0.7, y+h+0.005]], closed=True, fc="black", alpha=0.25, zorder=zorder-0.1)
    ax.add_patch(shadow)
    tower = plt.Polygon([[x-w, y],[x+w, y],[x+w*0.65, y+h],[x-w*0.65, y+h]], closed=True, fc="white", ec="#B71C1C", lw=1.2, alpha=0.97, zorder=zorder)
    ax.add_patch(tower)
    for fk in [(0.25, 0.42), (0.58, 0.75)]:
        f0, f1 = fk
        w0 = w*(1-f0*0.3); w1 = w*(1-f1*0.3)
        stripe = plt.Polygon([[x-w0, y+h*f0],[x+w0, y+h*f0],[x+w1, y+h*f1],[x-w1, y+h*f1]], closed=True, fc="#D32F2F", alpha=0.85, zorder=zorder+0.1)
        ax.add_patch(stripe)
    plat = plt.Polygon([[x-w*0.85, y+h],[x+w*0.85, y+h],[x+w*0.95, y+h+0.004],[x-w*0.95, y+h+0.004]], closed=True, fc="#424242", alpha=0.9, zorder=zorder+0.2)
    ax.add_patch(plat)
    light_y = y + h + 0.009
    glow = plt.Circle((x, light_y), 0.008, fc=beam_color, ec="#F9A825", lw=0.8, alpha=0.30, zorder=zorder+0.3)
    ax.add_patch(glow)
    lamp = plt.Circle((x, light_y), 0.005, fc=beam_color, ec="#F9A825", lw=0.8, alpha=0.97, zorder=zorder+0.4)
    ax.add_patch(lamp)
    for ang in (-35, -15, 0, 15, 35):
        a_r = np.radians(90 + ang)
        ax.plot([x, x + 0.055*np.cos(a_r)], [light_y, light_y + 0.055*np.sin(a_r)], color=beam_color, lw=1.5, alpha=0.18, zorder=zorder+0.3)

def populate_island(ax, island, rtype, is_main, zorder=9):
    try:
        minx, miny, maxx, maxy = island.bounds
        cx, cy = island.centroid.x, island.centroid.y
        placed = []

        def can_place(x, y, r):
            return (island.contains(Point(x, y)) and all(np.hypot(x-px, y-py) > r+pr for px, py, pr in placed))

        def try_place(draw_fn, r_excl, n_tries=50, **kwargs):
            for _ in range(n_tries):
                rx = random.uniform(minx+r_excl, maxx-r_excl)
                ry = random.uniform(miny+r_excl, maxy-r_excl)
                if can_place(rx, ry, r_excl):
                    draw_fn(ax, rx, ry, zorder=zorder, **kwargs)
                    placed.append((rx, ry, r_excl))
                    return True
            return False

        if is_main and rtype in ("player", "island"):
            lx = cx + (maxx-minx)*0.05
            ly = cy + (maxy-miny)*0.08
            beam = {"player": "#FF6F00", "island": "#40C4FF"}.get(rtype, "#FFD600")
            draw_lighthouse(ax, lx, ly, beam_color=beam, zorder=zorder+2)
            placed.append((lx, ly, 0.025))

        n_b = {"player": 6, "island": 4, "cluster_center": 5, "cluster_satellite": 2}
        n_buildings = n_b.get(rtype, 3) if is_main else max(1, n_b.get(rtype, 3)//2)
        roof_colors = {"player": "#B71C1C", "island": "#5D4037", "cluster_center": "#5D4037", "cluster_satellite": "#5D4037"}
        roof = roof_colors.get(rtype, "#E53935")
        for _ in range(n_buildings):
            sz = random.uniform(0.009, 0.013)
            wall = random.choice(["#CFD8DC","#ECEFF1","#E8EAF6","#FFF3E0"])
            try_place(draw_building, r_excl=0.017, n_tries=60, sz=sz, wall=wall, roof=roof)

        n_trees = random.randint(4, 9) if is_main else random.randint(1, 4)
        tree_colors = ["#388E3C","#2E7D32","#43A047","#1B5E20","#558B2F"]
        for _ in range(n_trees):
            sz = random.uniform(0.009, 0.013)
            color = random.choice(tree_colors)
            placed_tree = False
            for _ in range(60):
                angle  = random.uniform(0, 2*np.pi)
                frac   = random.uniform(0.45, 0.88)
                r_isl  = min(maxx-minx, maxy-miny) * frac * 0.48
                rx, ry = cx + r_isl*np.cos(angle), cy + r_isl*np.sin(angle)
                if can_place(rx, ry, 0.013):
                    draw_tree(ax, rx, ry, sz=sz, color=color, zorder=zorder)
                    placed.append((rx, ry, 0.013))
                    placed_tree = True
                    break
            if not placed_tree:
                try_place(draw_tree, r_excl=0.012, n_tries=30, sz=sz, color=color)

        n_rocks = random.randint(2, 4) if is_main else 1
        for _ in range(n_rocks):
            sz = random.uniform(0.006, 0.010)
            try_place(draw_rock, r_excl=0.012, n_tries=40, sz=sz)

    except Exception:
        pass

SECTOR_COLOR = {
    "player":            ("#FFCDD2", 0.30),
    "island":            ("#BBDEFB", 0.28),
    "cluster_center":    ("#DCEDC8", 0.28),
    "cluster_satellite": ("#FFF9C4", 0.26),
}
PLAYER_COLORS = ["#C62828", "#1565C0"]

NEUTRAL_ISLAND_COLOR = "#A1887F"

CLUSTER_COLORS = [
    "#7B1FA2",
    "#E65100",
    "#2E7D32",
    "#F9A825",
    "#00695C",
    "#283593",
    "#4E342E",
]
ARCHIPELAGO_COLORS = [
    "#E53935",
    "#8E24AA",
    "#1565C0",
    "#2E7D32",
    "#D81B60",
    "#00838F",
    "#EF6C00",
    "#4527A0",
    "#558B2F",
    "#6D4C41",
    "#00695C",
    "#AD1457",
    "#283593",
    "#BF360C",
]
MAIN_ISLAND_COLOR = {
    "player":            "#C62828",
    "island":            "#1565C0",
    "cluster_center":    "#2E7D32",
    "cluster_satellite": "#E65100",
}
SMALL_ISLAND_COLOR = {
    "player":            "#EF9A9A",
    "island":            "#90CAF9",
    "cluster_center":    "#A5D6A7",
    "cluster_satellite": "#FFCC80",
}
SECTOR_LABEL = {
    "player":            "Гравець",
    "island":            "Острів",
    "cluster_center":    "Центр кластеру",
    "cluster_satellite": "Кластер (супутник)",
}

def visualize(regions, cluster_groups, title_suffix=""):
    if regions is None:
        print("  Карта не згенерована.")
        return

    fig = plt.figure(figsize=(21, 16))
    fig.patch.set_facecolor("#0D2B3E")
    ax  = fig.add_axes([0.02, 0.04, 0.96, 0.90])
    ax.set_facecolor("#1A4F6E")

    overlay_artists = []
    sector_outlines = []
    main_island_highlights = [] # ДОДАНО: список для зберігання підсвітки головних островів

    voronoi_patches = []
    for r in regions:
        poly = safe_polygon(r.poly)
        fc, alpha = SECTOR_COLOR[r.type]
        x, y = poly.exterior.xy
        patch = ax.fill(x, y, fc=fc, ec="white", alpha=alpha,
                        linewidth=1.2, linestyle="--", zorder=1)
        voronoi_patches.extend(patch)

    for cluster_indices in cluster_groups:
        cr = [r for r in regions if r.point_idx in cluster_indices]
        if not cr: continue
        merged = safe_polygon(unary_union([r.poly for r in cr]))
        xm, ym = merged.exterior.xy
        l1, = ax.plot(xm, ym, color="white",   lw=4.0, alpha=0.6, zorder=2)
        l2, = ax.plot(xm, ym, color="#FFF176", lw=1.8, linestyle=(0,(8,4)), zorder=2)
        sector_outlines.extend([l1, l2])

    for r in regions:
        if r.type in ("player", "island"):
            poly = safe_polygon(r.poly)
            xm, ym = poly.exterior.xy
            color = "#FF8A80" if r.type == "player" else "#80D8FF"
            l, = ax.plot(xm, ym, color=color, lw=1.8, linestyle=(0,(8,4)), zorder=2)
            sector_outlines.append(l)

    print("  Малюємо архіпелаги…")
    all_islands = []
    region_color_map = {}

    player_color_idx = 0
    for r in regions:
        if r.type == "player":
            region_color_map[r.point_idx] = PLAYER_COLORS[player_color_idx % 2]
            player_color_idx += 1

    cluster_color_idx = 0
    for cluster_indices in cluster_groups:
        c = CLUSTER_COLORS[cluster_color_idx % len(CLUSTER_COLORS)]
        cluster_color_idx += 1
        for idx in cluster_indices:
            region_color_map[idx] = c

    for r in regions:
        if r.type == "island":
            region_color_map[r.point_idx] = NEUTRAL_ISLAND_COLOR

    for r in regions:
        poly  = safe_polygon(r.poly)
        rtype = r.type
        arch  = archipelago_for_sector(poly, sector_type=rtype)
        base_color = region_color_map.get(r.point_idx, ARCHIPELAGO_COLORS[0])
        for tag, isl in arch:
            if isl is None or isl.is_empty: continue
            isl     = safe_polygon(isl)
            is_main = (tag == 'main')
            lw      = 2.5 if is_main else 1.2
            shore = isl.buffer(0.006)
            if not shore.is_empty:
                sx, sy = safe_polygon(shore).exterior.xy
                ax.fill(sx, sy, fc="#F9A825", ec="none", alpha=0.30, zorder=3)
            x, y = isl.exterior.xy
            ax.fill(x, y, fc=base_color, ec="#111111", lw=lw,
                    alpha=0.95 if is_main else 0.55, zorder=4)
            ax.plot(x, y, color="#111111",
                    lw=4.0 if is_main else 1.5,
                    alpha=0.90 if is_main else 0.50,
                    solid_capstyle="round", solid_joinstyle="round", zorder=4)
            if is_main:
                ax.plot(x, y, color="white", lw=1.5, alpha=0.65,
                        solid_capstyle="round", solid_joinstyle="round", zorder=4)
            
            # ДОДАНО: Генеруємо підсвітку головного острова у головному секторі кластера
            # ДОДАНО: Делікатна підсвітка головного острова без жовтих контурів
            if is_main and rtype == "cluster_center":
                # Легке висвітлення самого острова
                hl_fill, = ax.fill(x, y, fc="white", alpha=0.35, zorder=11, visible=False)
                ci = isl.centroid
                # Акуратний білий текст
                hl_txt = ax.text(ci.x, ci.y + 0.035, "",
                                 ha='center', va='center', color="white", fontsize=9,
                                 weight='bold', zorder=13, visible=False,
                                 path_effects=[pe.withStroke(linewidth=2, foreground='black')])
                main_island_highlights.extend([hl_fill, hl_txt])

            all_islands.append((rtype, isl, is_main, base_color))

    island_graph = build_island_graph(all_islands, max_dist=0.14)
    stats = graph_stats(island_graph)
    print(f"  Граф островів: {stats.get('nodes')} вузлів, "
          f"{stats.get('edges')} ребер, середній ступінь {stats.get('avg_degree')}, "
          f"зв'язний: {'так' if stats.get('connected') else 'ні'}")

    print("  Малюємо дороги…")
    for rtype, isl, is_main, isl_color in all_islands:
        if is_main and isl.area > 0.0015:
            draw_roads(ax, isl, zorder=5)

    print("  Будуємо мости…")
    bridges_between_islands(ax, all_islands, max_dist=0.14, max_bridges=8)

    print("  Розставляємо об'єкти…")
    for rtype, isl, is_main, isl_color in all_islands:
        if isl.area > 0.0004:
            populate_island(ax, isl, rtype, is_main, zorder=9)

    print("  Малюємо порти…")
    map_inner = Polygon([(0.02, 0.02), (0.98, 0.02), (0.98, 0.98), (0.02, 0.98)])
    for rtype, isl, is_main, isl_color in all_islands:
        if isl.area < 0.0008: continue
        if not map_inner.contains(isl.centroid): continue
        if is_main or (isl.area > 0.0015 and random.random() < 0.50):
            draw_port(ax, isl, port_color=isl_color, zorder=8)

    player_idx = 0
    for r in regions:
        poly  = safe_polygon(r.poly)
        c     = poly.centroid
        rtype = r.type
        if rtype == "player":
            player_idx += 1
            label = f"ГРАВЕЦЬ {player_idx}\n{r.area:.3f}"
            fsize, color = 9, "#FFCDD2"
        elif rtype == "cluster_center":
            label = f"Кластер\n{r.area:.3f}"
            fsize, color = 7, "#DCEDC8"
        elif rtype == "cluster_satellite":
            label = f"↳{r.area:.3f}"
            fsize, color = 6, "#FFF9C4"
        else:
            label = f"Острів\n{r.area:.3f}"
            fsize, color = 7, "#BBDEFB"
        txt = ax.text(c.x, c.y, label, ha='center', va='center', fontsize=fsize, color=color, weight='bold',
                alpha=0.75, zorder=13, path_effects=[pe.withStroke(linewidth=1.5, foreground='black')])
        overlay_artists.append(txt)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")

    n_isl  = sum(1 for r in regions if r.type == "island")
    n_clst = sum(1 for r in regions if r.type == "cluster_center")
    ax.set_title(
        f"Ігрова карта · {n_isl} острів(и) · {n_clst} кластер(и){title_suffix}\nЗгенерована карта:",
        fontsize=13, weight="bold", color="white", pad=14
    )
    for spine in ax.spines.values():
        spine.set_edgecolor("#5C9ABF")
        spine.set_linewidth(1.5)
    ax.tick_params(colors="#7FB3CC")
    ax.set_xlabel("x", color="#7FB3CC", fontsize=10)
    ax.set_ylabel("y", color="#7FB3CC", fontsize=10)

    plt.tight_layout()
    fname = f"map_{n_isl}isl_{n_clst}cls.png"
    plt.savefig(fname, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"  Збережено: {fname}")

    def _build_export_data():
        export = {
            "islands":  n_isl, "clusters": n_clst, "regions":  [],
            "graph":    {str(k): v for k, v in island_graph.items()},
            "graph_stats": stats,
        }
        for r in regions:
            poly = safe_polygon(r.poly)
            coords = list(poly.exterior.coords)
            export["regions"].append({
                "type":   r.type, "area":   round(r.area, 6),
                "coords": [[round(x, 6), round(y, 6)] for x, y in coords],
            })
        return export

    def _export_json(event):
        import json
        data  = _build_export_data()
        fname_j = f"map_{n_isl}isl_{n_clst}cls.json"
        with open(fname_j, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  Експортовано JSON: {fname_j}")
        btn_json.label.set_text("✓ JSON збережено")
        fig.canvas.draw_idle()

    def _export_xml(event):
        import xml.etree.ElementTree as ET
        from xml.dom import minidom
        data = _build_export_data()
        root_el = ET.Element("map")
        root_el.set("islands",  str(data["islands"]))
        root_el.set("clusters", str(data["clusters"]))
        root_el.set("connected", str(data["graph_stats"].get("connected", "")))
        for r in data["regions"]:
            reg_el = ET.SubElement(root_el, "region")
            reg_el.set("type", r["type"])
            reg_el.set("area", str(r["area"]))
            coords_el = ET.SubElement(reg_el, "coords")
            for x, y in r["coords"]:
                pt = ET.SubElement(coords_el, "point")
                pt.set("x", str(x))
                pt.set("y", str(y))
        raw    = ET.tostring(root_el, encoding="unicode")
        pretty = minidom.parseString(raw).toprettyxml(indent="  ")
        fname_x = f"map_{n_isl}isl_{n_clst}cls.xml"
        with open(fname_x, "w", encoding="utf-8") as f: f.write(pretty)
        print(f"  Експортовано XML: {fname_x}")
        btn_xml.label.set_text("✓ XML збережено")
        fig.canvas.draw_idle()

    # ДОДАНО: Створюємо нову вісь для кнопки
    ax_btn_main_isl = fig.add_axes([0.84, 0.44, 0.14, 0.04])
    ax_btn_json     = fig.add_axes([0.84, 0.38, 0.14, 0.04])
    ax_btn_xml      = fig.add_axes([0.84, 0.32, 0.14, 0.04])
    ax_btn_overlay  = fig.add_axes([0.84, 0.26, 0.14, 0.04])
    ax_btn_contours = fig.add_axes([0.84, 0.20, 0.14, 0.04])
    ax_btn_voronoi  = fig.add_axes([0.84, 0.14, 0.14, 0.04])
    ax_btn_graph    = fig.add_axes([0.84, 0.08, 0.14, 0.04])

    from matplotlib.widgets import Button

    # ДОДАНО: Логіка кнопки виділення головних островів
    btn_main_isl = Button(ax_btn_main_isl, "⭐ Головні острови", color="#1A4F6E", hovercolor="#2A6F9E")
    btn_main_isl.label.set_color("white")
    btn_main_isl.label.set_fontsize(9)

    main_isl_visible = [False]
    def _toggle_main_islands(event):
        main_isl_visible[0] = not main_isl_visible[0]
        for artist in main_island_highlights:
            artist.set_visible(main_isl_visible[0])
        btn_main_isl.label.set_text(
            "✕ Сховати головні" if main_isl_visible[0] else "⭐ Головні острови"
        )
        fig.canvas.draw_idle()
    btn_main_isl.on_clicked(_toggle_main_islands)


    btn_json = Button(ax_btn_json, "⬇  Експорт JSON", color="#1A4F6E", hovercolor="#2A6F9E")
    btn_xml  = Button(ax_btn_xml,  "⬇  Експорт XML", color="#1A4F6E", hovercolor="#2A6F9E")
    btn_json.label.set_color("white")
    btn_json.label.set_fontsize(9)
    btn_xml.label.set_color("white")
    btn_xml.label.set_fontsize(9)
    btn_json.on_clicked(_export_json)
    btn_xml.on_clicked(_export_xml)

    overlay_visible = [True]

    def _toggle_overlay(event):
        overlay_visible[0] = not overlay_visible[0]
        for artist in overlay_artists:
            artist.set_visible(overlay_visible[0])
        btn_overlay.label.set_text(
            "👁  Показати підписи" if not overlay_visible[0] else "🚫  Сховати підписи"
        )
        fig.canvas.draw_idle()

    btn_overlay = Button(ax_btn_overlay, "🚫  Сховати підписи", color="#1A4F6E", hovercolor="#2A6F9E")
    btn_overlay.label.set_color("white")
    btn_overlay.label.set_fontsize(9)
    btn_overlay.on_clicked(_toggle_overlay)

    contours_visible = [True]

    def _toggle_contours(event):
        contours_visible[0] = not contours_visible[0]
        for artist in sector_outlines:
            artist.set_visible(contours_visible[0])
        btn_contours.label.set_text(
            "👁  Показати контури" if not contours_visible[0] else "〇  Сховати контури"
        )
        fig.canvas.draw_idle()

    btn_contours = Button(ax_btn_contours, "〇  Сховати контури",
                          color="#1A4F6E", hovercolor="#2A6F9E")
    btn_contours.label.set_color("white")
    btn_contours.label.set_fontsize(9)
    btn_contours.on_clicked(_toggle_contours)

    graph_visible = [False]
    graph_artists = []

    voronoi_visible = [True]

    def _toggle_voronoi(event):
        voronoi_visible[0] = not voronoi_visible[0]
        for patch in voronoi_patches:
            patch.set_visible(voronoi_visible[0])
        btn_voronoi.label.set_text(
            "👁  Показати Вороного" if not voronoi_visible[0] else "⬡  Сховати Вороного"
        )
        fig.canvas.draw_idle()

    btn_voronoi = Button(ax_btn_voronoi, "⬡  Сховати Вороного",
                         color="#1A4F6E", hovercolor="#2A6F9E")
    btn_voronoi.label.set_color("white")
    btn_voronoi.label.set_fontsize(9)
    btn_voronoi.on_clicked(_toggle_voronoi)


    def _toggle_graph(event):
        if not graph_visible[0]:
            connected = is_connected(island_graph)
            edge_color   = "#00E676" if connected else "#FF1744"
            node_fill    = "#B9F6CA" if connected else "#FF8A80"
            node_edge    = "#00C853" if connected else "#D50000"
            status_label = "зв'язний ✓" if connected else "НЕ зв'язний ✗"

            polys = [isl for _, isl, _, _c in all_islands]
            for i, neighbors in island_graph.items():
                ci = polys[i].centroid
                for j in neighbors:
                    if j <= i: continue
                    cj = polys[j].centroid
                    line, = ax.plot([ci.x, cj.x], [ci.y, cj.y], color=edge_color, lw=1.2, alpha=0.70, linestyle=(0, (4, 3)), zorder=15)
                    graph_artists.append(line)

            for i, (_, isl, _, _c) in enumerate(all_islands):
                c = isl.centroid
                circle = plt.Circle((c.x, c.y), 0.012, fc=node_fill, ec=node_edge, lw=1.0, alpha=0.90, zorder=16)
                ax.add_patch(circle)
                graph_artists.append(circle)
                txt = ax.text(c.x, c.y, str(i), ha="center", va="center", fontsize=6, color="#000000", weight="bold", zorder=17)
                graph_artists.append(txt)

            status_txt = ax.text(0.02, 0.98, f"Граф: {status_label}", ha="left", va="top", fontsize=8,
                                 color=edge_color, weight="bold", transform=ax.transAxes, zorder=18, bbox=dict(fc="black", alpha=0.45, pad=3, ec="none"))
            graph_artists.append(status_txt)

            graph_visible[0] = True
            btn_graph.label.set_text("✕  Сховати граф")
        else:
            for artist in graph_artists: artist.remove()
            graph_artists.clear()
            graph_visible[0] = False
            btn_graph.label.set_text("⬡  Показати граф")
        fig.canvas.draw_idle()

    btn_graph = Button(ax_btn_graph, "⬡  Показати граф", color="#1A3A50", hovercolor="#2A5A70")
    btn_graph.label.set_color("#FFF176")
    btn_graph.label.set_fontsize(9)
    btn_graph.on_clicked(_toggle_graph)

    plt.show()

def main():
    print("=" * 60)
    print("  ГЕНЕРАТОР ІГРОВИХ КАРТ  —  Вороний + Архіпелаги  v2.1")
    print("=" * 60)
    while True:
        try:
            islands = int(input("Кількість островів (3–5): "))
            if 3 <= islands <= 5: break
            print("  → Введіть число від 3 до 5")
        except ValueError:
            print("  → Введіть ціле число")
    while True:
        try:
            clusters = int(input("Кількість кластерів (3–5): "))
            if 3 <= clusters <= 5: break
            print("  → Введіть число від 3 до 5")
        except ValueError:
            print("  → Введіть ціле число")

    print(f"\n  Генерація: {islands} острів(и), {clusters} кластер(и)…")
    regions, cluster_groups = generate_map(islands, clusters)

    if regions:
        players   = [r for r in regions if r.type == "player"]
        others    = [r for r in regions if r.type != "player"]
        p1, p2    = players[0].area, players[1].area
        max_other = max(r.area for r in others)
        print(f"\n  ┌─ Статистика карти ─────────────────────────")
        print(f"  │ Регіонів всього:      {len(regions)}")
        print(f"  │ Гравці (площі):       {p1:.4f}  /  {p2:.4f}")
        print(f"  │ Різниця гравців:      {abs(p1-p2):.4f}  (ліміт {PLAYER_AREA_DIFF})")
        print(f"  │ Макс. інший сектор:   {max_other:.4f}")
        print(f"  └─────────────────────────────────────────────")
        print("\n  Візуалізація…")
        visualize(regions, cluster_groups)
    else:
        print("\n  ✗ Не вдалося згенерувати карту.")

if __name__ == "__main__":
    main()