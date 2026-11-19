"""Per-thread overrides of the benchmark's rule settings, used to re-judge a reference design under the rules it was
accepted under (robobuilder.courses.rules). Unset: the benchmark's rules (robobuilder.BENCHMARK_ENV)."""
import threading

LOCAL = threading.local()


def get(name: str, default=None):
    return getattr(LOCAL, name, default)
