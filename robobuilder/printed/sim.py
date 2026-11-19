"""The simulator with printed parts: registers every spec.json named in $RB_PRINTED_PARTS in this process's design
library (collision boxes, mass, centre of mass, studs / sockets / pin and cross holes), then runs
robobuilder.sim.run with the same arguments.

    RB_PRINTED_PARTS=<spec.json>[:<spec.json>] python -m robobuilder.printed.sim <robobuilder.sim.run arguments>
"""
import sys

from robobuilder.printed import register_env
from robobuilder.sim import run

if __name__ == "__main__":
    register_env()
    run.main(sys.argv[1:])
