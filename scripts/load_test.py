import asyncio
from collections import Counter
import os
import time

import httpx


def percentile(values: list[float], percent: int) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((percent / 100) * (len(ordered) - 1))))
    return ordered[index]


async def make_request(client, url, method, payload):
    start = time.perf_counter()
    try:
        if method == "POST":
            response = await client.post(
                url,
                json=payload,
                headers={"Origin": "http://localhost:8080", "X-CIET-Tenant": "ciet"},
            )
        else:
            response = await client.get(url)
        latency = time.perf_counter() - start
        return response.status_code, latency
    except httpx.HTTPError:
        latency = time.perf_counter() - start
        return 0, latency

async def run_load_test():
    url = os.getenv("LOAD_TEST_URL", "http://localhost:8000/healthz")
    concurrency = int(os.getenv("LOAD_TEST_CONCURRENCY", "25"))
    requests_count = int(os.getenv("LOAD_TEST_REQUESTS", "100"))
    method = os.getenv("LOAD_TEST_METHOD", "GET").upper()
    if method not in {"GET", "POST"}:
        raise ValueError("LOAD_TEST_METHOD must be GET or POST")
    payload = {
        "message": os.getenv("LOAD_TEST_MESSAGE", "What is the placement percentage?"),
        "language": "en",
        "channel": "website",
        "user_ref": "ciet-load-test",
        "history": [],
    }
    if not 1 <= concurrency <= 200 or not 1 <= requests_count <= 10_000:
        raise ValueError("Load-test concurrency or request count is outside the safe range")

    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(limits=limits, timeout=30) as client:
        latencies = []
        status_codes = []
        
        start_all = time.perf_counter()
        
        for offset in range(0, requests_count, concurrency):
            batch_size = min(concurrency, requests_count - offset)
            tasks = [make_request(client, url, method, payload) for _ in range(batch_size)]
            results = await asyncio.gather(*tasks)
            for status, lat in results:
                status_codes.append(status)
                latencies.append(lat)
                
        total_time = time.perf_counter() - start_all
        
        success_count = sum(1 for status in status_codes if status == 200)
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        min_lat = min(latencies) if latencies else 0
        max_lat = max(latencies) if latencies else 0
        p50_lat = percentile(latencies, 50)
        p95_lat = percentile(latencies, 95)
        p99_lat = percentile(latencies, 99)
        
        print(f"Total Requests: {requests_count}")
        print(f"Success Rate: {success_count / requests_count * 100:.1f}%")
        print(f"Total Time: {total_time:.3f} seconds")
        print(f"Average Latency: {avg_lat*1000:.1f} ms")
        print(f"P50 Latency: {p50_lat*1000:.1f} ms")
        print(f"P95 Latency: {p95_lat*1000:.1f} ms")
        print(f"P99 Latency: {p99_lat*1000:.1f} ms")
        print(f"Min Latency: {min_lat*1000:.1f} ms")
        print(f"Max Latency: {max_lat*1000:.1f} ms")
        print(f"Status Codes: {dict(sorted(Counter(status_codes).items()))}")
        if success_count != requests_count:
            raise SystemExit(1)

if __name__ == "__main__":
    asyncio.run(run_load_test())
