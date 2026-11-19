"""The custom 3D-printed part (the Cross+Print and All-in-one tasks).

Pipeline (`brick-bench part <cad_script.py>`):
  1. build: the agent's CadQuery script runs in a bubblewrap sandbox (no network, only its workspace writable) with the
     agents' design library (robobuilder/agent_lib, bricks/printed.py); its part() returns a PrintedPart (or a solid +
     INTERFACES). Out: part.stl + interfaces.json.
  2. check (trimesh, outside the sandbox; the STL is only read as data): watertight single solid, fits the printer's
     build volume (MAX_MM per side), minimum wall 1.2 mm (ray thickness from area-uniform surface samples), an overhang
     note (area facing down steeper than 45 deg in the best of the 6 axis-aligned print orientations), every declared
     interface present in the solid (studs modelled on their face, sockets / holes empty with material around them),
     the 8 mm stud grid, stud-face heights a multiple of 3.2 mm.
  3. physical model: mass = PLA 1.24 g/cm3 x (solid shell of 1.2 mm + 35 % infill of the rest); centre of mass of the
     solid; collision shape = the solid voxelised and merged into at most ~80 axis-aligned boxes on the brick grid (the
     simulator's and the validator's `Boxes` shape; studs left out, as for every catalogue part); a visual mesh.
  4. register: a catalogue entry (`BenchPart`, kind "connector", COPIES owned) inserted at runtime into
     robobuilder.core.parts.bench_parts() / inventory_part_set(), in the harness process (validate, review) and, through
     robobuilder.printed.sim, in the simulator process. Printed studs and sockets hold like brick studs; pins and
     axles in its holes behave as in a beam; the part itself is rigid.
The part id is p3d_<hash of the STL and interfaces>: a revised part is a new id, so every design keeps its geometry.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys


ENV_VAR = "RB_PRINTED_PARTS"  # os.pathsep-separated spec.json paths registered in the simulator process
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # robobuilder/
AGENT_LIB = os.path.join(PKG, "agent_lib")
MAX_MM = 256.0  # Cross+Print: the printer's build volume, 256 x 256 x 256 mm (All-in-one: 250 mm)
COPIES = 4  # Cross+Print: one part type, up to 4 copies (All-in-one: any number of types, 8 copies each)
MIN_WALL_MM = 1.2
PLA_DENSITY_G_CM3 = 1.24
PLA_INFILL = 0.35  # 35 % infill ...
PLA_SHELL_MM = 1.2  # ... inside a solid 1.2 mm shell (3 perimeters, top / bottom skins)
MAX_BOXES = 80
STUD_R, STUD_H = 2.4, 1.7
SOCKET_DEPTH = 2.0
HOLE_R = 2.45


# --------------------------------------------------------------------------------------------------------------------
# 1. build
# --------------------------------------------------------------------------------------------------------------------
RUNNER = r'''
import os, runpy, sys
sys.path.insert(0, os.getcwd())
from bricks.printed import export
ns = runpy.run_path(sys.argv[1], run_name="cad_part")
fn = ns.get("part")
if not callable(fn):
    raise SystemExit("the script must define part() returning a PrintedPart (bricks.printed) or (solid, INTERFACES)")
export(fn(), ns.get("INTERFACES"), sys.argv[2])
print("CAD_OK")
'''


def build(ws: str, script: str, out_rel: str, timeout_s: int = 300) -> tuple[bool, str]:
    """run the agent's CAD script (workspace path ``script``) sandboxed; writes ws/out_rel/part.stl, interfaces.json"""
    os.makedirs(os.path.join(ws, out_rel), exist_ok=True)
    runner = os.path.join(ws, "_custom", "_runner.py")
    os.makedirs(os.path.dirname(runner), exist_ok=True)
    open(runner, "w").write(RUNNER)
    rel = os.path.relpath(script, ws)
    py = sys.executable
    # the workspace at its real path, the only writable place; relative paths in the script work
    env = {"PYTHONPATH": f"{AGENT_LIB}:{os.path.dirname(PKG)}:{ws}", "HOME": ws, "PATH": "/usr/bin:/bin",
           "MPLBACKEND": "Agg", "PYTHONDONTWRITEBYTECODE": "1"}
    base = [py, "-u", runner, os.path.join(ws, rel), os.path.join(ws, out_rel)]
    if shutil.which("bwrap") and os.environ.get("RB_NO_SANDBOX") != "1":
        # as narrow as the agents' own sandbox: system dirs, the Python install, the design library, the workspace
        from .. import sandbox  # noqa: PLC0415

        cmd = (["bwrap", "--die-with-parent", "--unshare-net", "--unshare-pid", "--new-session", "--proc", "/proc",
                "--dev", "/dev", "--tmpfs", "/tmp"] + sandbox.python_binds()
               + ["--bind", ws, ws, "--chdir", ws, "--clearenv"]
               + sum((["--setenv", k, v] for k, v in env.items()), []) + base)
        e = None
    else:  # (no bubblewrap: only on a throwaway machine)
        cmd, e = base, env
    try:
        p = subprocess.run(cmd, cwd=ws, env=e, capture_output=True, text=True, timeout=timeout_s)
        out = (p.stdout or "") + (p.stderr or "")
        ok = p.returncode == 0 and "CAD_OK" in (p.stdout or "")
    except subprocess.TimeoutExpired:
        return False, f"the CAD script timed out after {timeout_s} s"
    ok = ok and os.path.exists(os.path.join(ws, out_rel, "part.stl"))
    return ok, out[-4000:]


