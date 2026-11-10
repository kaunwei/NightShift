"""Event-driven local hook commands; the live worker owns all scheduling state."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import stat
import threading
import time
import uuid

import acceptance as gate

MAX_MESSAGE = 65536


def directory(root):
    identity = str(gate.state_dir(root).resolve()).encode()
    base = Path("/tmp") / f"nightshift-hook-pipes-{os.getuid()}"
    path = base / hashlib.sha256(identity).hexdigest()[:32]
    for part in (base, path):
        part.mkdir(mode=0o700, exist_ok=True)
        info = part.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise gate.GateError("hook control pipe directory must be private and owned by the worker user")
    return path


def respond(message, path, scheduler):
    try:
        request = json.loads(message)
        reply = request["reply"]
        if not isinstance(reply, str) or not re.fullmatch(r"reply-[a-f0-9]{32}", reply):
            return
    except (ValueError, KeyError, TypeError):
        return
    try:
        if request["command"] == "register":
            response = {"registered": scheduler.register(request["spec"])}
        elif request["command"] == "retry":
            scheduler.retry(request["run_id"])
            response = {"retry_pending": request["run_id"]}
        elif request["command"] == "list":
            response = scheduler.list_runs(request.get("offset", 0))
        elif request["command"] == "cancel":
            scheduler.cancel(request["run_id"])
            response = {"cancelled": request["run_id"]}
        else:
            raise gate.GateError("unknown hook control command")
    except (OSError, ValueError, KeyError, TypeError) as error:
        response = {"error": str(error)}
    try:
        fd = os.open(path / reply, os.O_WRONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        try:
            if stat.S_ISFIFO(os.fstat(fd).st_mode):
                os.write(fd, json.dumps(response).encode() + b"\n")
        finally:
            os.close(fd)
    except OSError:
        pass


@contextmanager
def serve(root, scheduler):
    path = directory(root)
    endpoint = path / "request"
    # The workspace lock prevents a second worker from replacing a live pipe.
    endpoint.unlink(missing_ok=True)
    os.mkfifo(endpoint, 0o600)
    control = os.open(endpoint, os.O_RDWR | os.O_NONBLOCK)
    stop_read, stop_write = os.pipe()

    def listen():
        buffer = bytearray()
        while True:
            readable, _, _ = select.select([control, stop_read], [], [])
            if stop_read in readable:
                return
            buffer.extend(os.read(control, 8192))
            while b"\n" in buffer:
                line, _, rest = buffer.partition(b"\n")
                buffer = bytearray(rest)
                if len(line) <= MAX_MESSAGE:
                    respond(line, path, scheduler)
            if len(buffer) > MAX_MESSAGE:
                buffer.clear()

    thread = threading.Thread(target=listen, daemon=True)
    thread.start()
    try:
        yield
    finally:
        os.write(stop_write, b"x")
        thread.join()
        for fd in (stop_read, stop_write, control):
            os.close(fd)
        endpoint.unlink(missing_ok=True)


def request(root, value):
    path = directory(root)
    reply = path / ("reply-" + uuid.uuid4().hex)
    # A leading delimiter discards a partial frame left by a killed writer.
    payload = b"\n" + json.dumps({**value, "reply": reply.name}).encode() + b"\n"
    if len(payload) > MAX_MESSAGE:
        raise gate.GateError("hook control command is too large")
    os.mkfifo(reply, 0o600)
    reader = os.open(reply, os.O_RDWR | os.O_NONBLOCK)
    deadline = time.monotonic() + 4

    def remaining():
        return max(0, deadline - time.monotonic())

    try:
        # Serialize writers so large commands can span multiple pipe writes.
        with (path / "send.lock").open("a") as lock:
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if not remaining():
                        raise gate.GateError("hook control channel is busy")
                    time.sleep(min(.01, remaining()))
            try:
                writer = os.open(path / "request", os.O_WRONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
            except OSError as error:
                raise gate.GateError("no live worker for this runner; start the worker before registering a hook") from error
            try:
                pending = memoryview(payload)
                while pending:
                    if not select.select([], [writer], [], remaining())[1]:
                        raise gate.GateError("hook control command timed out")
                    try:
                        pending = pending[os.write(writer, pending):]
                    except BlockingIOError:
                        continue
            finally:
                os.close(writer)
        data = bytearray()
        while b"\n" not in data:
            if not select.select([reader], [], [], remaining())[0]:
                raise gate.GateError("worker did not acknowledge the hook command")
            data.extend(os.read(reader, 8192))
        response = json.loads(data)
        if "error" in response:
            raise gate.GateError(response["error"])
        return response
    finally:
        os.close(reader)
        reply.unlink(missing_ok=True)
