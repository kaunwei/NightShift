"""POSIX VERIFY supervision with durable live logs and a bounded memory tail."""
from datetime import datetime, timezone
import os
import errno
from pathlib import Path
import select
import signal
import subprocess
import time
import uuid

import acceptance


def run(command, work_dir, port, timeout, output_type, *, cancel_fd=None, environment=None, directory=None):
    started = time.monotonic()
    try:
        directory = Path(directory) if directory is not None else acceptance.state_dir(work_dir) / "verify"
    except OSError as error:
        if os.environ.get("NIGHTSHIFT_STATE_DIR") or error.errno not in (errno.EACCES, errno.EROFS, errno.EPERM):
            raise
        # Ad-hoc commands may have a read-only .git while their workspace is
        # writable. Keep generated logs within the allowed workspace instead.
        directory = Path(work_dir).resolve() / ".scratch/nightshift-verify"
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / (uuid.uuid4().hex + ".log")
    metadata_path = log_path.with_suffix(".json")
    environment = {**(os.environ if environment is None else environment), "PORT": str(port), "TEST_PORT": str(port)}
    tail = bytearray()
    total = 0
    scan_tail = b""
    empty_test_run = False
    invalid_repro = False
    eof = False
    timed_out = False
    cancelled = False
    with log_path.open("xb", buffering=0) as log:
        process = subprocess.Popen(["bash", "-c", command], cwd=work_dir, env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        record = {"pid": process.pid, "command": command, "log_path": str(log_path),
                  "started_at": datetime.now(timezone.utc).isoformat(), "budget_seconds": timeout,
                  "status": "running", "output_bytes": 0}
        acceptance.save(metadata_path, record)
        os.set_blocking(process.stdout.fileno(), False)

        def drain(wait):
            nonlocal eof, total, scan_tail, empty_test_run, invalid_repro, cancelled
            if cancel_fd is not None and select.select([cancel_fd], [], [], 0)[0]:
                cancelled = not os.read(cancel_fd, 1)
            if eof:
                time.sleep(min(wait, .02))
                return
            if select.select([process.stdout], [], [], wait)[0]:
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    eof = True
                    return
                log.write(chunk)
                scanned = (scan_tail + chunk).lower()
                empty_test_run |= any(marker in scanned for marker in (
                    b"0 tests passed", b"0 passed", b"ran 0 tests", b"0 suites passed", b"no matching tests"))
                invalid_repro |= any(marker in scanned for marker in (
                    b"error: cannot find", b"syntax error", b"compilation failed", b"build failed", b"undefined symbol"))
                scan_tail = scanned[-128:]
                total += len(chunk)
                tail.extend(chunk)
                del tail[:-65536]
                record.update(output_bytes=total, elapsed_seconds=round(time.monotonic() - started, 3))
                acceptance.save(metadata_path, record)

        def stop(sig):
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass

        try:
            while process.poll() is None or not eof:
                if cancelled:
                    break
                remaining = started + timeout - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                drain(min(.1, remaining))
            if timed_out or cancelled:
                stop(signal.SIGKILL if cancelled else signal.SIGTERM)
                end = time.monotonic() + 2
                while (process.poll() is None or not eof) and time.monotonic() < end:
                    drain(.05)
                if process.poll() is None or not eof:
                    stop(signal.SIGKILL)
                    end = time.monotonic() + .5
                    while (process.poll() is None or not eof) and time.monotonic() < end:
                        drain(.02)
                process.wait(timeout=1)
            code = 130 if cancelled else 124 if timed_out else process.wait(timeout=1)
        except BaseException:
            stop(signal.SIGKILL)
            process.wait(timeout=1)
            raise
        finally:
            process.stdout.close()
        record.update(status="cancelled" if cancelled else "timeout" if timed_out else "exited", exit=code,
                      elapsed_seconds=round(time.monotonic() - started, 3), output_bytes=total)
        acceptance.save(metadata_path, record)
    output = output_type(bytes(tail).decode("utf-8", "replace"), timed_out=timed_out,
                         elapsed=time.monotonic() - started, budget=timeout)
    output.log_path = str(log_path)
    output.output_bytes = total
    output.empty_test_run = empty_test_run
    output.invalid_repro = invalid_repro
    output.cancelled = cancelled
    return code, output
