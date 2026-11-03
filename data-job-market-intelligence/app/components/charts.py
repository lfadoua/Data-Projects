"""Small coordinated charts. Every plotted count is supplied by the analytics API."""

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components.design import empty_state, safe

COLORS = ["#245deb", "#60b5fa", "#9270f4", "#baa6fb", "#28c3b1", "#a3c6fa", "#cbd5e1"]
PLOT_CONFIG = {"displayModeBar": False, "responsive": True}
COUNTRY_ISO = {
    "United States": "USA",
    "United Kingdom": "GBR",
    "Canada": "CAN",
    "Australia": "AUS",
    "India": "IND",
}


def style(figure, height=220):
    figure.update_layout(
        height=height,
        margin=dict(l=0, r=8, t=12, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", size=12, color="#526581"),
        hoverlabel=dict(bgcolor="white", bordercolor="#e6ecf5", font_size=14),
    )
    return figure


def skills_chart(items, total, limit=5):
    items = items[:limit]
    if not items:
        empty_state("No skills found", "Try broadening the current filters.")
        return
    maximum = max(row["count"] for row in items) or 1
    rows = []
    for item in items:
        count = item["count"]
        percent = 100 * count / total if total else 0
        label = f"{item['name']}: {count:,} postings, {percent:.2f}% of matching jobs"
        rows.append(
            f'<div class="dj-skill-row" tabindex="0" title="{safe(label)}" '
            f'aria-label="{safe(label)}">'
            f'<span class="dj-skill-name">{safe(item["name"])}</span>'
            '<div class="dj-bar-track"><div class="dj-bar-fill" '
            f'style="width:{100 * count / maximum:.2f}%"></div></div>'
            f'<span class="dj-skill-count">{count:,}<small>{percent:.2f}%</small></span></div>'
        )
    st.html("".join(rows))


def role_chart(items, key="roles", height=218, limit=7):
    items = items[:limit]
    if not items:
        empty_state("No matching roles", "Broaden the filters to explore role distribution.")
        return
    figure = go.Figure(
        go.Bar(
            x=[i["count"] for i in reversed(items)],
            y=[i["name"] for i in reversed(items)],
            orientation="h",
            marker_color=[COLORS[i % len(COLORS)] for i in range(len(items))][::-1],
            marker_cornerradius=4,
            hovertemplate="%{y}<br><b>%{x:,}</b> postings<extra></extra>",
        )
    )
    style(figure, height)
    figure.update_layout(
        bargap=0.42,
        xaxis=dict(
            title=dict(text="Postings", font=dict(size=12)),
            gridcolor="#edf2fa",
            tickformat="~s",
            zeroline=False,
            automargin=True,
        ),
        yaxis=dict(title=None, automargin=True, tickfont=dict(size=12)),
    )
    st.plotly_chart(figure, width="stretch", config=PLOT_CONFIG, key=key, theme=None)


def seniority_chart(items, total, key="seniority"):
    if not items:
        empty_state("No seniority data", "No matching categories are recorded.")
        return
    figure = go.Figure(
        go.Pie(
            labels=[i["name"] for i in items],
            values=[i["count"] for i in items],
            hole=0.73,
            sort=False,
            direction="clockwise",
            textinfo="none",
            marker=dict(colors=COLORS, line=dict(color="white", width=2)),
            hovertemplate="%{label}<br>%{value:,} postings · %{percent:.1%}<extra></extra>",
        )
    )
    style(figure, 197)
    figure.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=8, b=8),
        annotations=[
            dict(
                text=f"<b>{total:,}</b>",
                x=0.5,
                y=0.54,
                showarrow=False,
                font=dict(size=18, color="#17213c"),
            ),
            dict(text="jobs", x=0.5, y=0.40, showarrow=False, font=dict(size=10, color="#6c80a2")),
        ],
    )
    left, right = st.columns([1.1, 1], gap="small", vertical_alignment="center")
    with left:
        st.plotly_chart(figure, width="stretch", config=PLOT_CONFIG, key=key, theme=None)
    with right:
        legend = []
        for index, item in enumerate(items):
            percent = 100 * item["count"] / total if total else 0
            legend.append(
                f'<div class="dj-legend-row" title="{item["count"]:,} postings">'
                f'<i style="background:{COLORS[index % len(COLORS)]}"></i>'
                f'<span class="dj-legend-name">{safe(item["name"])}</span>'
                f"<strong>{percent:.1f}%</strong></div>"
            )
        st.html('<div class="dj-legend">' + "".join(legend) + "</div>")


