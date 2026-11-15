#!/bin/bash
# Full-resolution iOS Simulator captures for design verification.
#
#   sim.sh shot  <out.png> [device]   screenshot at full resolution (3x on iPhone)
#   sim.sh start <out.mp4> [device]   start recording at full frame rate
#   sim.sh stop  <out.mp4>            stop that recording and finish the file
#
# device: a UDID or simulator name; defaults to the booted one.
# Read a recording frame by frame:  node sheet.mjs <out.mp4> <sheet.png> --auto
# Measure a capture:                node edges.mjs <out.png> --scale 3 --rows y0-y1
set -euo pipefail

usage() { sed -n '4,10p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
cmd=${1:-}
out=${2:-}
device=${3:-booted}
[[ -n $cmd && -n $out ]] || usage
command -v xcrun >/dev/null || { echo "error: xcrun not found (needs Xcode)" >&2; exit 1; }
mkdir -p "$(dirname "$out")"
out="$(cd "$(dirname "$out")" && pwd)/$(basename "$out")"
state="${TMPDIR:-/tmp}/uc-simrec-$(printf '%s' "$out" | shasum | cut -c1-12)"

case $cmd in
  shot)
    xcrun simctl io "$device" screenshot --type=png "$out" >/dev/null
    echo "$out"
    ;;
  start)
    if [[ -f $state.pid ]] && kill -0 "$(cat "$state.pid")" 2>/dev/null; then
      echo "error: already recording $out" >&2; exit 1
    fi
    xcrun simctl io "$device" recordVideo --codec=h264 --force "$out" >"$state.log" 2>&1 &
    echo $! >"$state.pid"
    sleep 1.2
    if ! kill -0 "$(cat "$state.pid")" 2>/dev/null; then
      cat "$state.log" >&2; rm -f "$state.pid" "$state.log"; exit 1
    fi
    echo "recording $out (stop with: sim.sh stop $out)"
    ;;
  stop)
    [[ -f $state.pid ]] || { echo "error: no recording running for $out" >&2; exit 1; }
    pid=$(cat "$state.pid")
    kill -INT "$pid" 2>/dev/null || true
    for _ in $(seq 1 50); do kill -0 "$pid" 2>/dev/null || break; sleep 0.2; done
    rm -f "$state.pid" "$state.log"
    [[ -s $out ]] || { echo "error: the recording is empty" >&2; exit 1; }
    echo "$out"
    ;;
  *) usage ;;
esac
