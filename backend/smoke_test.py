"""
Smoke test for ParleyLab API v2.
Run: python smoke_test.py
"""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8000"


def get(path):
    r = urllib.request.urlopen(BASE + path)
    return r.status, json.loads(r.read())


def post(path, body, expect_error=False):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        r = urllib.request.urlopen(req)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        if expect_error:
            return e.code, json.loads(e.read())
        raise


passed = failed = 0


def check(name, condition, info=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} — {info}")
        failed += 1


print("\n=== ParleyLab API Smoke Tests ===\n")

# ── 1. Health check ────────────────────────────────────────────────────────────
s, d = get("/healthz")
check("GET /healthz → 200", s == 200)
check("healthz.status == ok", d.get("status") == "ok", d)
check("healthz.rl_model_loaded == True", d.get("rl_model_loaded") is True, d)
print(f"     payload: {d}")

# ── 2. Root info ───────────────────────────────────────────────────────────────
s, d = get("/")
check("GET / → 200", s == 200)
check("/ has endpoints key", "endpoints" in d, d)
ep = list(d.get("endpoints", {}).keys())
print(f"     endpoints: {ep}")

# ── 3. Scenario list (new /api/ route) ─────────────────────────────────────────
s, d = get("/api/scenario/list")
check("GET /api/scenario/list → 200", s == 200)
check("scenario count == 4", d.get("count") == 4, d)
ids = [x["id"] for x in d.get("scenarios", [])]
check("all 4 scenario IDs present", set(ids) == {"salary_v1", "rent_v1", "freelance_v1", "equity_v1"}, ids)
print(f"     scenarios: {ids}")

# ── 4. Validation — bad scenario_id pattern ─────────────────────────────────────
s, d = post("/api/scenario/start", {"scenario_id": "INVALID ID!"}, expect_error=True)
check("POST /api/scenario/start (bad id) → 422", s == 422, f"got {s}")
check("error code == validation_error", d.get("error") == "validation_error", d)
check("errors array populated", len(d.get("errors", [])) > 0, d)
print(f"     error: {d['error']} | {d['detail'][:60]}")

# ── 5. Validation — blank message ──────────────────────────────────────────────
s, d = post("/api/chat/message", {"session_id": "x", "message": "   "}, expect_error=True)
check("POST /api/chat/message (blank) → 422", s == 422, f"got {s}")
check("error code == validation_error", d.get("error") == "validation_error", d)
print(f"     error: {d['error']} | {d['detail'][:60]}")

# ── 6. Session not found ────────────────────────────────────────────────────────
s, d = post("/api/chat/message", {"session_id": "sess_notexist", "message": "hello"}, expect_error=True)
check("POST /api/chat/message (no session) → 4xx or 503", s in (404, 503, 500), f"got {s}")
print(f"     error: {d.get('error')} ({s})")

# ── 7. Evaluate — missing session ──────────────────────────────────────────────
s, d = post("/api/chat/evaluate", {"session_id": "sess_bad", "message": "hi", "turn_number": 1}, expect_error=True)
check("POST /api/chat/evaluate (no session) → 4xx", s in (404, 500, 503), f"got {s}")
print(f"     error: {d.get('error')} ({s})")

# ── 8. CORS preflight ──────────────────────────────────────────────────────────
req = urllib.request.Request(
    BASE + "/api/scenario/list",
    headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Content-Type",
    },
    method="OPTIONS",
)
try:
    r = urllib.request.urlopen(req)
    acao = r.headers.get("Access-Control-Allow-Origin", "")
    acam = r.headers.get("Access-Control-Allow-Methods", "")
    check("OPTIONS /api/scenario/list → CORS header", "localhost:3000" in acao or acao == "*", acao)
    print(f"     ACAO: {acao} | methods: {acam}")
except Exception as e:
    check("OPTIONS CORS preflight", False, str(e))

# ── 9. Legacy route still works ────────────────────────────────────────────────
s, d = get("/session/scenarios")
check("GET /session/scenarios (legacy) → 200", s == 200, f"got {s}")
print(f"     legacy scenarios count: {len(d) if isinstance(d, list) else d}")

# ── Summary ────────────────────────────────────────────────────────────────────
total = passed + failed
print(f"\n{'='*40}")
print(f"Results: {passed}/{total} passed", "✓" if failed == 0 else "✗")
if failed:
    print(f"         {failed} FAILED")
    sys.exit(1)
