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
        json={"paste_uid": paste_uid, "content_type": "image/png", "size_bytes": 6 * 1024 * 1024},
    )

    assert r.status_code == 422
