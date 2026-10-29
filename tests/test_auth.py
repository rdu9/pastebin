from conftest import login_as


async def test_healthz(client):
    r = await client.get("/healthz")

    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

async def test_me_without_logging(client):
    r = await client.get("/api/v1/auth/me")

    assert r.status_code == 401
    assert r.json()["error_code"] == "not_authenticated"

async def test_me_after_login(client):
    await login_as(client, "alice@example.com")

    r = await client.get("/api/v1/auth/me")

    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"

async def test_email_register_twice(client):

    #first register
    r = await client.post("/api/v1/auth/register",
                          json={"email": "my_email@gmail.com",
                                "password": "my_password"})

    assert r.status_code == 200

    # second register, should not pass
    r = await client.post("/api/v1/auth/register",
                              json={"email": "my_email@gmail.com",
                                    "password": "my_password"})
    
    assert r.status_code == 409
    

async def test_readyz(client):
    r = await client.get("/readyz")

    assert r.status_code == 200
    assert r.json() == {"postgres": "ok", "redis": "ok", "garage": "ok"}