import streamlit as st


def render(cards):
    """cards: (label, value, help) tuples. None is shown as "n/a", never as zero."""
    per_row = len(cards) if len(cards) <= 4 else 3
    for start in range(0, len(cards), per_row):
        for column, (label, value, hint) in zip(st.columns(per_row), cards[start:start + per_row]):
            column.metric(label, "n/a" if value is None else value, help=hint, border=True)
