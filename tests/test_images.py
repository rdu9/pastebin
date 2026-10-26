import httpx
from src.db.models import Visibility


async def test_create_paste_and_image_same_user(alice):
    # create the test paste

    p = await alice.post(
        "/api/v1/pastes/",
        json={
            "title": "my_paste",
            "content": "the_content",
            "language": "spanish",
            "visibility": "public",
            "burn_after_reading": "false",
            "expires_in": "never",
        },
    )

    assert p.status_code == 200

    # check if an image can be attached to it, it should pass with 200

    paste_uid = p.json()["uid"]

    r = await alice.post(
        "/api/v1/images/upload-url",
        json={"paste_uid": paste_uid, "content_type": "image/png", "size_bytes": 256},
    )

    assert r.status_code == 200

    assert r.json()["url"]
    assert r.json()["fields"]


async def test_create_paste_and_image_different_user(alice, bob):
    # create the test paste

    p = await alice.post(
        "/api/v1/pastes/",
        json={
            "title": "my_paste",
            "content": "the_content",
            "language": "spanish",
            "visibility": "public",
            "burn_after_reading": "false",
            "expires_in": "never",
        },
    )

    assert p.status_code == 200

    # check if an image can be attached to it from a different user, it should be rejected with 404

    paste_uid = p.json()["uid"]

    r = await bob.post(
        "/api/v1/images/upload-url",
        json={"paste_uid": paste_uid, "content_type": "image/png", "size_bytes": 256},
    )

    assert r.status_code == 404


async def test_create_image_with_wrong_content_type(alice):
    # create the test paste

    p = await alice.post(
        "/api/v1/pastes/",
        json={
            "title": "my_paste",
            "content": "the_content",
            "language": "spanish",
            "visibility": "public",
            "burn_after_reading": "false",
            "expires_in": "never",
        },
    )

    assert p.status_code == 200

    # configure the image, it shouldnt pass

    paste_uid = p.json()["uid"]

    r = await alice.post(
        "/api/v1/images/upload-url",
        json={"paste_uid": paste_uid, "content_type": "html/text", "size_bytes": 256},
    )

    assert r.status_code == 422


async def test_create_image_with_wrong_size_bytes(alice):
    # create the test paste

    p = await alice.post(
        "/api/v1/pastes/",
        json={
            "title": "my_paste",
            "content": "the_content",
            "language": "spanish",
            "visibility": "public",
            "burn_after_reading": "false",
            "expires_in": "never",
        },
    )

    assert p.status_code == 200

    # configure the image, it shouldnt pass

    paste_uid = p.json()["uid"]

    r = await alice.post(
        "/api/v1/images/upload-url",
        json={
            "paste_uid": paste_uid,
            "content_type": "image/png",
            "size_bytes": 6 * 1024 * 1024,
        },
    )

    assert r.status_code == 422


# records the existence of the image in the database

async def get_ticket(user) -> dict:
    p = await user.post("/api/v1/pastes/", json={"content": "the_content"})
    assert p.status_code == 200

    r = await user.post(
        "/api/v1/images/upload-url",
        json={"paste_uid": p.json()["uid"], "content_type": "image/png", "size_bytes": 256},
    )
    assert r.status_code == 200
    return r.json()

# actually uploads the image

async def upload_to_garage(ticket: dict):
    async with httpx.AsyncClient() as s3:
        up = await s3.post(
            ticket["url"],
            data=ticket["fields"],
            files={"file": ("a.png", b"x" * 256, "image/png")},
        )
    assert up.status_code == 204, up.text

# run the test, happy / unhappy paths

async def test_complete_after_upload(alice):
    ticket = await get_ticket(alice)
    await upload_to_garage(ticket)

    r = await alice.post(f"/api/v1/images/{ticket['image_uid']}/complete")

    assert r.status_code == 200
    assert r.json()["status"] == "ready"


async def test_complete_twice(alice):
    ticket = await get_ticket(alice)
    await upload_to_garage(ticket)
    await alice.post(f"/api/v1/images/{ticket['image_uid']}/complete")

    r = await alice.post(f"/api/v1/images/{ticket['image_uid']}/complete")

    assert r.status_code == 404


async def test_complete_without_upload(alice):
    ticket = await get_ticket(alice)

    r = await alice.post(f"/api/v1/images/{ticket['image_uid']}/complete")

    assert r.status_code == 404


async def test_another_user_completes_a_users_image(alice, bob):
    ticket = await get_ticket(alice)
    await upload_to_garage(ticket)

    r = await bob.post(f"/api/v1/images/{ticket['image_uid']}/complete")

    assert r.status_code == 404


########

async def get_ticket_with_visibility(user,visibility: Visibility) -> dict:
    p = await user.post("/api/v1/pastes/", json={"content": "the_content","visibility":visibility})
    assert p.status_code == 200

    r = await user.post(
        "/api/v1/images/upload-url",
        json={"paste_uid": p.json()["uid"], "content_type": "image/png", "size_bytes": 256},
    )
    assert r.status_code == 200
    return r.json()


async def test_view_image_happy_path(alice):
    response = await get_ticket_with_visibility(alice,visibility=Visibility.unlisted)
    await upload_to_garage(response)

    image_uid = response["image_uid"]

    r = await alice.post(
        f"/api/v1/images/{image_uid}/complete"
    )

    assert r.status_code == 200



    p = await alice.get(
        f"/i/{image_uid}"
    )
    assert p.status_code == 302

    location = p.headers["location"]
    assert location.startswith("http://localhost:3900/")
    
    async with httpx.AsyncClient() as s3:
        v = await s3.get(location)
    
    assert v.status_code == 200
    assert v.content == b"x" * 256

async def test_view_image_unhappy_path(alice,bob):
    response = await get_ticket_with_visibility(alice,visibility=Visibility.private)
    await upload_to_garage(response)

    image_uid = response["image_uid"]
    
    r = await alice.post(
        f"/api/v1/images/{image_uid}/complete"
    )
    assert r.status_code == 200

    # should be rejected, other user doesnt have access to a private paste that isnt his

    p = await bob.get(
            f"/i/{image_uid}"
        )
    assert p.status_code == 404


async def test_pending_image_unhappy_path(alice):
    response = await get_ticket_with_visibility(alice,visibility=Visibility.private)
    image_uid = response["image_uid"]

    p = await alice.get(
                f"/i/{image_uid}"
            )
    assert p.status_code == 404