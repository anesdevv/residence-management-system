"""Tests for the latency probe and statistical calculations."""

from __future__ import annotations

import pytest
from tools.perf.latency_probe import (
    compute_stats,
    extract_project_ref,
)


def test_compute_stats_empty() -> None:
    stats = compute_stats([])
    assert stats["count"] == 0
    assert stats["min"] == 0.0
    assert stats["median"] == 0.0
    assert stats["p95"] == 0.0
    assert stats["max"] == 0.0


def test_compute_stats_single_element() -> None:
    stats = compute_stats([42.5])
    assert stats["count"] == 1
    assert stats["min"] == 42.5
    assert stats["median"] == 42.5
    assert stats["p95"] == 42.5
    assert stats["max"] == 42.5


def test_compute_stats_odd_elements() -> None:
    data = [10.0, 50.0, 20.0, 40.0, 30.0]
    stats = compute_stats(data)
    assert stats["count"] == 5
    assert stats["min"] == 10.0
    assert stats["median"] == 30.0
    assert stats["max"] == 50.0
    # rank = 0.95 * 4 = 3.8; sorted = [10, 20, 30, 40, 50]
    # val = 0.2 * 40.0 + 0.8 * 50.0 = 48.0
    assert stats["p95"] == 48.0


def test_compute_stats_even_elements() -> None:
    data = [10.0, 20.0, 30.0, 40.0]
    stats = compute_stats(data)
    assert stats["count"] == 4
    assert stats["min"] == 10.0
    assert stats["median"] == 25.0
    assert stats["max"] == 40.0
    # rank = 0.95 * 3 = 2.85; sorted = [10, 20, 30, 40]
    # val = 0.15 * 30.0 + 0.85 * 40.0 = 4.5 + 34.0 = 38.5
    assert stats["p95"] == 38.5


def test_compute_stats_100_elements_deterministic() -> None:
    # 1.0 to 100.0 inclusive
    data = [float(i) for i in range(1, 101)]
    stats = compute_stats(data)
    assert stats["count"] == 100
    assert stats["min"] == 1.0
    assert stats["median"] == 50.5
    assert stats["max"] == 100.0
    # rank = 0.95 * 99 = 94.05; low=94 (val 95), high=95 (val 96)
    # 0.95 * 95 + 0.05 * 96 = 90.25 + 4.8 = 95.05
    assert stats["p95"] == 95.05


def test_extract_project_ref() -> None:
    host, ref = extract_project_ref("https://kjqbnurycfjsuufibkac.supabase.co")
    assert host == "kjqbnurycfjsuufibkac.supabase.co"
    assert ref == "kjqbnurycfjsuufibkac"

    host_port, ref_port = extract_project_ref("http://localhost:54321")
    assert host_port == "localhost"
    assert ref_port == "localhost"
