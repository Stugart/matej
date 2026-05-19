async def test_health_ok(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["env"]
    assert body["version"]
    assert body["time"]


async def test_health_no_secrets_leaked(client):
    r = await client.get("/api/v1/health")
    body = r.text.lower()
    for forbidden in ("secret", "api_key", "password", "anthropic", "openai"):
        assert forbidden not in body


async def test_root_serves_landing(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "Kutaj AI Core" in r.text


async def test_openapi_available_in_dev(client):
    r = await client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "Kutaj AI Core API"
