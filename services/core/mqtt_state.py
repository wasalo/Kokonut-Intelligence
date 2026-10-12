"""Private local readiness snapshot for the optional subscriber process."""

import json
import os
import stat
import tempfile
from pathlib import Path


class MQTTState:
    def __init__(self, path: str | None):
        self.path = Path(path) if path else None
        if self.path is not None and not self.path.is_absolute():
            raise ValueError("MQTT_STATE_FILE must be an absolute path")

    def write(self, *, connected: bool, subscribed: bool):
        if self.path is None:
            return
        fd, temporary = tempfile.mkstemp(prefix=".mqtt-state-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump({"version": 1, "pid": os.getpid(),
                           "connected": connected, "subscribed": subscribed}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def check_state(path: str) -> dict:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "r") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077:
            raise RuntimeError("MQTT state must be a private file owned by this user")
        data = stream.read(4097)
    if len(data) > 4096:
        raise RuntimeError("MQTT state exceeds the expected size")
    state = json.loads(data)
    if state.get("version") != 1 or type(state.get("pid")) is not int or state["pid"] < 1:
        raise RuntimeError("Invalid MQTT process state")
    os.kill(state["pid"], 0)
    if state.get("connected") is not True or state.get("subscribed") is not True:
        raise RuntimeError("MQTT subscriber is not connected and subscribed")
    return {"ready": True, "pid": state["pid"]}


if __name__ == "__main__":
    import argparse

    from services.common.cli import print_json, run

    parser = argparse.ArgumentParser(description="Check local MQTT subscriber readiness")
    parser.add_argument("--file", required=True)
    args = parser.parse_args()
    run(lambda: print_json(check_state(args.file)))
