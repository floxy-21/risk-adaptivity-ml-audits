"""Read-only public HTTP measurement transport; importing this performs no I/O.

This instrument measures actual requests, not a simulated archival service.
Response-body bytes are application HTTP body bytes, not TLS wire traffic.
The public-service rate limiter is recorded separately from API I/O time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import http.client
import json
from pathlib import Path
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import zlib


@dataclass
class Received:
    status: int
    payload: bytes
    observation: dict


class HTTPRecorder:
    """One serial, persistent HTTP/1.1 connection per public host, no retries."""

    def __init__(self, allowed_hosts, *, maximum_requests=60, min_start_interval=1.0,
                 timeout=30.0, connection_factory=None):
        self.allowed_hosts = set(allowed_hosts)
        self.maximum_requests = maximum_requests
        self.min_start_interval = min_start_interval
        self.timeout = timeout
        self.connections = {}
        self.records = []
        self.last_start = None
        self.stopped = False
        self.connection_factory = connection_factory or http.client.HTTPSConnection

    def get(self, url, *, trial_id, policy, role, information_round):
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname not in self.allowed_hosts:
            raise ValueError("Only the frozen public HTTPS hosts are allowed")
        if parts.username or parts.password or parts.port not in (None,443):
            raise ValueError("No credentials or nonstandard ports are accepted")
        private_keys = {"apikey","api_key","token","password","auth","authorization"}
        if any(k.lower() in private_keys for k,v in parse_qsl(parts.query)):
            raise ValueError("This benchmark accepts only unauthenticated public URLs")
        if self.stopped or len(self.records) >= self.maximum_requests:
            raise RuntimeError("Public request cap reached or provider throttling stopped the run")
        before = time.perf_counter()
        throttle = 0.0
        if self.last_start is not None:
            throttle = max(0.0,self.min_start_interval-(before-self.last_start))
            if throttle:
                time.sleep(throttle)
        started = time.perf_counter()
        waited = started-before
        self.last_start = started
        cpu_start = time.process_time()
        stamp = datetime.now(timezone.utc).isoformat()
        host = parts.hostname
        new_connection = host not in self.connections
        if new_connection:
            self.connections[host] = self.connection_factory(host,timeout=self.timeout)
        connection = self.connections[host]
        path = urlunsplit(("","",parts.path or "/",parts.query,""))
        record = {
            "sequence":len(self.records)+1,"trial_id":trial_id,"policy":policy,
            "role":role,"information_round":information_round,"url":url,
            "url_sha256":hashlib.sha256(url.encode()).hexdigest(),"started_utc":stamp,
            "new_connection_object":new_connection,"throttle_wait_seconds":waited,
            "requested_minimum_start_interval_seconds":self.min_start_interval,
            "status":None,"error":None,"response_body_bytes":0,"decoded_payload_bytes":0,
            "wire_bytes_measured":False,"automatic_retries":0,
        }
        self.records.append(record)  # Failed requests consume the cap as well.
        try:
            connection.request("GET",path,headers={
                "User-Agent":"CounterCertificateResearch/1.0 (public read-only benchmark)",
                "Accept":"application/json","Accept-Encoding":"identity",
            })
            response = connection.getresponse()
            header_time = time.perf_counter()
            raw = response.read()
            body_time = time.perf_counter()
            headers = {k.lower():v for k,v in response.getheaders()}
            encoding = headers.get("content-encoding","").lower()
            payload = gzip.decompress(raw) if encoding == "gzip" else zlib.decompress(raw) if encoding == "deflate" else raw
            if encoding not in ("","identity","gzip","deflate"):
                raise ValueError(f"Unsupported content encoding: {encoding}")
            record.update(
                status=response.status,header_wait_seconds=header_time-started,
                transfer_after_headers_seconds=body_time-header_time,
                api_io_seconds=body_time-started,response_body_bytes=len(raw),
                decoded_payload_bytes=len(payload),response_sha256=hashlib.sha256(raw).hexdigest(),
                decoded_payload_sha256=hashlib.sha256(payload).hexdigest(),
                content_encoding=encoding,
                selected_response_headers={k:v for k,v in headers.items() if k in {
                    "content-type","content-length","content-encoding","date","age",
                    "cache-control","etag","last-modified","x-cache","cf-cache-status",
                    "connection","location","retry-after"}},
            )
            if response.will_close:
                connection.close()
                self.connections.pop(host,None)
            # Redirects are logged and returned, never silently followed.
            if response.status == 429:
                self.stopped = True
            return Received(response.status,payload,record)
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["api_io_seconds"] = time.perf_counter()-started
            connection.close()
            self.connections.pop(host,None)
            raise
        finally:
            record["client_cpu_seconds"] = time.process_time()-cpu_start
            record["elapsed_including_throttle_seconds"] = time.perf_counter()-before

    def close(self):
        for conn in self.connections.values():
            conn.close()
        self.connections.clear()

    def write(self,path,*,scope,metadata=None):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        Path(path).write_text(json.dumps({
            "scope":scope,"maximum_requests":self.maximum_requests,
            "requests_attempted":len(self.records),"stopped":self.stopped,
            "metadata":metadata or {},"records":self.records,
            "measurement_limits":[
                "HTTP response-body bytes are not packet/TLS wire bytes.",
                "Client rate-limit wait is separate from provider API I/O.",
                "No automatic retries or forced cache-busting; provider cache state is uncontrolled.",
                "A new connection object is observed; a provider can close/reopen sockets independently."
            ]},indent=2),encoding="utf-8")


def hpm_range_url(system_id,feed_key,start_text,end_text,interval_seconds):
    """Build documented range parameters; timestamp semantics need adapter audit.

    start_text/end_text are supplied by the verified source adapter. This
    function deliberately does not guess milliseconds versus seconds or infer
    that average=0 means an unaltered physical device-register observation.
    """
    if int(system_id) <= 0 or int(interval_seconds) <= 0:
        raise ValueError("Invalid system or sampling interval")
    if not feed_key or "," in feed_key:
        raise ValueError("Exactly one declared public cumulative feed is required")
    return "https://heatpumpmonitor.org/timeseries/data?"+urlencode({
        "id":int(system_id),"feeds":feed_key,"start":start_text,"end":end_text,
        "interval":int(interval_seconds),"average":0,"delta":0,
    })


def summarize_trial(records,*,elapsed_seconds,planning_seconds,validation_seconds,
                    requested_timestamps,returned_timestamps,precision_success):
    """Actual policy completion metrics; caller measures outer elapsed time."""
    return {
        "requests":len(records),"information_rounds":len({r["information_round"] for r in records}),
        "distinct_requested_samples":len(set(requested_timestamps)),
        "distinct_returned_samples":len(set(returned_timestamps)),
        "body_bytes_received":sum(r["response_body_bytes"] for r in records),
        "decoded_payload_bytes":sum(r["decoded_payload_bytes"] for r in records),
        "api_io_seconds":sum(r.get("api_io_seconds",0) for r in records),
        "throttle_wait_seconds":sum(r["throttle_wait_seconds"] for r in records),
        "client_cpu_seconds":sum(r.get("client_cpu_seconds",0) for r in records),
        "planning_seconds":planning_seconds,"validation_seconds":validation_seconds,
        "end_to_end_elapsed_seconds":elapsed_seconds,"precision_success":precision_success,
        "http_errors":sum(r["status"] != 200 or r["error"] is not None for r in records),
    }