# --------------------------------------------------------------------------------------------------------------------
# 2-3. checks and the physical model
# --------------------------------------------------------------------------------------------------------------------
def _ring(c, axis, r, ts, n=8):
    import numpy as np  # noqa: PLC0415

    a = np.zeros(3)
    a["xyz".index(axis)] = 1.0
    u = np.array([1.0, 0, 0]) if axis != "x" else np.array([0, 1.0, 0])
    u = u - a * (u @ a)
    u /= np.linalg.norm(u)
    v = np.cross(a, u)
    c = np.asarray(c, float)
    return np.array([c + t * a + r * (np.cos(th) * u + np.sin(th) * v)
                     for t in ts for th in np.linspace(0, 2 * np.pi, n, endpoint=False)])


def _line(c, axis, ts):
    import numpy as np  # noqa: PLC0415

    a = np.zeros(3)
    a["xyz".index(axis)] = 1.0
    return np.array([np.asarray(c, float) + t * a for t in ts])


def _on_grid(xy) -> bool:
    if not xy:
        return True
    x0, y0 = xy[0]
    return all(abs((x - x0) / 8.0 - round((x - x0) / 8.0)) < 0.01 and abs((y - y0) / 8.0 - round((y - y0) / 8.0)) < 0.01
               for x, y in xy)


