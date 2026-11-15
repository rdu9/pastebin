async def create_paste(client, content="v1", visibility="public", **extra):
    r = await client.post(
        "/api/v1/pastes/", json={"content": content, "visibility": visibility, **extra}
    )
    assert r.status_code == 200, r.text
    return r.json()["uid"]


async def edit(client, uid, content):
    return await client.put(f"/api/v1/pastes/{uid}", json={"content": content})


async def test_owner_can_edit(alice):
    uid = await create_paste(alice)

    r = await edit(alice, uid, "v2")

    assert r.status_code == 200
    assert (await alice.get(f"/api/v1/pastes/{uid}")).json()["content"] == "v2"


async def test_other_user_cannot_edit(alice, bob):
    uid = await create_paste(alice)

    assert (await edit(bob, uid, "hacked")).status_code == 404
    assert (await alice.get(f"/api/v1/pastes/{uid}")).json()["content"] == "v1"


async def test_logged_out_cannot_edit(alice, client):
    uid = await create_paste(alice)

    assert (await edit(client, uid, "hacked")).status_code == 401


async def test_burn_paste_cannot_be_edited(alice):
    uid = await create_paste(alice, burn_after_reading=True)

    assert (await edit(alice, uid, "v2")).status_code == 404


async def test_edits_create_revisions_with_old_content(alice):
    uid = await create_paste(alice)
    await edit(alice, uid, "v2")
    await edit(alice, uid, "v3")

    revisions = (await alice.get(f"/api/v1/pastes/{uid}/revisions")).json()
    assert [r["number"] for r in revisions] == [1, 2]

    first = (await alice.get(f"/api/v1/pastes/{uid}/revisions/1")).json()
    second = (await alice.get(f"/api/v1/pastes/{uid}/revisions/2")).json()
    assert first["content"] == "v1"
    assert second["content"] == "v2"


async def test_unedited_paste_has_empty_revision_list(alice):
    uid = await create_paste(alice)

    r = await alice.get(f"/api/v1/pastes/{uid}/revisions")

    assert r.status_code == 200
    assert r.json() == []


async def test_revision_list_has_no_content(alice):
    uid = await create_paste(alice)
    await edit(alice, uid, "v2")

    revisions = (await alice.get(f"/api/v1/pastes/{uid}/revisions")).json()

    assert "content" not in revisions[0]


async def test_stranger_sees_only_public_revisions(alice, bob):
    uid = await create_paste(alice)
    await edit(alice, uid, "v2")
    await edit(alice, uid, "v3")

    assert (await bob.get(f"/api/v1/pastes/{uid}/revisions")).json() == []
    assert (await bob.get(f"/api/v1/pastes/{uid}/revisions/1")).status_code == 404

    r = await alice.patch(f"/api/v1/pastes/{uid}/revisions/1", json={"is_public": True})
    assert r.status_code == 200

    revisions = (await bob.get(f"/api/v1/pastes/{uid}/revisions")).json()
    assert [r["number"] for r in revisions] == [1]
    assert (await bob.get(f"/api/v1/pastes/{uid}/revisions/1")).json()["content"] == "v1"
    assert (await bob.get(f"/api/v1/pastes/{uid}/revisions/2")).status_code == 404


async def test_public_revision_of_private_paste_stays_hidden(alice, client):
    uid = await create_paste(alice, visibility="private")
    await edit(alice, uid, "v2")
    await alice.patch(f"/api/v1/pastes/{uid}/revisions/1", json={"is_public": True})

    assert (await client.get(f"/api/v1/pastes/{uid}/revisions")).status_code == 404
    assert (await client.get(f"/api/v1/pastes/{uid}/revisions/1")).status_code == 404


async def test_other_user_cannot_change_revision_visibility(alice, bob):
    uid = await create_paste(alice)
    await edit(alice, uid, "v2")

    r = await bob.patch(f"/api/v1/pastes/{uid}/revisions/1", json={"is_public": True})

    assert r.status_code == 404
    assert (await bob.get(f"/api/v1/pastes/{uid}/revisions/1")).status_code == 404


async def test_changing_visibility_of_missing_revision_is_404(alice):
    uid = await create_paste(alice)

    r = await alice.patch(f"/api/v1/pastes/{uid}/revisions/99", json={"is_public": True})

    assert r.status_code == 404
