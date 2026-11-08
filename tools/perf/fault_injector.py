"""Fault and latency injector for RÉSIVO data layer.

Wraps the data layer and execute_network_call to inject:
- Latencies (e.g. 0.3s, 2.0s, 10.0s)
- Network timeouts (NetworkTimeoutError)
- HTTP 500 API errors (postgrest.exceptions.APIError)
- Connection errors / offline state (NetworkError)
- Flapping connections (alternating online/offline)

Can be used as a context manager, a function decorator, or a client wrapper.
"""

from __future__ import annotations

import logging
import sys
import time
from enum import Enum
from typing import Any, Callable, TypeVar

from postgrest.exceptions import APIError

from desktop.app.timeouts import NetworkError, NetworkTimeoutError

_log = logging.getLogger("resivo.fault_injector")

T = TypeVar("T")


class FaultMode(str, Enum):
    NORMAL = "normal"
    LATENCY = "latency"
    TIMEOUT = "timeout"
    HTTP_500 = "http_500"
    OFFLINE = "offline"
    FLAPPING = "flapping"


class FaultInjector:
    """Configurable fault and latency injector for testing network resilience."""

    def __init__(
        self,
        mode: FaultMode | str = FaultMode.NORMAL,
        *,
        latency: float = 0.0,
        flap_pattern: tuple[bool, ...] = (True, False),
        filter_is_write: bool | None = None,
        filter_table: str | None = None,
        timeout_delay: float = 0.0,
    ) -> None:
        if isinstance(mode, str):
            mode = FaultMode(mode.lower())
        self.mode = mode
        self.latency = float(latency)
        self.flap_pattern = flap_pattern
        self.filter_is_write = filter_is_write
        self.filter_table = filter_table
        self.timeout_delay = float(timeout_delay)

        self._call_count = 0
        self._fault_count = 0
        self._total_latency = 0.0
        self._patched_modules: dict[str, Any] = {}
        self._orig_execute_timeouts = None

    # Context manager convenience constructors
    @classmethod
    def with_latency(cls, seconds: float = 2.0, **kwargs) -> FaultInjector:
        return cls(mode=FaultMode.LATENCY, latency=seconds, **kwargs)

    @classmethod
    def with_timeout(cls, delay: float = 0.0, **kwargs) -> FaultInjector:
        return cls(mode=FaultMode.TIMEOUT, timeout_delay=delay, **kwargs)

    @classmethod
    def with_http_500(cls, **kwargs) -> FaultInjector:
        return cls(mode=FaultMode.HTTP_500, **kwargs)

    @classmethod
    def with_offline(cls, **kwargs) -> FaultInjector:
        return cls(mode=FaultMode.OFFLINE, **kwargs)

    @classmethod
    def with_flapping(cls, flap_pattern: tuple[bool, ...] = (True, False), **kwargs) -> FaultInjector:
        return cls(mode=FaultMode.FLAPPING, flap_pattern=flap_pattern, **kwargs)

    def _should_apply_fault(self, is_write: bool) -> bool:
        if self.filter_is_write is not None and self.filter_is_write != is_write:
            return False
        return True

    def intercept(self, fn: Callable[[], T], *, is_write: bool = False, **kwargs: Any) -> T:
        """Execute callable with injected fault/latency according to active mode."""
        self._call_count += 1

        if not self._should_apply_fault(is_write):
            if self._orig_execute_timeouts is not None:
                return self._orig_execute_timeouts(fn, is_write=is_write, **kwargs)
            return fn()

        if self.mode == FaultMode.LATENCY:
            if self.latency > 0:
                _log.debug("Injecting latency: %.3f s", self.latency)
                time.sleep(self.latency)
                self._total_latency += self.latency
            self._fault_count += 1
            if self._orig_execute_timeouts is not None:
                return self._orig_execute_timeouts(fn, is_write=is_write, **kwargs)
            return fn()

        elif self.mode == FaultMode.TIMEOUT:
            if self.timeout_delay > 0:
                time.sleep(self.timeout_delay)
                self._total_latency += self.timeout_delay
            self._fault_count += 1
            _log.info("Injecting timeout error (is_write=%s)", is_write)
            raise NetworkTimeoutError(is_write=is_write)

        elif self.mode == FaultMode.HTTP_500:
            self._fault_count += 1
            _log.info("Injecting HTTP 500 APIError")
            raise APIError(
                {
                    "message": "Internal Server Error (HTTP 500)",
                    "code": "500",
                    "details": "Simulated database fault in fault_injector",
                    "hint": None,
                }
            )

        elif self.mode == FaultMode.OFFLINE:
            self._fault_count += 1
            _log.info("Injecting offline NetworkError")
            raise NetworkError("Could not connect to the server. Check your connection and try again.")

        elif self.mode == FaultMode.FLAPPING:
            idx = (self._call_count - 1) % len(self.flap_pattern)
            is_online = self.flap_pattern[idx]
            if not is_online:
                self._fault_count += 1
                _log.info("Injecting flapping offline failure on call #%d", self._call_count)
                raise NetworkError("Flapping connection dropped. Check your connection.")
            else:
                if self.latency > 0:
                    time.sleep(self.latency)
                    self._total_latency += self.latency
                if self._orig_execute_timeouts is not None:
                    return self._orig_execute_timeouts(fn, is_write=is_write, **kwargs)
                return fn()

        else:
            if self._orig_execute_timeouts is not None:
                return self._orig_execute_timeouts(fn, is_write=is_write, **kwargs)
            return fn()

    def __enter__(self) -> FaultInjector:
        import desktop.app.timeouts as app_timeouts

        self._orig_execute_timeouts = app_timeouts.execute_network_call
        self._patched_modules.clear()

        def _patched(fn, *, is_write=False, **kwargs):
            return self.intercept(fn, is_write=is_write, **kwargs)

        # Patch desktop.app.timeouts as base
        self._patched_modules["desktop.app.timeouts"] = app_timeouts.execute_network_call
        app_timeouts.execute_network_call = _patched

        # Patch any loaded desktop module that has imported execute_network_call
        for name, mod in list(sys.modules.items()):
            if mod and (name.startswith("desktop.app") or name.startswith("tools.perf")):
                if hasattr(mod, "execute_network_call") and getattr(mod, "execute_network_call") is not _patched:
                    self._patched_modules[name] = getattr(mod, "execute_network_call")
                    setattr(mod, "execute_network_call", _patched)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        for name, orig in self._patched_modules.items():
            mod = sys.modules.get(name)
            if mod is not None:
                setattr(mod, "execute_network_call", orig)
        self._patched_modules.clear()
        self._orig_execute_timeouts = None

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "call_count": self._call_count,
            "fault_count": self._fault_count,
            "total_latency": round(self._total_latency, 3),
        }