def check_interfaces(mesh, itf: dict, errors: list, warnings: list) -> dict:
    """every declared interface is really in the solid; -> the normalised interfaces"""
    import numpy as np  # noqa: PLC0415

    inside = lambda P: mesh.contains(np.atleast_2d(np.asarray(P, float)))  # noqa: E731
    out = {"studs_top": None, "studs_bottom": None, "pin_holes": [], "axle_holes": []}
    for key, want in (("studs_top", "top"), ("studs_bottom", "bottom")):
        f = itf.get(key)
        if not f:
            continue
        try:
            z = float(f["z"])
            xy = [(float(x), float(y)) for x, y in f["xy"]]
        except Exception:  # noqa: BLE001
            errors.append(f"{key}: give {{'z': height, 'xy': [[x, y], ...]}}")
            continue
        if not xy:
            continue
        if len(xy) > 256:
            errors.append(f"{key}: at most 256 studs")
            continue
        if not _on_grid(xy):
            errors.append(f"{key}: the positions are not on one 8 mm stud grid")
        bad = []
        for x, y in xy:
            if want == "top":
                ok = inside([x, y, z - 0.6])[0] and inside([x, y, z + 0.85])[0]
            else:
                ring = _ring((x, y, z + 1.0), "z", 3.3, [0.0])
                ok = (not inside([x, y, z + 0.8])[0]) and inside(ring).mean() >= 0.75
            if not ok:
                bad.append((round(x, 2), round(y, 2)))
        if bad:
            errors.append(f"{key}: {len(bad)} of {len(xy)} positions are not in the solid as declared "
                          f"({'a stud needs the face below it and the stud modelled on it' if want == 'top' else 'a socket needs an empty 4.9 mm hole 2 mm deep with material around it'}; "
                          f"use bricks.printed): {bad[:6]}")
        out[key] = {"z": z, "xy": xy}
    if out["studs_top"] and out["studs_bottom"]:
        h = out["studs_top"]["z"] - out["studs_bottom"]["z"]
        if abs(h / 3.2 - round(h / 3.2)) > 0.02 or h <= 0:
            errors.append(f"stud faces: the top face is {h:.2f} mm above the bottom face; it must be a multiple of the "
                          f"plate height 3.2 mm (a brick is 9.6 mm)")
    for key in ("pin_holes", "axle_holes"):
        holes = itf.get(key) or []
        if len(holes) > 64:
            errors.append(f"{key}: at most 64 hole segments")
            continue
        for h in holes:
            try:
                x, y, z, a = float(h[0]), float(h[1]), float(h[2]), str(h[3])
                assert a in ("x", "y", "z")
            except Exception:  # noqa: BLE001
                errors.append(f"{key}: each hole is [x, y, z, 'x'|'y'|'z'] (the middle of an 8 mm hole segment)")
                break
            empty = not inside(_line((x, y, z), a, (-3.5, -2.0, 0.0, 2.0, 3.5))).any()
            wall = inside(_ring((x, y, z), a, HOLE_R + 0.85, (-2.0, 0.0, 2.0))).mean()
            if not empty:
                errors.append(f"{key} at ({x:g}, {y:g}, {z:g}) along {a}: the hole is not open along its 8 mm")
            elif wall < 0.75:
                errors.append(f"{key} at ({x:g}, {y:g}, {z:g}) along {a}: not enough material around the hole "
                              f"({wall:.0%} of the ring 0.85 mm outside it is solid; needs a closed wall)")
            out[key].append((x, y, z, a))
    if not (out["studs_top"] or out["studs_bottom"] or out["pin_holes"] or out["axle_holes"]):
        errors.append("no interfaces: the part must connect to the bricks (studs, sockets, pin holes or axle holes)")
    return out


def wall_thickness(mesh, n: int = 4000):
    """area-uniform surface samples -> local wall thickness along the inward normal [mm] (inf: not a wall)"""
    import numpy as np  # noqa: PLC0415

    pts, fi = mesh.sample(n, return_index=True)
    nrm = mesh.face_normals[fi]
    org = pts - nrm * 1e-3
    loc, idx, tri = mesh.ray.intersects_location(org, -nrm, multiple_hits=False)
    th = np.full(len(pts), np.inf)
    th[idx] = np.linalg.norm(loc - org[idx], axis=1)
    # a wall is two faces within ~20 deg of parallel; the tapering edge of a wedge or chamfer is not a thin wall
    opp = np.zeros(len(pts), bool)
    opp[idx] = np.einsum("ij,ij->i", nrm[idx], mesh.face_normals[tri]) < -0.94
    th[~opp] = np.inf
    return pts, th


def overhang(mesh) -> dict:
    """downward-facing area steeper than 45 deg (off the bed) in each axis-aligned print orientation"""
    import numpy as np  # noqa: PLC0415

    best = None
    for name, up in (("+z up", (0, 0, 1)), ("-z up", (0, 0, -1)), ("+x up", (1, 0, 0)), ("-x up", (-1, 0, 0)),
                     ("+y up", (0, 1, 0)), ("-y up", (0, -1, 0))):
        u = np.array(up, float)
        h = mesh.triangles_center @ u
        nz = mesh.face_normals @ u
        bed = h < h.min() + 0.3
        a = float(mesh.area_faces[(nz < -0.7071) & ~bed].sum())
        if best is None or a < best[1]:
            best = (name, a)
        if name == "+z up":
            as_modelled = a
    return {"as_modelled_mm2": round(as_modelled, 1), "best_orientation": best[0], "best_mm2": round(best[1], 1)}


