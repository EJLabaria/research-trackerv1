"""
dashboard.py

Live-filtering dashboard over your combined researcher dataset. Point it
at authors_master.csv (built by combine_datasets.py) to filter across
NVIDIA, Wayve, VLA, and any future sections all in one view -- or point
it at any single CSV if you just want one section.

Usage:
    streamlit run dashboard.py -- --csv authors_master.csv
"""

import argparse
import sys

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Researcher Tracker", layout="wide")


def get_csv_path():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="authors_master.csv")
    args, _ = parser.parse_known_args(sys.argv[1:])
    return args.csv


@st.cache_data
def load_data(path):
    df = pd.read_csv(path)
    # Numeric columns may have been written as blank/text -- coerce for filtering/sorting
    for col in ("paper_count", "h_index", "citation_count"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def main():
    st.title("Researcher Tracker")

    csv_path = get_csv_path()
    try:
        df = load_data(csv_path)
    except FileNotFoundError:
        st.error(
            f"Couldn't find {csv_path}. If you haven't built a combined file yet, run "
            f"combine_datasets.py first, or pass --csv pointing at any single dataset file."
        )
        return

    # -- Sidebar filters --
    st.sidebar.header("Filters")

    if "source" in df.columns:
        sources = sorted(set(s.strip() for val in df["source"].dropna() for s in str(val).split(";")))
        selected_sources = st.sidebar.multiselect("Dataset / Section", sources, default=sources)
    else:
        selected_sources = None

    name_filter = st.sidebar.text_input("Name contains")
    affiliation_filter = st.sidebar.text_input("Affiliation contains")

    min_citations = 0
    if "citation_count" in df.columns and df["citation_count"].notna().any():
        max_citations = int(df["citation_count"].max())
        min_citations = st.sidebar.slider("Min citation count", 0, max_citations, 0)

    has_github = st.sidebar.checkbox("Has GitHub only")

    # -- Apply filters --
    filtered = df.copy()

    if selected_sources is not None:
        filtered = filtered[
            filtered["source"].apply(
                lambda val: any(s.strip() in selected_sources for s in str(val).split(";"))
            )
        ]
    if name_filter:
        filtered = filtered[filtered["name"].str.contains(name_filter, case=False, na=False)]
    if affiliation_filter and "affiliation" in filtered.columns:
        filtered = filtered[filtered["affiliation"].str.contains(affiliation_filter, case=False, na=False)]
    if "citation_count" in filtered.columns and min_citations > 0:
        filtered = filtered[filtered["citation_count"].fillna(0) >= min_citations]
    if has_github and "github_url" in filtered.columns:
        filtered = filtered[filtered["github_url"].notna() & (filtered["github_url"] != "")]

    st.write(f"Showing {len(filtered)} of {len(df)} researchers")
    st.caption("Tip: links in the table below may not open reliably due to browser security restrictions. Select a researcher below the table for working GitHub/LinkedIn buttons.")

    # -- Main table --
    display_cols = [c for c in [
        "name", "source", "affiliation", "paper_count", "h_index",
        "citation_count", "github_url", "linkedin_search_url",
    ] if c in filtered.columns]

    st.dataframe(
        filtered[display_cols].sort_values(
            by="citation_count" if "citation_count" in display_cols else display_cols[0],
            ascending=False,
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "github_url": st.column_config.LinkColumn("GitHub"),
            "linkedin_search_url": st.column_config.LinkColumn("LinkedIn Search"),
            "citation_count": st.column_config.NumberColumn("Citations"),
            "h_index": st.column_config.NumberColumn("H-Index"),
            "paper_count": st.column_config.NumberColumn("Papers"),
        },
    )

    # -- Detail view for one author --
    st.subheader("Researcher detail")
    if len(filtered) > 0:
        selected = st.selectbox("Pick a researcher", filtered["name"].tolist())
        row = filtered[filtered["name"] == selected].iloc[0]

        # Rendered as plain HTML links rather than st.link_button -- Streamlit's
        # link_button adds a layer of JS handling around the click, and that
        # extra step is what triggers Google's strict anti-framing check on a
        # normal click (this is also why Ctrl/Cmd+click worked around it --
        # that bypasses JS and tells the browser to open a new tab directly).
        # A plain <a target="_blank"> tag doesn't have that extra step.
        col1, col2 = st.columns(2)
        with col1:
            gh = row.get("github_url", "")
            if isinstance(gh, str) and gh.strip():
                st.markdown(
                    f'<a href="{gh}" target="_blank" rel="noopener noreferrer">'
                    f'<button style="width:100%;padding:0.5em;border-radius:6px;'
                    f'border:1px solid #ccc;background:#f0f2f6;cursor:pointer;">'
                    f'Open GitHub</button></a>',
                    unsafe_allow_html=True,
                )
        with col2:
            li = row.get("linkedin_search_url", "")
            if isinstance(li, str) and li.strip():
                st.markdown(
                    f'<a href="{li}" target="_blank" rel="noopener noreferrer">'
                    f'<button style="width:100%;padding:0.5em;border-radius:6px;'
                    f'border:1px solid #ccc;background:#f0f2f6;cursor:pointer;">'
                    f'Search LinkedIn</button></a>',
                    unsafe_allow_html=True,
                )

        st.json(row.dropna().to_dict())
    else:
        st.info("No researchers match the current filters.")


if __name__ == "__main__":
    main()
