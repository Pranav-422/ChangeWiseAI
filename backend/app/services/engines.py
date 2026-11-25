"""The real engines on PostgreSQL data. No setting can put a test double here."""
from functools import lru_cache

from member3.ai.provider import get_provider  # noqa: F401  (services take the provider from here)
from member3.services.member1_adapter import Member1Adapter
from member3.services.member2_adapter import Member2Adapter

from ..integrations import member1_postgres

MEMBER1 = member1_postgres.__name__


@lru_cache
def engines():
    member1 = Member1Adapter(MEMBER1)
    return member1, Member2Adapter(member1.simulate)
