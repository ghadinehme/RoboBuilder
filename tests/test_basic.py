"""Fast checks of a fresh install (pytest tests/test_basic.py): courses, inventory, validator, printed-part pipeline,
scoring, and one simulation. The full reproduction of the paper's verdicts is tests/selftest.py."""
import json
import os
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(REPO, "reference_results")
EXAMPLE = os.path.join(REPO, "agent_docs", "example_design.json")
PASSING = os.path.join(REF, "designs", "opus-5.5", "ramp_L1", "cross.json")


def test_courses():
    from robobuilder import courses

    assert len(courses.BENCHES) == 10
    for b in courses.BENCHES:
        for lv in courses.LEVELS:
            t = courses.task(b, lv)
            assert t["time_limit_s"] > 0 and t["description"]


def test_inventory():
    from robobuilder.core.parts import bench_parts, inventory_part_set, owned_inventory

    s = inventory_part_set()
    assert len(owned_inventory()) == 131 and sum(owned_inventory().values()) == 3055  # catalogue ids in inventory.json
    assert len(s) == 132 and sum(1 for v in s.values() if v > 0) == 131 and sum(s.values()) == 3057  # 132 owned, 131 offered
    assert s["87574c01"] == 0 and "87574c01" in bench_parts()  # the train motor is owned but withdrawn


def test_all_in_one_ban():
    """the banned kinds are exactly the parts.md sections the All-in-one documents ban"""
    import re

    from robobuilder.core.parts import bench_parts
    from robobuilder.harness import config as C

    docs = open(os.path.join(REPO, "agent_docs", "parts.md")).read()
    banned = set()
    for sec in re.split(r"^## ", docs, flags=re.M):
        if sec.startswith(("beam bricks, liftarms and frames", "Bricks and plates")):
            banned |= set(re.findall(r"^\| `([^`]+)`", sec, flags=re.M))
    by_kind = {p for p, bp in bench_parts().items() if bp.kind in C.BANNED_ALL_IN_ONE}
    assert banned and banned == by_kind


def test_validate():
    from robobuilder.validate import validate

    v = validate(EXAMPLE, "ramp", 1)
    assert "errors" in v and "review" in v
    v = validate(PASSING, "ramp", 1)
    assert v["ok"] and not v["review"]["critical"], v
    assert abs(v["stats"]["mass_g"] - 379.89) < 0.01


def test_score_reproduces_paper():
    from robobuilder import scoring

    rows = {r["entrant"]: r for r in scoring.leaderboard(scoring.load_reference())}
    want = {"opus-5.5": (100, 80, 40, 80, 8.5, 60, 22.6, 27.1, 76.4), "sonnet-5.5": (90, 40, 20, 53, 12, 30, 17.2, 11.0, 44.3),
            "gpt-6-astra": (90, 80, 30, 77, 10.5, 60, 18.1, 10.1, 57.6), "gpt-6.1-sol": (100, 60, 40, 77, 10, 50, 18.5, 9.6, 55.1)}
    for n, w in want.items():
        r = rows[n]
        got = (round(r["cross_L1"]), round(r["cross_L2"]), round(r["cross_L3"]), round(r["cross_print"]), r["sims_median"],
               round(r["all_in_one"]), round(r["light_score"], 1), round(r["fast_score"], 1), round(r["score"], 1))
        assert got == w, (n, got, w)


def test_printed_part(tmp_path):
    from robobuilder import printed

    ws = str(tmp_path / "ws")
    os.makedirs(ws)
    shutil.copy(os.path.join(REPO, "tests", "data", "example_part.py"), ws)
    ok, log = printed.build(ws, os.path.join(ws, "example_part.py"), "_custom/b1")
    assert ok, log
    stl = os.path.join(ws, "_custom/b1/part.stl")
    rep = printed.analyze_safe(stl, json.load(open(os.path.join(ws, "_custom/b1/interfaces.json"))))
    assert rep["ok"], rep["errors"]
    spec = printed.make_spec(rep, stl, json.load(open(os.path.join(ws, "_custom/b1/interfaces.json"))), str(tmp_path / "out"))
    pid = printed.register(spec)
    from robobuilder.core.parts import bench_parts

    assert pid in bench_parts() and abs(bench_parts()[pid].mass_g - rep["mass_g"]) < 1e-9


def test_simulate_one(tmp_path):
    from robobuilder import simulate

    r = simulate.run(PASSING, "ramp", 1, video=False, out_dir=str(tmp_path / "sim"))
    s = simulate.summary(r)
    assert s["passed"] and abs(s["time_s"] - 2.41) < 0.011, s
