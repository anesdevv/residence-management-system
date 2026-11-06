"""R\u00c9SIVO Supabase Latency and Connection Probe.

Measures network latency and transport layer metrics (DNS, TCP, TLS)
from the current host to the Supabase backend.

Never prints or logs the Supabase anon or service keys.
"""

from __future__ import annotations

import os
import socket
import ssl
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv


def load_credentials() -> tuple[str, str]:
    """Load SUPABASE_URL and SUPABASE_ANON_KEY safely.

    Checks active environment variables first, then searches candidates:
    .env in current directory, desktop/.env, web/.env, and repo root .env.
    Falls back to embedded desktop defaults if neither is set.
    NEVER logs or exposes the key.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    candidate_paths = [
        Path.cwd() / ".env",
        repo_root / "desktop" / ".env",
        repo_root / "web" / ".env",
        repo_root / ".env",
    ]

    for p in candidate_paths:
        if p.is_file():
            load_dotenv(p)

    fallback_url = "https://kjqbnurycfjsuufibkac.supabase.co"
    fallback_key = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtqcWJudXJ5Y2Zqc3V1Zmlia2FjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE1NzM1NjcsImV4cCI6MjEwNzE0OTU2N30."
        "6KBkUy6fcD3jGRVmfNUvDZtnK9siQFOJ8KBDvDL0JGM"
    )

    url = os.environ.get("SUPABASE_URL") or os.environ.get("PUBLIC_SUPABASE_URL") or fallback_url
    key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("PUBLIC_SUPABASE_ANON_KEY") or fallback_key

    return url.rstrip("/"), key


def extract_project_ref(url: str) -> tuple[str, str]:
    """Extract (hostname, project_ref) from a Supabase URL."""
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    if ":" in host:
        host = host.split(":")[0]
    parts = host.split(".")
    ref = parts[0] if parts else "unknown"
    return host, ref


def compute_stats(values: list[float]) -> dict[str, float]:
    """Compute summary statistics (min, median, p95, max) for numeric samples.

    Uses standard linear interpolation between ranks for the 95th percentile.
    Returns values rounded to 2 decimal places.
    """
    if not values:
        return {"min": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0, "count": 0}

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    min_val = sorted_vals[0]
    max_val = sorted_vals[-1]

    # Median calculation
    if n % 2 == 1:
        median_val = sorted_vals[n // 2]
    else:
        median_val = (sorted_vals[(n // 2) - 1] + sorted_vals[n // 2]) / 2.0

    # 95th Percentile with linear interpolation
    if n == 1:
        p95_val = sorted_vals[0]
    else:
        rank = 0.95 * (n - 1)
        low_idx = int(rank)
        high_idx = min(low_idx + 1, n - 1)
        weight = rank - low_idx
        p95_val = (1.0 - weight) * sorted_vals[low_idx] + weight * sorted_vals[high_idx]

    return {
        "min": round(min_val, 2),
        "median": round(median_val, 2),
        "p95": round(p95_val, 2),
        "max": round(max_val, 2),
        "count": n,
    }


def measure_connection_breakdown(
    host: str, port: int = 443, timeout: float = 8.0
) -> dict[str, float]:
    """Measure single connection transport phases: DNS, TCP connect, and TLS handshake.

    Returns times in milliseconds.
    """
    # Phase 1: DNS resolution
    t_dns_start = time.perf_counter()
    addr_info = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_STREAM)
    dns_ms = (time.perf_counter() - t_dns_start) * 1000.0
    ip = addr_info[0][4][0]

    # Phase 2: TCP handshake
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        t_tcp_start = time.perf_counter()
        sock.connect((ip, port))
        tcp_ms = (time.perf_counter() - t_tcp_start) * 1000.0

        # Phase 3: TLS handshake
        ctx = ssl.create_default_context()
        t_tls_start = time.perf_counter()
        ssock = ctx.wrap_socket(sock, server_hostname=host)
        tls_ms = (time.perf_counter() - t_tls_start) * 1000.0
        ssock.close()
    except Exception:
        sock.close()
        raise

    return {
        "dns": dns_ms,
        "tcp": tcp_ms,
        "tls": tls_ms,
        "total": dns_ms + tcp_ms + tls_ms,
    }


def run_http_series(
    client: httpx.Client,
    url: str,
    headers: dict[str, str],
    warmup_count: int = 2,
    sample_count: int = 30,
    label: str = "Request",
) -> list[float]:
    """Run warm-up requests followed by sample_count sequential timed requests.

    Returns list of response times in milliseconds.
    """
    for _ in range(warmup_count):
        try:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
        except Exception as e:
            print(f"[Warning] Warm-up to {url} failed: {e}", file=sys.stderr)

    timings: list[float] = []
    for _ in range(sample_count):
        t0 = time.perf_counter()
        resp = client.get(url, headers=headers)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        resp.raise_for_status()
        timings.append(elapsed_ms)

    return timings


def run_probe(sample_count: int = 30) -> dict[str, dict[str, float]]:
    """Execute complete probe suite against Supabase project."""
    url, key = load_credentials()
    host, ref = extract_project_ref(url)

    print("=" * 68)
    print(" R\u00c9SIVO SUPABASE NETWORK LATENCY & DISTANCE PROBE")
    print("=" * 68)
    print(f" Target Project Host : {host}")
    print(f" Target Project Ref  : {ref}")
    print(f" Base Supabase URL   : {url}")
    print(f" Credentials Auth    : [Configured - Key Hidden for Security]")
    print(f" Sample Count        : {sample_count} sequential requests (after 2 warm-ups)")
    print("-" * 68)

    # 1. Transport Layer Breakdown (DNS, TCP, TLS)
    print("Measuring transport layer timings (DNS, TCP, TLS)...")
    dns_times: list[float] = []
    tcp_times: list[float] = []
    tls_times: list[float] = []
    conn_total_times: list[float] = []

    for _ in range(sample_count):
        try:
            res = measure_connection_breakdown(host, port=443)
            dns_times.append(res["dns"])
            tcp_times.append(res["tcp"])
            tls_times.append(res["tls"])
            conn_total_times.append(res["total"])
        except Exception as e:
            print(f"[Warning] Connection sample failed: {e}", file=sys.stderr)

    dns_stats = compute_stats(dns_times)
    tcp_stats = compute_stats(tcp_times)
    tls_stats = compute_stats(tls_times)
    conn_stats = compute_stats(conn_total_times)

    # 2. HTTP Endpoints
    health_endpoint = f"{url}/auth/v1/health"
    rest_endpoint = f"{url}/rest/v1/rooms?select=id&limit=1"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }

    print(f"Probing GET {health_endpoint}...")
    with httpx.Client(timeout=15.0) as client:
        health_timings = run_http_series(
            client=client,
            url=health_endpoint,
            headers=headers,
            warmup_count=2,
            sample_count=sample_count,
            label="auth/v1/health",
        )
    health_stats = compute_stats(health_timings)

    print(f"Probing GET {rest_endpoint}...")
    with httpx.Client(timeout=15.0) as client:
        rest_timings = run_http_series(
            client=client,
            url=rest_endpoint,
            headers=headers,
            warmup_count=2,
            sample_count=sample_count,
            label="rest/v1/rooms",
        )
    rest_stats = compute_stats(rest_timings)

    results = {
        "dns": dns_stats,
        "tcp": tcp_stats,
        "tls": tls_stats,
        "connection_handshake": conn_stats,
        "auth_health": health_stats,
        "rest_rooms": rest_stats,
    }

    # Print summary table
    print("\n" + "=" * 68)
    print(" MEASUREMENT RESULTS (all values in ms)")
    print("=" * 68)
    print(f"{'Probe Target / Phase':<32} | {'Min':>8} | {'Median':>8} | {'p95':>8} | {'Max':>8}")
    print("-" * 68)
    print(f"{'DNS Lookup':<32} | {dns_stats['min']:>8.2f} | {dns_stats['median']:>8.2f} | {dns_stats['p95']:>8.2f} | {dns_stats['max']:>8.2f}")
    print(f"{'TCP Connect (SYN/ACK)':<32} | {tcp_stats['min']:>8.2f} | {tcp_stats['median']:>8.2f} | {tcp_stats['p95']:>8.2f} | {tcp_stats['max']:>8.2f}")
    print(f"{'TLS Handshake':<32} | {tls_stats['min']:>8.2f} | {tls_stats['median']:>8.2f} | {tls_stats['p95']:>8.2f} | {tls_stats['max']:>8.2f}")
    print(f"{'Total Connection Handshake':<32} | {conn_stats['min']:>8.2f} | {conn_stats['median']:>8.2f} | {conn_stats['p95']:>8.2f} | {conn_stats['max']:>8.2f}")
    print("-" * 68)
    print(f"{'GET /auth/v1/health':<32} | {health_stats['min']:>8.2f} | {health_stats['median']:>8.2f} | {health_stats['p95']:>8.2f} | {health_stats['max']:>8.2f}")
    print(f"{'GET /rest/v1/rooms?limit=1':<32} | {rest_stats['min']:>8.2f} | {rest_stats['median']:>8.2f} | {rest_stats['p95']:>8.2f} | {rest_stats['max']:>8.2f}")
    print("=" * 68)

    return results


if __name__ == "__main__":
    run_probe()