def location_chart(countries, cities, key="location", compact=True, heading=""):
    if heading:
        title, controls = st.columns([2.3, 1], gap="small", vertical_alignment="center")
        with title:
            st.html(f'<div class="dj-card-header"><h2>{safe(heading)}</h2></div>')
    else:
        controls = st.container()
    with controls:
        mode = st.segmented_control(
            "Location view",
            ["Map", "List"],
            default="Map",
            key=f"{key}_mode",
            label_visibility="collapsed",
        )
    known = [row for row in countries if row["name"] in COUNTRY_ISO]
    unknown = sum(row["count"] for row in countries if row["name"] == "Unknown")
    if mode == "List":
        st.dataframe(
            pd.DataFrame(countries).rename(columns={"name": "Country", "count": "Postings"}),
            hide_index=True,
            width="stretch",
            height=183 if compact else "auto",
        )
        return
    left, right = st.columns([1.45, 1], gap="small", vertical_alignment="center")
    with left:
        if known:
            maximum = max(row["count"] for row in known) or 1
            figure = go.Figure(
                go.Scattergeo(
                    locations=[COUNTRY_ISO[row["name"]] for row in known],
                    locationmode="ISO-3",
                    text=[f"{row['name']}<br>{row['count']:,} postings" for row in known],
                    hovertemplate="%{text}<extra></extra>",
                    marker=dict(
                        size=[9 + 21 * math.sqrt(row["count"] / maximum) for row in known],
                        color="#287bfa",
                        opacity=0.75,
                        line=dict(width=3, color="#d9eaff"),
                    ),
                )
            )
            style(figure, 140 if compact else 270)
            figure.update_geos(
                projection_type="natural earth",
                showframe=False,
                showcoastlines=False,
                showland=True,
                landcolor="#e8f0fe",
                showcountries=True,
                countrycolor="white",
                countrywidth=0.7,
                bgcolor="rgba(0,0,0,0)",
                lataxis_range=[-60, 85],
            )
            figure.update_layout(margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(
                figure,
                width="stretch",
                key=key,
                theme=None,
                config={**PLOT_CONFIG, "topojsonURL": "/app/static/geo/"},
            )
        else:
            st.caption("No recorded countries can be mapped for these filters.")
    with right:
        rows = []
        known_cities = [c for c in cities if c["name"] != "Unknown"][:5]
        for index, city in enumerate(known_cities, 1):
            rows.append(
                f'<div class="dj-city"><span>{index}</span>'
                f"<span>{safe(city['name'])}</span><strong>{city['count']:,}</strong></div>"
            )
        st.html(
            '<div class="dj-cities"><h3>Top Cities</h3>'
            + ("".join(rows) if rows else '<div class="dj-caption">No recorded cities</div>')
            + "</div>"
        )
    st.html(
        '<div class="dj-caption" title="Marker sizes represent posting counts. '
        'Country centroids are not inferred job locations.">Country-level view'
        + (f" · {unknown:,} country unknown" if unknown else "")
        + "</div>"
    )


def heatmap(items, roles, skills, key="skill_role"):
    if not items:
        empty_state("No role–skill overlap", "No tracked combinations match the selected filters.")
        return
    lookup = {(row["role"], row["skill"]): row["count"] for row in items}
    figure = go.Figure(
        go.Heatmap(
            z=[[lookup.get((role, skill), 0) for skill in skills] for role in roles],
            x=skills,
            y=roles,
            colorscale=[[0, "#f2f7ff"], [0.45, "#8fc4ff"], [1, "#2563eb"]],
            hovertemplate="%{y} · %{x}<br>%{z:,} postings<extra></extra>",
            colorbar=dict(thickness=12, title=dict(text="Postings", font=dict(size=12))),
            xgap=3,
            ygap=3,
        )
    )
    style(figure, max(360, len(roles) * 46 + 100))
    figure.update_layout(
        margin=dict(l=0, r=12, t=12, b=90),
        xaxis=dict(title=None, tickangle=-30, automargin=True, tickfont=dict(size=12)),
        yaxis=dict(title=None, automargin=True, tickfont=dict(size=12)),
    )
    st.plotly_chart(figure, width="stretch", config=PLOT_CONFIG, key=key, theme=None)
    with st.expander("Read Skill × Role counts as a table"):
        st.dataframe(
            pd.DataFrame(figure.data[0].z, index=roles, columns=skills).rename_axis("Role"),
            width="stretch",
        )
