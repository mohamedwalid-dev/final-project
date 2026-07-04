import asyncio
import os
import sys

# Fast settings for testing (must be set BEFORE importing the module,
# since it reads env vars at import time)
os.environ["NODE_API_CB_FAILURE_THRESHOLD"] = "3"
os.environ["NODE_API_CB_COOLDOWN_SEC"] = "0.3"
os.environ["NODE_API_MAX_RETRIES"] = "2"
os.environ["NODE_API_RETRY_BACKOFF_BASE_SEC"] = "0.05"
os.environ["NODE_API_SERVICE_TOKEN"] = "test-token-123"

sys.path.insert(0, "/home/claude/build")

import httpx
from core.node_api_client import NodeAPIClient, NodeAPIError, _unwrap_list, _unwrap_one, clear_node_api_cache

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}")


async def test_basic_get_and_auth_header():
    print("\n[test] basic GET + auth header + unwrap")
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, json={"count": 2, "customers": [{"name": "A"}, {"name": "B"}]})

    client = NodeAPIClient(transport=httpx.MockTransport(handler))
    data = await client.get_customers(limit=10)
    check("auth header attached", seen_headers.get("authorization") == "Bearer test-token-123")
    check("unwrap finds 'customers' key", data == [{"name": "A"}, {"name": "B"}])
    await client.aclose()


async def test_cache_hit_avoids_second_call():
    print("\n[test] cache hit avoids second network call")
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json={"invoices": [{"id": 1}]})

    client = NodeAPIClient(transport=httpx.MockTransport(handler))
    clear_node_api_cache()
    await client.get_invoices(limit=5)
    await client.get_invoices(limit=5)  # same params -> should hit cache
    check("only 1 real request made for 2 identical calls", call_count["n"] == 1)
    await client.get_invoices(limit=99)  # different params -> new cache key
    check("different params bypass cache (now 2 requests)", call_count["n"] == 2)
    await client.aclose()


async def test_retry_then_success():
    print("\n[test] retry on 500 then succeed")
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] < 2:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json={"reviews": [{"id": "r1"}]})

    client = NodeAPIClient(transport=httpx.MockTransport(handler))
    clear_node_api_cache()
    data = await client.get_salary_reviews()
    check("succeeded after 1 retry", data == [{"id": "r1"}])
    check("exactly 2 attempts made", call_count["n"] == 2)
    await client.aclose()


async def test_all_retries_exhausted():
    print("\n[test] all retries exhausted -> NodeAPIError")
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(503, json={"error": "down"})

    client = NodeAPIClient(transport=httpx.MockTransport(handler))
    clear_node_api_cache()
    raised = False
    try:
        await client.get_absence_events()
    except NodeAPIError as e:
        raised = True
        check("error mentions status", "503" in str(e) or e.status_code == 503)
    check("NodeAPIError raised", raised)
    check("attempted MAX_RETRIES+1 = 3 times", call_count["n"] == 3)
    await client.aclose()


async def test_401_no_retry():
    print("\n[test] 401 fails immediately, no retry")
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(401, json={"error": "unauthorized"})

    client = NodeAPIClient(transport=httpx.MockTransport(handler))
    clear_node_api_cache()
    raised = False
    try:
        await client.get_incentive_requests()
    except NodeAPIError as e:
        raised = True
        check("status_code is 401", e.status_code == 401)
    check("401 raised", raised)
    check("only 1 attempt (no retry on 401)", call_count["n"] == 1)
    await client.aclose()


async def test_404_no_retry():
    print("\n[test] 404 fails immediately, no retry")
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(404, text="not found")

    client = NodeAPIClient(transport=httpx.MockTransport(handler))
    clear_node_api_cache()
    raised = False
    try:
        await client.get_invoice("does-not-exist")
    except NodeAPIError as e:
        raised = True
        check("status_code is 404", e.status_code == 404)
    check("404 raised", raised)
    check("only 1 attempt", call_count["n"] == 1)
    await client.aclose()


async def test_circuit_breaker_opens_and_recovers():
    print("\n[test] circuit breaker opens after threshold, fails fast, then half-opens")
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(500, json={"error": "down"})

    client = NodeAPIClient(transport=httpx.MockTransport(handler))
    clear_node_api_cache()

    # threshold=3 consecutive failures opens it. Each call_legal_cases()
    # call (different entity ids -> different cache keys) does up to 3
    # attempts (MAX_RETRIES+1) and each failed attempt increments the
    # breaker's consecutive-failure counter, so a single failing call
    # is enough on its own to cross threshold=3 within one call's retries.
    try:
        await client.get_legal_case("case-1")
    except NodeAPIError:
        pass

    check("circuit reports open after threshold crossed", client.circuit_status["open"] is True)

    calls_before = call_count["n"]
    raised_fast = False
    try:
        await client.get_legal_case("case-2")
    except NodeAPIError as e:
        raised_fast = True
        check("fails fast with circuit_breaker endpoint", e.endpoint == "circuit_breaker")
    check("short-circuited (raised)", raised_fast)
    check("no new HTTP request made while open", call_count["n"] == calls_before)

    await asyncio.sleep(0.35)  # cooldown is 0.3s
    check("circuit reports closed after cooldown elapses", client.circuit_status["open"] is False)

    await client.aclose()


async def test_unwrap_shapes():
    print("\n[test] _unwrap_list handles bare list / {key:[...]} / {data:[...]} / passthrough")
    check("bare list", _unwrap_list([1, 2, 3]) == [1, 2, 3])
    check("named key", _unwrap_list({"customers": [1, 2]}, "customers") == [1, 2])
    check("data fallback", _unwrap_list({"data": [1, 2]}, "nope") == [1, 2])
    check("passthrough when no list found", _unwrap_list({"foo": "bar"}, "nope") == {"foo": "bar"})

    print("\n[test] _unwrap_one handles bare object / {key:{...}} / {data:{...}} / passthrough")
    check("bare object", _unwrap_one({"_id": "x1", "name": "A"}) == {"_id": "x1", "name": "A"})
    check("named key single-object envelope", _unwrap_one({"invoice": {"_id": "i1"}}, "invoice") == {"_id": "i1"})
    check("data fallback single-object", _unwrap_one({"data": {"_id": "i1"}}, "nope") == {"_id": "i1"})
    check("REGRESSION: single-object envelope is NOT left wrapped",
          _unwrap_one({"invoice": {"_id": "i1", "ai_risk_score": 0.81}}, "invoice") == {"_id": "i1", "ai_risk_score": 0.81})


async def test_params_with_none_are_stripped():
    print("\n[test] None-valued params are not sent on the wire")
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json={"customers": []})

    client = NodeAPIClient(transport=httpx.MockTransport(handler))
    clear_node_api_cache()
    await client.get_customers(status=None, limit=7)
    check("status not sent when None", "status" not in seen_params)
    check("limit sent", seen_params.get("limit") == "7")
    await client.aclose()


async def main():
    await test_basic_get_and_auth_header()
    await test_cache_hit_avoids_second_call()
    await test_retry_then_success()
    await test_all_retries_exhausted()
    await test_401_no_retry()
    await test_404_no_retry()
    await test_circuit_breaker_opens_and_recovers()
    await test_unwrap_shapes()
    await test_params_with_none_are_stripped()
    print(f"\n{'='*50}\nRESULTS: {PASS} passed, {FAIL} failed\n{'='*50}")
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
