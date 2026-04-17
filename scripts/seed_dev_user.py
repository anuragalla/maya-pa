"""Seed a development user for local testing.

Usage: python -m scripts.seed_dev_user
"""

import asyncio

from sqlalchemy import select

from live150.db.models.user_profile import UserProfile
from live150.db.session import async_session_factory


async def main():
    async with async_session_factory() as db:
        # Check if already exists
        stmt = select(UserProfile).where(UserProfile.user_id == "dev-user-1")
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            print("Dev user already exists")
            return

        profile = UserProfile(
            user_id="dev-user-1",
            timezone="America/New_York",
            locale="en-US",
            profile_json={
                "name": "Dev User",
                "age": 30,
                "goals": ["improve sleep", "lose weight", "build muscle"],
                "dietary_flags": ["vegetarian"],
                "conditions_summary": "None reported",
            },
        )
        db.add(profile)
        await db.commit()
        print("Dev user seeded: dev-user-1")


if __name__ == "__main__":
    asyncio.run(main())
