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

    plot = data.copy().reset_index(drop=True)

    if horizontal:
        chart = (
            alt.Chart(plot)
            .mark_bar(color=color, cornerRadiusEnd=4)
            .encode(
                x=alt.X(f"{y}:Q", title=y),
                y=alt.Y(f"{x}:N", title=x, sort="-x"),
                tooltip=[x, y],
            )
            .properties(title=title, height=300)
        )
    else:
        # 直條圖：X 軸只用 1/2/3，店名不放軸上（避免直書難讀）
        plot["rank"] = [str(i + 1) for i in range(len(plot))]
        plot["full_name"] = plot[x].astype(str)
        order = list(plot["rank"])
        bars = (
            alt.Chart(plot)
            .mark_bar(color=color, cornerRadiusEnd=4)
            .encode(
                x=alt.X(
                    "rank:N",
                    title=None,
                    sort=order,
                    axis=alt.Axis(labelAngle=0, labelFontSize=14),
                ),
                y=alt.Y(
                    f"{y}:Q",
                    title=y,
                    axis=alt.Axis(titleAngle=0, titlePadding=8),
                ),
                tooltip=[
                    alt.Tooltip("full_name:N", title=x),
                    alt.Tooltip(f"{y}:Q", title=y),
                ],
            )
        )
        chart = bars.properties(title=title, height=300)
        st.altair_chart(chart, use_container_width=True)
        st.caption(
            "　".join(
                f"**{r.rank}.** {r.full_name}" for r in plot.itertuples()
            )
        )
        return

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
            x=alt.X("reviews:Q", title="DB 評論數"),
            y=alt.Y("intensity:Q", title="烈度", scale=alt.Scale(domain=[0, 10])),
            tooltip=["店家", "reviews", "intensity"],
        )
        .properties(title=title, height=300)
    )
    st.altair_chart(chart, use_container_width=True)