def boxes(mesh, studs_top, studs_bottom=None, max_boxes: int = MAX_BOXES):
    """voxelise the solid (studs excluded) and merge the voxels into axis-aligned boxes: [(lo, hi), ...], pitch.
    The grid is aligned on the brick system: x / y voxel faces on multiples of the pitch from the part origin (pitches
    1, 2, 4, 8 mm divide the 8 mm stud grid), z faces on the stud face (pitches 0.8, 1.6, 3.2 mm: plate heights), so
    the faces a brick sits on are exact. The coarsest pitch is used only when the boxes would exceed ``max_boxes``."""
    import numpy as np  # noqa: PLC0415

    lo, hi = mesh.bounds
    ext = hi - lo
    z_ref = studs_top["z"] if studs_top else (studs_bottom["z"] if studs_bottom else 0.0)
    need = max(1.0, float(ext.max()) / 48.0)
    ladder = [(pxy, pz) for pxy, pz in ((1.0, 0.8), (2.0, 1.6), (4.0, 3.2), (8.0, 3.2), (8.0, 6.4)) if pxy >= need * 0.99]
    ladder = ladder or [(8.0, 6.4)]
    for pxy, pz in ladder:
        pitch = np.array([pxy, pxy, pz])
        ref = np.array([0.0, 0.0, z_ref])
        g0 = ref + np.floor((lo - ref) / pitch) * pitch  # grid start (aligned), voxel k spans g0 + k p .. g0 + (k+1) p
        n = np.maximum(1, np.ceil((hi - g0) / pitch - 1e-9).astype(int))
        axes = [g0[i] + (np.arange(n[i]) + 0.5) * pitch[i] for i in range(3)]
        G = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
        filled = _fill(mesh, axes)
        if studs_top:  # studs are not part of a catalogue part's collision shape
            z0 = studs_top["z"]
            above = (G[:, 2] > z0).reshape(tuple(n))
            near = np.zeros(len(G), bool)
            for x, y in studs_top["xy"]:
                near |= (G[:, 0] - x) ** 2 + (G[:, 1] - y) ** 2 <= (STUD_R + 0.5 * pxy) ** 2
            filled &= ~(above & near.reshape(tuple(n)) & (G[:, 2] < z0 + STUD_H + pz).reshape(tuple(n)))
        out = _merge(filled)
        if len(out) <= max_boxes:
            break
    res = [((g0 + np.array(a) * pitch).round(3).tolist(), (g0 + np.array(b) * pitch).round(3).tolist())
           for a, b in out]
    return res, float(pitch[0])


def _fill(mesh, axes):
    """inside / outside of the voxel centres axes[0] x axes[1] x axes[2], by one vertical ray per (x, y) column and
    the parity of its crossings below each centre (mesh.contains on every centre is minutes and tens of GB on a large part)"""
    import numpy as np  # noqa: PLC0415

    X, Y = np.meshgrid(axes[0], axes[1], indexing="ij")
    z0 = float(mesh.bounds[0][2]) - 1.0
    # a hair off the centre: a ray lying in a vertical face would graze it and miscount the crossings
    O = np.stack([X.ravel() + 1.3e-4, Y.ravel() + 0.7e-4, np.full(X.size, z0)], axis=1)
    D = np.tile([0.0, 0.0, 1.0], (len(O), 1))
    loc, ray, _ = mesh.ray.intersects_location(O, D, multiple_hits=True)
    zc = np.asarray(axes[2])
    out = np.zeros((X.size, len(zc)), bool)
    order = np.argsort(ray, kind="stable")
    ray, hz = ray[order], loc[order, 2]
    cuts = np.searchsorted(ray, np.arange(X.size + 1))
    for r in range(X.size):
        z = np.sort(hz[cuts[r]:cuts[r + 1]])
        if len(z) == 0:
            continue
        z = z[np.concatenate([[True], np.diff(z) > 1e-6])]  # a ray through an edge hits both faces at one point
        out[r] = (np.searchsorted(z, zc) % 2) == 1
    return out.reshape(len(axes[0]), len(axes[1]), len(zc))


