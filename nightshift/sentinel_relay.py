#!/usr/bin/env python3
"""Relay actionable watcher events to an explicitly selected planner agent and conversation."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

TRIGGERS = ('[SENTINEL_COMPLETED]', '[SENTINEL_BLOCKED]', '[SENTINEL_SCOPE_BLOCKED]',
            '[SENTINEL_PAUSED_FOR_PLANNER]', '[SENTINEL_AGENT_NO_RESPONSE]',
            '[SENTINEL_WORKER_DIED]', '[SENTINEL_PLANNER_REVIEW_REQUIRED]',
            '[SENTINEL_INACTIVE]', '[SENTINEL_FAILED]')


def relay(line, thread, context, command=None, agent='codex'):
    if not any(trigger in line for trigger in TRIGGERS):
        return False
    message = ('NightShift sentinel event (automated follow-up): ' + line.strip()
               + '\n' + context)
    if agent == 'codex':
        argv = [command or 'codex', 'queue', '--thread', thread, '--message', message, '--resume']
    elif agent == 'agy':
        argv = [command or 'agy', '--conversation', thread, '-p', message]
    else:
        raise ValueError('Unsupported planner agent: ' + agent)
    result = subprocess.run(argv, capture_output=True, text=True, timeout=300)

    if result.returncode or 'failed' in result.stderr.lower():
        raise RuntimeError('Could not enqueue/resume Planner: ' + result.stderr)
    print('[RELAY_DELIVERED] ' + result.stdout.strip(), flush=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--agent', choices=('codex', 'agy'), default='codex')
    parser.add_argument('--thread', '--planner-id', dest='thread', required=True)
    parser.add_argument('--wait', type=int, default=0)
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--task', default='')
    parser.add_argument('--context', default='Use planner Recover for blockers; do not treat inactivity alone as task failure.')
    args = parser.parse_args()
    if args.wait < 0 or args.interval <= 0:
        parser.error('wait must be nonnegative and interval positive')
    environment = dict(os.environ)
    environment.setdefault('WORKER_INACTIVE_REPEAT', '1')
    process = subprocess.Popen(['bash', str(args.root / 'nightshift/watch_worker.sh'), str(args.wait), str(args.interval), args.task],
                               cwd=args.root, env=environment, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    try:
        for line in process.stdout:
            print(line, end='', flush=True)
            relay(line, args.thread, args.context, agent=args.agent)
        return process.wait()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


if __name__ == '__main__':
    sys.exit(main())
