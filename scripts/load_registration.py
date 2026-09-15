#!/usr/bin/env python3
"""
Load test the public registration flow.

This script creates real application records on the target environment.
Use a dedicated test window and clean up records by the generated run id.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import http.cookiejar
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone


CSRF_RE = re.compile(
    rb'name=["\']csrfmiddlewaretoken["\'][^>]*value=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


@dataclass
class Result:
    index: int
    ok: bool
    status: int
    elapsed: float
    final_url: str
    error: str = ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Submit concurrent BRI registration applications against an environment."
    )
    parser.add_argument("--base-url", required=True, help="Target site root, for example https://example.com")
    parser.add_argument("--users", type=int, default=100, help="Total applications to submit")
    parser.add_argument("--concurrency", type=int, default=100, help="Concurrent workers")
    parser.add_argument("--timeout", type=float, default=30, help="Per-request timeout in seconds")
    parser.add_argument(
        "--run-id",
        default=datetime.now(timezone.utc).strftime("load-%Y%m%d%H%M%S"),
        help="Unique marker used in generated names, emails, and LINE ids",
    )
    parser.add_argument(
        "--path",
        default="/",
        help="Registration path, defaults to /",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required when the base URL is not localhost because this creates real records",
    )
    return parser


def normalize_base_url(base_url: str) -> str:
    value = base_url.rstrip("/")
    if not value.startswith(("http://", "https://")):
        raise ValueError("--base-url must start with http:// or https://")
    return value


def is_localhost(base_url: str) -> bool:
    host = urllib.parse.urlparse(base_url).hostname or ""
    return host in {"localhost", "127.0.0.1", "::1"}


def make_opener() -> urllib.request.OpenerDirector:
    cookie_jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))


def make_request(url: str, headers: dict[str, str], data: bytes | None = None) -> urllib.request.Request:
    return urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")


def fetch_csrf(opener: urllib.request.OpenerDirector, url: str, timeout: float) -> str:
    request = make_request(
        url,
        {
            "User-Agent": "BRIRegistrationLoadTest/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with opener.open(request, timeout=timeout) as response:
        body = response.read()

    match = CSRF_RE.search(body)
    if not match:
        raise RuntimeError("csrf token not found on registration page")
    return match.group(1).decode("utf-8")


def registration_payload(index: int, csrf_token: str, run_id: str) -> dict[str, str]:
    suffix = f"{run_id}-{index:04d}"
    return {
        "csrfmiddlewaretoken": csrf_token,
        "line_user_id": f"U{suffix}",
        "line_display_name": f"Load Test {index:04d}",
        "line_picture_url": "",
        "preferred_language": "th",
        "country_code": "TH",
        "country_name_en": "Thailand",
        "country_name_th": "ไทย",
        "first_name": f"โหลด{index:04d}",
        "last_name": "ทดสอบ",
        "nickname": f"LT{index:04d}",
        "gender": "male" if index % 2 else "female",
        "date_of_birth": "01011990",
        "phone": f"089{index:07d}"[-10:],
        "email": f"{suffix}@loadtest.invalid",
        "occupation": "Load tester",
        "region": "central",
        "province": "จังหวัดทดสอบโหลด",
        "district": "เขตทดสอบโหลด",
        "sub_district": "ตำบลทดสอบโหลด",
        "address": f"บ้านเลขที่ {index} ถนนทดสอบโหลด",
        "address_line": "",
        "city": "",
        "state_province": "",
        "postal_code": "",
        "is_pastor": "false",
        "has_studied_bri": "false",
        "facebook_link": f"https://facebook.com/{suffix}",
        "church": "คริสตจักรทดสอบโหลด",
        "serving_position": "",
        "mentor_name": "",
        "believer_years": "3",
        "goal": "ทดสอบโหลดระบบสมัครเรียน",
        "vision_calling": "ทดสอบโหลดระบบสมัครเรียน",
        "privacy_consent": "true",
    }


def submit_one(index: int, base_url: str, path: str, run_id: str, timeout: float) -> Result:
    opener = make_opener()
    url = urllib.parse.urljoin(base_url + "/", path.lstrip("/"))
    started = time.perf_counter()
    try:
        csrf_token = fetch_csrf(opener, url, timeout)
        payload = urllib.parse.urlencode(registration_payload(index, csrf_token, run_id)).encode("utf-8")
        request = make_request(
            url,
            {
                "User-Agent": "BRIRegistrationLoadTest/1.0",
                "Accept": "text/html,application/xhtml+xml",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": base_url,
                "Referer": url,
            },
            data=payload,
        )
        with opener.open(request, timeout=timeout) as response:
            body = response.read(2048)
            final_url = response.geturl()
            status = response.status
        elapsed = time.perf_counter() - started
        ok = status < 400 and (
            "/registration/success/" in final_url
            or "registration_success" in final_url
            or "สมัครเรียบร้อย" in body.decode("utf-8", errors="ignore")
        )
        return Result(index, ok, status, elapsed, final_url, "" if ok else "success page not reached")
    except urllib.error.HTTPError as exc:
        elapsed = time.perf_counter() - started
        return Result(index, False, exc.code, elapsed, exc.geturl(), str(exc))
    except Exception as exc:  # noqa: BLE001 - load test results should record every failure.
        elapsed = time.perf_counter() - started
        return Result(index, False, 0, elapsed, url, str(exc))


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percent
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        base_url = normalize_base_url(args.base_url)
    except ValueError as exc:
        parser.error(str(exc))

    if args.users < 1:
        parser.error("--users must be at least 1")
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")
    if not args.yes and not is_localhost(base_url):
        parser.error("--yes is required for non-localhost targets because the script creates real records")

    concurrency = min(args.concurrency, args.users)
    started = time.perf_counter()
    results: list[Result] = []

    print(
        f"Starting registration load test: users={args.users} concurrency={concurrency} "
        f"base_url={base_url} run_id={args.run_id}",
        flush=True,
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(submit_one, index, base_url, args.path, args.run_id, args.timeout)
            for index in range(1, args.users + 1)
        ]
        for completed, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            marker = "OK" if result.ok else "FAIL"
            print(
                f"[{completed:03d}/{args.users:03d}] {marker} user={result.index:04d} "
                f"status={result.status} time={result.elapsed:.3f}s url={result.final_url}",
                flush=True,
            )

    total_elapsed = time.perf_counter() - started
    ok_count = sum(1 for result in results if result.ok)
    fail_count = len(results) - ok_count
    latencies = [result.elapsed for result in results]

    print("\nSummary")
    print(f"  run_id:      {args.run_id}")
    print(f"  total:       {len(results)}")
    print(f"  succeeded:   {ok_count}")
    print(f"  failed:      {fail_count}")
    print(f"  wall time:   {total_elapsed:.3f}s")
    print(f"  throughput:  {ok_count / total_elapsed:.2f} ok/s" if total_elapsed else "  throughput:  n/a")
    print(f"  latency avg: {statistics.mean(latencies):.3f}s" if latencies else "  latency avg: n/a")
    print(f"  latency p50: {percentile(latencies, 0.50):.3f}s")
    print(f"  latency p95: {percentile(latencies, 0.95):.3f}s")
    print(f"  latency max: {max(latencies):.3f}s" if latencies else "  latency max: n/a")

    failed = [result for result in results if not result.ok]
    if failed:
        print("\nFailures")
        for result in failed[:20]:
            print(f"  user={result.index:04d} status={result.status} error={result.error}")
        if len(failed) > 20:
            print(f"  ...and {len(failed) - 20} more")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
