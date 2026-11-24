import pytest

from member3.ai.provider import Provider, ProviderError
from member3.application.access_control import User
from member3.evaluate import build_facts, samples
from member3.services import ecn_service, planning_service
from member3.services.member1_adapter import Member1Adapter
from member3.services.member2_adapter import Member2Adapter

STANDIN = "member3.reference.member1_standin"
PLANNER = User("Asha", "Planner")


class FakeProvider(Provider):
    """Returns a fixed reply, or raises the given error."""
    name = "fake"

    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    def complete_json(self, prompt):
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


DOWN = FakeProvider(ProviderError("timeout"))


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("CHANGEWISE_DB", str(tmp_path / "app.db"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("CHANGEWISE_MEMBER1", STANDIN)  # test_member1_integration.py uses the real module
    return tmp_path / "app.db"


@pytest.fixture(scope="session")
def member1():
    return Member1Adapter(STANDIN)


@pytest.fixture(scope="session")
def member2(member1):
    return Member2Adapter(member1.simulate)


@pytest.fixture(scope="session")
def ecn_text():
    return samples("ecn_samples.json")[0]["text"]


@pytest.fixture(scope="session")
def facts(member1, member2):
    return build_facts(member1, member2, "BASE")


@pytest.fixture
def planned(member1, member2, ecn_text):
    """planned(scenario) -> stored run, through the real services."""
    def make(scenario="BASE", provider=None):
        review = ecn_service.create_review(ecn_text, scenario, member1, PLANNER)
        ecn_service.confirm(review, member1, PLANNER)
        return planning_service.get_run(planning_service.run_planning(review, member1, member2, PLANNER, provider))
    return make
