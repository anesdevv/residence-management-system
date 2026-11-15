#!/usr/bin/env python3
"""Metadata-only storage inventory; writes one new private JSON report, never deletes data."""

import argparse
from datetime import datetime, timezone
import heapq
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time


def absolute(path):
    return Path(os.path.abspath(os.path.expanduser(path)))


def allocated(info):
    return getattr(info, 'st_blocks', 0) * 512


def inventory(roots, max_depth, top, minimum_bytes, recent_days):
    now = time.time()
    directories, skipped, errors = [], [], []
    largest, recent = [], []
    sequence = 0

    def keep(heap, row):
        nonlocal sequence
        sequence += 1
        item = (row['allocated_bytes'], sequence, row)
        if len(heap) < top:
            heapq.heappush(heap, item)
        elif item[:2] > heap[0][:2]:
            heapq.heapreplace(heap, item)

    def walk(path, device, depth, seen):
        result = {'path': str(path), 'allocated_bytes': 0, 'logical_bytes': 0, 'unique_files': 0}
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    try:
                        info = entry.stat(follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode):
                            skipped.append({'path': str(child), 'reason': 'symlink'})
                            continue
                        if info.st_dev != device:
                            skipped.append({'path': str(child), 'reason': 'different filesystem'})
                            continue
                        if stat.S_ISDIR(info.st_mode):
                            nested = walk(child, device, depth + 1, seen)
                            for key in ('allocated_bytes', 'logical_bytes', 'unique_files'):
                                result[key] += nested[key]
                            continue
                        if not stat.S_ISREG(info.st_mode):
                            continue
                        identity = (info.st_dev, info.st_ino)
                        if identity in seen:
                            continue
                        seen.add(identity)
                        size = allocated(info)
                        result['allocated_bytes'] += size
                        result['logical_bytes'] += info.st_size
                        result['unique_files'] += 1
                        row = {'path': str(child), 'allocated_bytes': size,
                               'logical_bytes': info.st_size, 'mtime': info.st_mtime}
                        if hasattr(info, 'st_birthtime'):
                            row['birthtime'] = info.st_birthtime
                        if info.st_size >= minimum_bytes:
                            keep(largest, row)
                            if info.st_mtime >= now - recent_days * 86400:
                                keep(recent, row)
                    except OSError as exc:
                        errors.append({'path': str(child), 'error': type(exc).__name__})
        except OSError as exc:
            errors.append({'path': str(path), 'error': type(exc).__name__})
        if depth <= max_depth:
            directories.append(result.copy())
        return result

    summaries = []
    for root in roots:
        error_start = len(errors)
        summary = walk(root, root.stat().st_dev, 0, set())
        summary['scan_complete'] = len(errors) == error_start
        summaries.append(summary)
    volume = Path('/System/Volumes/Data')
    if not volume.is_dir():
        volume = Path.home()
    disk = shutil.disk_usage(volume)
    return {
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'disk': {'path': str(volume), 'free_bytes': disk.free, 'total_bytes': disk.total},
        'roots': summaries,
        'directories': sorted(directories, key=lambda row: row['allocated_bytes'], reverse=True),
        'largest_files': [item[2] for item in sorted(largest, reverse=True)],
        'recent_large_files': [item[2] for item in sorted(recent, reverse=True)],
        'skipped': skipped, 'errors': errors,
        'accounting': 'Allocated file blocks, deduplicated by inode within each root. '
                      'APFS clones/snapshots and overlapping roots can share storage. '
                      'Do not sum root totals or treat them as reclaimable physical bytes.',
    }


def compare(report, previous):
    old = {row['path']: row for row in previous['roots']}
    rows = []
    for root in report['roots']:
        if root['path'] in old:
            rows.append({'path': root['path'],
                         'allocated_bytes_delta': root['allocated_bytes'] - old[root['path']]['allocated_bytes'],
                         'logical_bytes_delta': root['logical_bytes'] - old[root['path']]['logical_bytes']})
    result = {'previous_captured_at': previous['captured_at'], 'roots': rows}
    if report['disk']['path'] == previous['disk']['path']:
        result['free_bytes_delta'] = report['disk']['free_bytes'] - previous['disk']['free_bytes']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', action='append', required=True, help='Explicit directory to scan; repeat for additional roots')
    parser.add_argument('--output', required=True, help='New JSON file; parent must exist; existing files are never overwritten')
    parser.add_argument('--compare', help='Previous inventory JSON for growth comparison')
    parser.add_argument('--max-depth', type=int, default=3, help='Depth of directory summaries; the scan still visits all files (default: 3)')
    parser.add_argument('--top', type=int, default=50, help='Maximum files in each largest/recent list (default: 50)')
    parser.add_argument('--large-file-mib', type=float, default=100, help='Minimum logical MiB for file lists (default: 100)')
    parser.add_argument('--recent-days', type=float, default=7, help='Modification-time window for recent files (default: 7)')
    args = parser.parse_args()
    if args.top < 1 or args.max_depth < 0 or args.large_file_mib < 0 or args.recent_days < 0:
        parser.error('limits must be nonnegative and --top must be positive')
    roots = list(dict.fromkeys(absolute(value) for value in args.root))
    for root in roots:
        if root.is_symlink() or not root.is_dir():
            parser.error('each root must be an existing directory, not a symlink: ' + str(root))
    output = absolute(args.output)
    if os.path.lexists(output):
        parser.error('refusing to overwrite existing output: ' + str(output))
    if not output.parent.is_dir():
        parser.error('output parent must already exist: ' + str(output.parent))
    previous = None
    if args.compare:
        with open(absolute(args.compare), encoding='utf-8') as handle:
            previous = json.load(handle)
    report = inventory(roots, args.max_depth, args.top, args.large_file_mib * 1024 ** 2, args.recent_days)
    if previous is not None:
        report['comparison'] = compare(report, previous)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print(json.dumps({'output': str(output), 'free_GB': round(report['disk']['free_bytes'] / 1e9, 2),
                      'roots': len(roots), 'errors': len(report['errors']), 'skipped': len(report['skipped'])}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError) as exc:
        print('inventory failed: ' + str(exc), file=sys.stderr)
        sys.exit(1)
