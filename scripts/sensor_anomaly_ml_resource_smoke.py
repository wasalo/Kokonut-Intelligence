"""Run a small, synthetic sensor-model workload inside a constrained image."""

from __future__ import annotations

import json
import os
import resource
import time
from pathlib import Path


def main() -> None:
    memory_max = Path("/sys/fs/cgroup/memory.max").read_text().strip()
    cpu_max = Path("/sys/fs/cgroup/cpu.max").read_text().strip()
    if memory_max != "1073741824" or cpu_max != "200000 100000":
        raise SystemExit("smoke requires Docker limits of 1 GiB memory and 2 CPUs")

    started = time.monotonic()
    import numpy as np
    import pandas as pd
    import prophet
    import psycopg2
    import scipy
    import sklearn
    from sklearn.ensemble import IsolationForest

    values = np.random.default_rng(7).normal(size=(1024, 4))
    frame = pd.DataFrame(values, columns=["a", "b", "c", "d"])
    labels = IsolationForest(
        n_estimators=16,
        max_samples=256,
        random_state=7,
        n_jobs=1,
    ).fit_predict(frame)
    if labels.shape != (1024,) or not set(labels).issubset({-1, 1}):
        raise SystemExit("synthetic model output failed validation")

    result = {
        "status": "passed",
        "architecture": os.uname().machine,
        "memory_limit_bytes": int(memory_max),
        "cpu_quota": cpu_max,
        "samples": int(labels.size),
        "feature_count": int(frame.shape[1]),
        "outlier_count": int(np.count_nonzero(labels == -1)),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "packages": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
            "prophet": prophet.__version__,
            "psycopg2": psycopg2.__version__.split()[0],
        },
        "network_or_database_calls": False,
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