def _merge(F):
    """greedy merge of a boolean voxel grid into boxes [(i0, j0, k0), (i1, j1, k1)) (exclusive ends)"""
    F = F.copy()
    nx, ny, nz = F.shape
    out = []
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                if not F[i, j, k]:
                    continue
                k1 = k
                while k1 < nz and F[i, j, k1]:
                    k1 += 1
                j1 = j + 1
                while j1 < ny and F[i, j1, k:k1].all():
                    j1 += 1
                i1 = i + 1
                while i1 < nx and F[i1, j:j1, k:k1].all():
                    i1 += 1
                F[i:i1, j:j1, k:k1] = False
                out.append(((i, j, k), (i1, j1, k1)))
    return out


def analyze(stl: str, itf: dict, max_mm: float = MAX_MM) -> dict:
    """printability, interfaces and the physical model of one printed part -> report (errors block registration)"""
    import numpy as np  # noqa: PLC0415
    import trimesh  # noqa: PLC0415

    errors, warnings, notes = [], [], []
    mesh = trimesh.load(stl, force="mesh")
    if mesh.is_empty or len(mesh.faces) == 0:
        return {"ok": False, "errors": ["the STL is empty"], "warnings": [], "notes": []}
    if len(mesh.split(only_watertight=False)) > 1:
        errors.append("the part is not one piece: it has several separate bodies")
    if not mesh.is_watertight or mesh.volume <= 0:
        errors.append("the solid is not closed (not watertight): it cannot be printed or weighed")
        return {"ok": False, "errors": errors, "warnings": warnings, "notes": notes}
    ext = mesh.bounds[1] - mesh.bounds[0]
    size = [round(float(v), 2) for v in ext]
    if ext.max() > max_mm + 1e-6:
        errors.append(f"size {size} mm: the part must fit the printer's build volume ({max_mm:.0f} mm per side)")
    pts, th = wall_thickness(mesh)
    fin = th[np.isfinite(th)]
    thin = th < MIN_WALL_MM - 0.05
    frac = float(thin.mean())
    min_wall = round(float(np.percentile(fin, 1)), 2) if len(fin) else None
    if frac > 0.01:
        where = np.round(pts[thin][:5], 1).tolist()
        errors.append(f"walls thinner than {MIN_WALL_MM} mm over {frac:.1%} of the surface (e.g. near "
                      f"{where}); thicken them")
    elif frac > 0:
        warnings.append(f"a few spots thinner than {MIN_WALL_MM} mm ({frac:.2%} of the surface)")
    oh = overhang(mesh)
    if oh["best_mm2"] > 50:
        notes.append(f"overhangs: {oh['best_mm2']:.0f} mm2 face down steeper than 45 deg even printed {oh['best_orientation']}: "
                     f"those need supports (as modelled, {oh['as_modelled_mm2']:.0f} mm2)")
    else:
        notes.append(f"prints without supports {oh['best_orientation']} (as modelled: {oh['as_modelled_mm2']:.0f} mm2 of "
                     "overhang steeper than 45 deg)")
    itf_n = check_interfaces(mesh, itf, errors, warnings)
    V, A = float(mesh.volume), float(mesh.area)
    shell = min(V, A * PLA_SHELL_MM)
    mass = PLA_DENSITY_G_CM3 * 1e-3 * (shell + PLA_INFILL * (V - shell))
    com = [round(float(v), 3) for v in mesh.center_mass]
    rep = {"ok": not errors, "errors": errors, "warnings": warnings, "notes": notes, "size_mm": size,
           "volume_cm3": round(V / 1000, 3), "mass_g": round(mass, 2), "com_mm": com, "min_wall_mm": min_wall,
           "overhang": oh, "interfaces": itf_n,
           "mass_model": f"PLA {PLA_DENSITY_G_CM3} g/cm3, {PLA_SHELL_MM} mm solid shell + {PLA_INFILL:.0%} infill"}
    if not errors:
        bx, pitch = boxes(mesh, itf_n["studs_top"], itf_n["studs_bottom"])
        vb = sum((h[0] - l[0]) * (h[1] - l[1]) * (h[2] - l[2]) for l, h in bx)
        rep["collision"] = {"boxes": len(bx), "voxel_mm": round(pitch, 2), "volume_ratio": round(vb / V, 3)}
        rep["_boxes"] = bx
        rep["_mesh"] = mesh
    return rep


