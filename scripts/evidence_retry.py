#!/usr/bin/env python3
"""Retry only corrected TDD metadata through the mounted runtime's ordinary gate."""
import argparse
import copy
import json
import os
from pathlib import Path
import uuid

import acceptance as gate
import project_config
import worker_runtime as runtime
from lifecycle import task_level


def schedule(root, state, event, cases, snapshot):
    root, state, snapshot = Path(root).resolve(), Path(state).resolve(), Path(snapshot).resolve()
    lock = state / 'evidence-retry.lock'
    lock.mkdir()
    try:
        paused = gate.load(state / 'paused.json', {})
        status = gate.load(Path(os.environ['NIGHTSHIFT_STATE_DIR']) / 'worker.status', {})
        report = gate.load(state / 'reports' / event / 'report.json', {})
        result = report.get('result', {})
        error = result.get('runtime_error', {})
        raw = report.get('task', '')
        task_id = raw.split('|', 1)[0].strip().split()[0]
        base = report.get('base')
        if (paused.get('task') != task_id or status.get('state') != 'PAUSED_FOR_PLANNER'
                or error.get('phase') != 'hot'
                or not error.get('message', '').startswith('TDD case unchanged or source evidence unsupported: ')
                or result.get('outcome') != 'complete' or result.get('terminal_status') != 'complete'
                or gate.git(root, 'rev-parse', 'HEAD') != base):
            raise ValueError('retry requires matching unchanged-TDD pause on original HEAD')
        if (state / 'active.json').exists():
            raise ValueError('another active task exists')
        marker = 'NightShift-Key: ' + gate.key(task_id, raw)
        if gate.git(root, 'log', '--format=%H', '--fixed-strings', '--grep=' + marker, '-1'):
            raise ValueError('task already has a commit; refusing commit-replay shortcut')
        output = gate.load(state / 'runs' / event / 'output.json', {})
        artifact = Path(output.get('terminal_artifacts', {}).get('result', '')).resolve()
        metadata = gate.load(snapshot / 'snapshot.json', {})
        if (not snapshot.is_relative_to(Path(os.environ['NIGHTSHIFT_STATE_DIR']).resolve() / '.scratch/attempts' / task_id)
                or not artifact.is_relative_to(snapshot.parent)
                or metadata.get('task_id') != task_id or metadata.get('head') != base
                or Path(metadata.get('work_dir', '')).resolve() != root
                or not metadata.get('audit_tree')):
            raise ValueError('original attempt baseline does not match failure')
        old = result.get('tdd_cases', [])
        if (not isinstance(cases, list) or not cases or not all(case in old for case in cases)
                or len({case.get('id') for case in cases}) != len(cases)):
            raise ValueError('replacement declarations must be a nonempty unique original subset')
        dropped = [case for case in old if case not in cases]
        if not dropped:
            raise ValueError('retry must remove only unchanged declaration metadata')
        before = runtime.worktree_tree(root)
        permanent, evidence = gate.invoke(root, gate.config(root), 'hot', 'discover', base, runtime.run_verify)
        for case in old:
            observed = permanent.get(case['id'], {})
            fingerprint = observed.get('fingerprint')
            baseline = observed.get('baseline_fingerprint')
            if observed.get('source') != case.get('source') or not isinstance(fingerprint, str) or len(fingerprint) != 64:
                raise ValueError('discovery does not support original declaration')
            if case in dropped:
                if baseline != fingerprint:
                    raise ValueError('cannot drop a changed case')
            elif baseline == fingerprint or 'baseline_fingerprint' not in observed:
                raise ValueError('retained declaration must have changed case content')
        if runtime.worktree_tree(root) != before or gate.git(root, 'rev-parse', 'HEAD') != base:
            raise ValueError('workspace changed during evidence discovery; retry refused')
        if gate.load(state / 'paused.json', {}) != paused or (state / 'active.json').exists():
            raise ValueError('paused lifecycle changed during discovery')
        journal_path = state / 'tasks' / (gate.key(task_id, raw) + '.json')
        if journal_path.exists():
            raise ValueError('existing acceptance journal requires separate recovery')
        corrected = copy.deepcopy(result)
        corrected['tdd_cases'] = cases
        for field in ('runtime_error', 'hot', 'exit_code', 'terminal_status', 'commit'):
            corrected.pop(field, None)
        retry_event = uuid.uuid4().hex
        args = dict(work_dir=str(root), base=base, target=runtime.task_field(raw, 'TARGET'),
                    verify=runtime.task_field(raw, 'VERIFY'), task_id=task_id, title=raw,
                    level=task_level(raw), worker_port='3001', timeout=180,
                    attempt_baseline=str(snapshot), required_cases=runtime.task_field(raw, 'CASES'),
                    agent_id=result.get('registration_id', ''), constraints=runtime.task_field(raw, 'CONSTRAINTS'))
        gate.save(state / 'evidence-retries' / retry_event / 'request.json',
                  dict(original_event=event, worktree=before, dropped=dropped, retained=cases,
                       baseline=str(snapshot), discovery=evidence))
        # ready_commit replay reruns normal hot/VERIFY/audit before runtime commits.
        gate.save(journal_path, dict(task_id=task_id, title=raw, base=base, phase='ready_commit',
                  result=corrected, registration_id=result.get('registration_id', ''), args=args))
        gate.save(state / 'active.json', dict(raw=raw, claimed=True, task_id=task_id, base=base,
                  event=retry_event, phase='evidence_retry', attempt_baseline=str(snapshot)))
        (state / 'paused.json').unlink()
        return dict(task_id=task_id, retry_event=retry_event, dropped=dropped, state='queued_for_runtime_revalidation')
    finally:
        lock.rmdir()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--project')
    parser.add_argument('--event',required=True)
    parser.add_argument('--cases',required=True,type=Path)
    parser.add_argument('--snapshot',required=True,type=Path)
    args=parser.parse_args()
    name,root,state=project_config.resolve_project(args.config,args.project)
    if state is None:
        parser.error('external runner configuration is required')
    os.environ.update(NIGHTSHIFT_CONFIG_FILE=str(Path(args.config).resolve()),NIGHTSHIFT_PROJECT_NAME=name,
                      NIGHTSHIFT_PROJECT_ROOT=str(root),NIGHTSHIFT_STATE_DIR=str(state))
    print(json.dumps(schedule(root,gate.state_dir(root),args.event,json.loads(args.cases.read_text()),args.snapshot)))


if __name__=='__main__':
    main()
