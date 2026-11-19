"""Export a printed part for a real print: rerun its CadQuery script with the interface sizes tuned for an FDM printer
(studs 5.0 mm, pin holes 5.0 mm, cross holes 5.0 x 2.0 mm, stud sockets 5.1 mm; RB_PRINT_FIT=real). The simulated
part is unchanged; only the clearances of the printed interfaces differ.

    python scripts/export_printed_part.py reference_results/printed_parts/<id>/cad_script.py out_dir/
Print the stud fit coupon (real_world/course_parts.zip: fit_coupons/stud_fit_coupon.stl) first and adjust the sizes in
robobuilder/agent_lib/bricks/printed.py if your printer needs other clearances."""
import os
import runpy
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    os.environ["RB_PRINT_FIT"] = "real"
    sys.path.insert(0, os.path.join(REPO, "robobuilder", "agent_lib"))
    script, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    os.chdir(os.path.dirname(script))  # scripts may read files next to them
    sys.path.insert(0, os.path.dirname(script))
    from bricks.printed import export  # noqa: E402

    ns = runpy.run_path(script, run_name="cad_part")
    r = export(ns["part"](), ns.get("INTERFACES"), out)
    os.replace(r["stl"], os.path.join(out, "part_print.stl"))
    print("wrote", os.path.join(out, "part_print.stl"))