_SUBPROC = r"""
import json, pickle, resource, sys
resource.setrlimit(resource.RLIMIT_AS, (int(float(sys.argv[4]) * 2 ** 30),) * 2)
from robobuilder import printed as P
try:
    rep = P.analyze(sys.argv[1], json.load(open(sys.argv[2])), float(sys.argv[5]))
    rep.pop("_mesh", None)
    out = ("ok", rep)
except MemoryError:
    out = ("err", "the part check ran out of memory (the mesh is too fine or too large); simplify the part")
except Exception as e:  # noqa: BLE001
    out = ("err", f"the part check failed: {type(e).__name__}: {str(e)[:300]}")
pickle.dump(out, open(sys.argv[3], "wb"))
"""


def analyze_safe(stl: str, itf: dict, max_mm: float = MAX_MM, mem_gb: float = 16.0, timeout_s: float = 900.0) -> dict:
    """analyze() in a fresh Python process with a memory cap and a time limit, so a pathological mesh cannot take the
    harness down"""
    import pickle  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    import trimesh  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as td:
        itf_p, out_p = os.path.join(td, "itf.json"), os.path.join(td, "out.pkl")
        json.dump(itf, open(itf_p, "w"))
        env = dict(os.environ, PYTHONPATH=os.path.dirname(PKG) + os.pathsep + os.environ.get("PYTHONPATH", ""))
        try:
            subprocess.run([sys.executable, "-c", _SUBPROC, stl, itf_p, out_p, str(mem_gb), str(max_mm)],
                           capture_output=True, timeout=timeout_s, stdin=subprocess.DEVNULL, env=env)
        except subprocess.TimeoutExpired:
            return {"ok": False, "errors": [f"the part check took over {timeout_s:.0f} s; simplify the part"],
                    "warnings": [], "notes": []}
        if not os.path.exists(out_p):
            return {"ok": False, "errors": ["the part check crashed (out of memory?); simplify the part"],
                    "warnings": [], "notes": []}
        kind, rep = pickle.load(open(out_p, "rb"))
    if kind != "ok":
        return {"ok": False, "errors": [rep], "warnings": [], "notes": []}
    if rep.get("ok"):
        rep["_mesh"] = trimesh.load(stl, force="mesh")
    return rep


# --------------------------------------------------------------------------------------------------------------------
# 4. the catalogue entry
# --------------------------------------------------------------------------------------------------------------------
def part_id(stl: str, itf: dict) -> str:
    h = hashlib.sha256(open(stl, "rb").read() + json.dumps(itf, sort_keys=True).encode()).hexdigest()
    return f"p3d_{h[:10]}"


