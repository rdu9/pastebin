from src.db.redis import redis_client


async def test_anonymous_create_and_view(client):
    r = await client.post("/api/v1/pastes/", json={"content": "print('hello')"})
    assert r.status_code == 200
    uid = r.json()["uid"]

    r = await client.get(f"/api/v1/pastes/{uid}")

    assert r.status_code == 200
    assert r.json()["content"] == "print('hello')"


async def test_private_paste_hidden_from_others(alice, bob):
    r = await alice.post(
        "/api/v1/pastes/", json={"content": "secret", "visibility": "private"}
    )
    uid = r.json()["uid"]

    assert (await alice.get(f"/api/v1/pastes/{uid}")).status_code == 200
    assert (await bob.get(f"/api/v1/pastes/{uid}")).status_code == 404


async def test_anonymous_creates_private_paste(client):
    r = await client.post(
        "/api/v1/pastes/",
        json={
            "title": "my_paste",
            "content": "random_content",
            "language": "english",
            "visibility": "private",
            "burn_after_reading": "false",
            "expires_in": "never",
        },
    )

    assert r.status_code == 403


async def test_raw_of_normal_paste(client):

    paste_content = "random_content"

    r = await client.post(
        "/api/v1/pastes/",
        json={
            "title": "my_paste",
            "content": paste_content,
            "language": "english",
            "visibility": "public",
            "burn_after_reading": "false",
            "expires_in": "never",
        },
    )

    assert r.status_code == 200

    paste_uid = r.json()["uid"]
    p = await client.get(f"/api/v1/pastes/{paste_uid}/raw")

    assert p.status_code == 200
    assert paste_content == p.text


async def test_burn_paste_reveal_works_once(client,bob):
    r = await client.post(
        "/api/v1/pastes/",
        json={
            "title": "my_paste",
            "content": "paste_content",
            "language": "english",
            "visibility": "public",
            "burn_after_reading": "true",
            "expires_in": "never",
        },
    )

    assert r.status_code == 200

    paste_uid = r.json()["uid"]

    # first time it should work

    a = await bob.post(f"/api/v1/pastes/{paste_uid}/reveal")
    assert a.status_code == 200

    # this time it shouldnt.

    a = await bob.post(f"/api/v1/pastes/{paste_uid}/reveal")
    assert a.status_code == 404


async def test_user_cant_delete_another_user_paste(alice, bob):
    a = await alice.post(
        "/api/v1/pastes/",
        json={
            "title": "my_paste",
            "content": "my_paste_content",
            "language": "english",
            "visibility": "public",
            "burn_after_reading": "false",
            "expires_in": "never",
        },
    )

    assert a.status_code == 200

    paste_uid = a.json()["uid"]

    b = await bob.delete(f"/api/v1/pastes/{paste_uid}")

    assert b.status_code == 404

    assert (await alice.get(f"/api/v1/pastes/{paste_uid}")).status_code == 200




async def test_view_by_someone_else_is_counted(alice, bob):
    uid = (await alice.post("/api/v1/pastes/", json={"content": "views"})).json()["uid"]

    assert (await bob.get(f"/api/v1/pastes/{uid}")).status_code == 200

    assert await redis_client.get(f"views:{uid}") == "1"


async def test_repeated_view_is_counted_once(alice, bob):
    uid = (await alice.post("/api/v1/pastes/", json={"content": "views"})).json()["uid"]

    await bob.get(f"/api/v1/pastes/{uid}")
    await bob.get(f"/api/v1/pastes/{uid}")

    assert await redis_client.get(f"views:{uid}") == "1"


async def test_owner_view_is_not_counted(alice):
    uid = (await alice.post("/api/v1/pastes/", json={"content": "views"})).json()["uid"]

    await alice.get(f"/api/v1/pastes/{uid}")

    assert await redis_client.get(f"views:{uid}") is None


async def test_anonymous_view_of_anonymous_paste_is_counted(client):
    uid = (await client.post("/api/v1/pastes/", json={"content": "views"})).json()["uid"]

    await client.get(f"/api/v1/pastes/{uid}")

    assert await redis_client.get(f"views:{uid}") == "1"


async def test_burn_paste_view_is_not_counted(alice, bob):
    uid = (
        await alice.post(
            "/api/v1/pastes/", json={"content": "views", "burn_after_reading": True}
        )
    ).json()["uid"]

    await bob.get(f"/api/v1/pastes/{uid}")

    assert await redis_client.get(f"views:{uid}") is None
