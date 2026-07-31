"""Drama Radar Altair theme — matches dark dashboard UI."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

DRAMA_COLORS = ["#ff315d", "#be3cff", "#ff811b", "#f7ba38", "#ff6687", "#e00043"]


def configure_altair_theme() -> None:
    theme = {
        "config": {
            "background": "transparent",
            "view": {"stroke": "transparent"},
            "title": {
                "color": "#fff9fc",
                "fontSize": 15,
                "fontWeight": 700,
                "anchor": "start",
            },
            "axis": {
                "labelColor": "#d8cdd3",
                "titleColor": "#fff9fc",
                "gridColor": "rgba(255,255,255,0.08)",
                "domainColor": "rgba(255,255,255,0.15)",
            },
            "legend": {
                "labelColor": "#d8cdd3",
                "titleColor": "#fff9fc",
            },
            "header": {
                "labelColor": "#fff9fc",
                "titleColor": "#fff9fc",
            },
        }
    }
    alt.themes.register("drama", lambda: theme)
    alt.themes.enable("drama")


@st.cache_data(ttl=300)
def cached_star_distribution() -> pd.DataFrame:
    from dashboard.charts import star_distribution_data

    return star_distribution_data()


@st.cache_data(ttl=300)
def cached_top_intensity(limit: int = 10) -> pd.DataFrame:
    from dashboard.charts import top_intensity_data

    return top_intensity_data(limit=limit)


def render_bar(
    data: pd.DataFrame,
    x: str,
    y: str,
    *,
    title: str,
    horizontal: bool = False,
    color: str = "#ff315d",
) -> None:
    if data.empty:
        st.info(f"{title} 尚無資料。")
        return

    chart = (
        alt.Chart(data)
        .mark_bar(color=color, cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                f"{y}:Q" if horizontal else f"{x}:N",
                title=y if horizontal else x,
            ),
            y=alt.Y(
                f"{x}:N" if horizontal else f"{y}:Q",
                title=x if horizontal else y,
                sort="-x" if horizontal else "-y",
            ),
            tooltip=[x, y],
        )
        .properties(title=title, height=300)
    )
    st.altair_chart(chart, use_container_width=True)


def render_pie(data: pd.DataFrame, label: str, value: str, *, title: str) -> None:
    if data.empty:
        st.info(f"{title} 尚無資料。")
        return

    chart = (
        alt.Chart(data)
        .mark_arc(innerRadius=55, outerRadius=110, stroke="#151118", strokeWidth=1)
        .encode(
            theta=alt.Theta(f"{value}:Q", stack=True),
            color=alt.Color(
                f"{label}:N",
                legend=alt.Legend(title=label),
                scale=alt.Scale(range=DRAMA_COLORS),
            ),
            tooltip=[label, value],
        )
        .properties(title=title, height=300)
    )
    st.altair_chart(chart, use_container_width=True)


def render_scatter(data: pd.DataFrame, *, title: str) -> None:
    if data.empty:
        st.info(f"{title} 尚無資料。")
        return

    chart = (
        alt.Chart(data)
        .mark_circle(size=85, color="#ff315d", opacity=0.8)
        .encode(
            x=alt.X("reviews:Q", title="Google 評論數"),
            y=alt.Y("intensity:Q", title="烈度", scale=alt.Scale(domain=[0, 10])),
            tooltip=["店家", "reviews", "intensity"],
        )
        .properties(title=title, height=300)
    )
    st.altair_chart(chart, use_container_width=True)
