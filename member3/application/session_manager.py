"""Per-session choices (scenario, user) and the shared context every page starts from."""
from typing import Any, NamedTuple, Optional

import streamlit as st

from ..ai.provider import get_provider
from ..services import approval_service, planning_service
from ..services.member1_adapter import Member1Adapter
from ..services.member2_adapter import Member2Adapter
from .access_control import ROLES, User


class Context(NamedTuple):
    member1: Member1Adapter
    member2: Member2Adapter
    user: User
    scenario: str
    dataset: dict
    run: Optional[dict]
    approval: Optional[dict]
    provider: Any


@st.cache_resource
def adapters():
    member1 = Member1Adapter()
    return member1, Member2Adapter(member1.simulate)


def render_sidebar():
    member1, _ = adapters()
    state = st.session_state
    scenarios = member1.list_scenarios()
    # Copied out of the widgets so the choice survives page changes.
    state.scenario = st.sidebar.selectbox("Scenario", scenarios, index=scenarios.index(state.get("scenario", scenarios[0])))
    state.user_name = st.sidebar.text_input("Your name", state.get("user_name", "Demo user"))
    state.role = st.sidebar.selectbox("Acting as", ROLES, index=ROLES.index(state.get("role", "Planner")))
    st.sidebar.caption("Demo roles: there is no login, so a role is chosen, not proven.")
    provider = get_provider()
    st.sidebar.caption(f"AI: {provider.name}" if provider else "AI: demo mode (offline rules and templates)")
    if member1.synthetic:
        st.sidebar.caption(f"Data: synthetic, from `{member1.name}`")


def context():
    member1, member2 = adapters()
    state = st.session_state
    scenario = state.get("scenario", member1.list_scenarios()[0])
    run = planning_service.latest_run(scenario)
    return Context(member1, member2, User(state.get("user_name", "Demo user"), state.get("role", "Planner")),
                   scenario, member1.load_dataset(scenario), run,
                   approval_service.get_decision(run["run_id"]) if run else None, get_provider())


def flash(message):
    """Show a confirmation after the rerun that follows a successful action."""
    st.session_state.flash = message


def page_header(title, ctx):
    st.title(title)
    if ctx.member1.synthetic:
        st.caption("Synthetic demo data. Decisions are recorded here only; no ERP or PLM record is changed.")
    if st.session_state.get("flash"):
        st.success(st.session_state.pop("flash"))
    if ctx.run and planning_service.is_stale(ctx.run, ctx.member1, ctx.member2):
        st.warning("The planning data changed after the last run. Run planning again.")


def require_run(ctx):
    """The current run, or an instruction and a stop."""
    if not ctx.run:
        st.info("No planning run yet for this scenario. Confirm the ECN on the ECN Intake page, then run planning.")
        st.stop()
    return ctx.run