def make_spec(rep: dict, stl: str, itf: dict, out_dir: str, script: str | None = None, copies: int = COPIES) -> str:
    """write <out_dir>/<pid>/: the STL for printing, the CAD script, spec.json and the visual mesh <pid>.npz -> spec"""
    import numpy as np  # noqa: PLC0415

    pid = part_id(stl, itf)
    d = os.path.join(out_dir, pid)
    os.makedirs(d, exist_ok=True)
    shutil.copy(stl, os.path.join(d, f"{pid}.stl"))
    if script and os.path.exists(script):
        shutil.copy(script, os.path.join(d, "cad_script.py"))
    mesh = rep["_mesh"]
    np.savez_compressed(os.path.join(d, f"{pid}.npz"), p=np.asarray(mesh.vertices, np.float32),
                        i=np.asarray(mesh.faces, np.uint32), c=np.array("#e8a33d"))
    I = rep["interfaces"]
    spec = {"part_id": pid, "title": f"printed part: {itf.get('title') or itf.get('name') or pid}",
            "kind": "connector", "mass_g": rep["mass_g"], "com_mm": rep["com_mm"], "size_mm": rep["size_mm"],
            "boxes": rep["_boxes"],
            "studs_top": I["studs_top"]["xy"] if I["studs_top"] else [],
            "top_z": I["studs_top"]["z"] if I["studs_top"] else 0.0,
            "studs_bottom": I["studs_bottom"]["xy"] if I["studs_bottom"] else [],
            "bottom_z": I["studs_bottom"]["z"] if I["studs_bottom"] else 0.0,
            "pin_holes": [list(h) for h in I["pin_holes"]], "axle_holes": [list(h) for h in I["axle_holes"]],
            "copies": int(copies), "interfaces": itf, "report": {k: v for k, v in rep.items() if not k.startswith("_")}}
    p = os.path.join(d, "spec.json")
    json.dump(spec, open(p, "w"), indent=1)
    return p


def register(spec: dict | str) -> str:
    """insert the printed part into the design library's catalogue and the inventory part set (this process)"""
    if isinstance(spec, str):
        spec = json.load(open(spec))
    from robobuilder.core.parts import BenchPart, Boxes, bench_parts, inventory_part_set  # noqa: PLC0415

    bx = tuple((tuple(float(v) for v in lo), tuple(float(v) for v in hi)) for lo, hi in spec["boxes"])
    lo = tuple(min(b[0][i] for b in bx) for i in range(3))
    hi = tuple(max(b[1][i] for b in bx) for i in range(3))
    bp = BenchPart(
        part_id=spec["part_id"], kind="connector", title=spec["title"], mass_g=float(spec["mass_g"]),
        com_mm=tuple(float(v) for v in spec["com_mm"]), shape=Boxes(lo, hi, bx),
        studs_top=tuple(tuple(float(v) for v in p) for p in spec["studs_top"]), top_z=float(spec["top_z"]),
        studs_bottom=tuple(tuple(float(v) for v in p) for p in spec["studs_bottom"]),
        bottom_z=float(spec["bottom_z"]),
        pin_holes=tuple((float(x), float(y), float(z), a) for x, y, z, a in spec["pin_holes"]),
        axle_holes=tuple((float(x), float(y), float(z), a) for x, y, z, a in spec["axle_holes"]),
        inventory=True,
        notes=f"custom 3D-printed PLA part ({spec.get('size_mm')} mm, {spec['mass_g']} g); printed studs hold like "
              f"brick studs")
    bench_parts()[spec["part_id"]] = bp
    inventory_part_set()[spec["part_id"]] = int(spec.get("copies", COPIES))
    return spec["part_id"]


def register_env() -> list[str]:
    """register every spec named in $RB_PRINTED_PARTS (the simulator wrapper)"""
    return [register(p) for p in os.environ.get(ENV_VAR, "").split(os.pathsep) if p]


def geom_dirs(specs) -> list[str]:
    """the folders of the printed parts' visual meshes (<pid>.npz next to each spec.json)"""
    return sorted({os.path.dirname(os.path.abspath(p)) for p in specs})


def ids_in(design_path: str) -> list[str]:
    try:
        d = json.load(open(design_path))
    except Exception:  # noqa: BLE001
        return []
    return sorted({str(p.get("part", "")) for p in d.get("parts", []) if str(p.get("part", "")).startswith("p3d_")})
