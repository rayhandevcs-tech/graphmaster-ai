"""Avatar catalogue and selection."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from app.models.enums import Gender


class TestAvatarCatalogue:
    async def test_lists_only_own_gender(
        self, client: AsyncClient, seeded, user_factory, auth_headers
    ):
        # An avatar of the other gender can never be selected, so listing it
        # would only advertise a door that never opens.
        user = await user_factory(gender=Gender.FEMALE)
        r = await client.get("/api/v1/avatars", headers=auth_headers(user))
        assert r.status_code == 200

        avatars = r.json()
        assert avatars, "seeded avatars should be returned"
        assert {a["gender"] for a in avatars} == {"female"}

    async def test_marks_unlock_state_by_level(
        self, client: AsyncClient, seeded, user_factory, auth_headers
    ):
        user = await user_factory(gender=Gender.FEMALE, current_level=1)
        avatars = (await client.get("/api/v1/avatars", headers=auth_headers(user))).json()

        by_code = {a["code"]: a for a in avatars}
        assert by_code["girl_default"]["is_unlocked"] is True
        assert by_code["girl_scholar"]["is_unlocked"] is False  # unlocks at level 10

    async def test_higher_level_unlocks_more(
        self, client: AsyncClient, seeded, user_factory, auth_headers
    ):
        user = await user_factory(gender=Gender.FEMALE, current_level=25)
        avatars = (await client.get("/api/v1/avatars", headers=auth_headers(user))).json()
        assert all(a["is_unlocked"] for a in avatars)

    async def test_full_catalogue_includes_both_genders(
        self, client: AsyncClient, seeded, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.get("/api/v1/avatars/all", headers=auth_headers(user))
        assert {a["gender"] for a in r.json()} == {"male", "female"}

    async def test_requires_authentication(self, client: AsyncClient, seeded):
        assert (await client.get("/api/v1/avatars")).status_code == 401


class TestAvatarSelection:
    async def test_select_unlocked_avatar(
        self, client: AsyncClient, seeded, user_factory, auth_headers, db
    ):
        from app.repositories.avatar import AvatarRepository

        user = await user_factory(gender=Gender.FEMALE, current_level=1)
        default = await AvatarRepository(db).get_by_code("girl_default")

        r = await client.put(
            "/api/v1/avatars/select",
            headers=auth_headers(user),
            json={"avatar_id": str(default.id)},
        )
        assert r.status_code == 200
        assert r.json()["avatar"]["code"] == "girl_default"

    async def test_cannot_select_locked_avatar(
        self, client: AsyncClient, seeded, user_factory, auth_headers, db
    ):
        from app.repositories.avatar import AvatarRepository

        user = await user_factory(gender=Gender.FEMALE, current_level=1)
        locked = await AvatarRepository(db).get_by_code("girl_scholar")  # level 10

        r = await client.put(
            "/api/v1/avatars/select",
            headers=auth_headers(user),
            json={"avatar_id": str(locked.id)},
        )
        assert r.status_code == 403
        assert "level 10" in r.json()["error"]["message"]

    async def test_cannot_select_other_gender_avatar(
        self, client: AsyncClient, seeded, user_factory, auth_headers, db
    ):
        # The rule cannot live in the UI alone; the catalogue endpoint is only
        # a convenience and a client can post any ID it likes.
        from app.repositories.avatar import AvatarRepository

        user = await user_factory(gender=Gender.FEMALE, current_level=50)
        other = await AvatarRepository(db).get_by_code("boy_default")

        r = await client.put(
            "/api/v1/avatars/select",
            headers=auth_headers(user),
            json={"avatar_id": str(other.id)},
        )
        assert r.status_code == 403

    async def test_unknown_avatar_is_404(
        self, client: AsyncClient, seeded, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.put(
            "/api/v1/avatars/select",
            headers=auth_headers(user),
            json={"avatar_id": str(uuid.uuid4())},
        )
        assert r.status_code == 404
