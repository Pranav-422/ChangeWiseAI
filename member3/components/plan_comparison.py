"""Member 2's own views, so the numbers are drawn exactly as the engine reports them."""
from member2.dashboard.evaluation_view import render as render_baselines  # noqa: F401
from member2.dashboard.optimization_view import render as render_recommendation  # noqa: F401
from member2.dashboard.plan_comparison import render as render_plans  # noqa: F401
