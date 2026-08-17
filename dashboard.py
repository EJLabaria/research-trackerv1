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

# Toggle the Cypher (password gate for emails / full row count) on or off.
# Set to False to temporarily hide the password field entirely -- flip
# back to True whenever you want it active again.
ENABLE_CYPHER = False


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

    # Email column is only ever included in what gets sent to the browser
    # if this password matches -- unauthenticated visitors never receive
    # the email data at all, not even hidden in the page somewhere.
    #
    # When ENABLE_CYPHER is False, everything is unlocked automatically
    # (no password needed, no row cap) -- used for showcasing the full
    # dashboard temporarily. Flip ENABLE_CYPHER back to True to restore
    # the exact same password-gated behavior as before.
    show_emails = not ENABLE_CYPHER
    if ENABLE_CYPHER and "email" in df.columns:
        admin_password = st.sidebar.text_input("Enter the Cypher (to see full data)", type="password")
        correct_password = st.secrets.get("ADMIN_PASSWORD", None)
        if correct_password and admin_password == correct_password:
            show_emails = True
        elif admin_password:
            st.sidebar.error("Incorrect password")

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

    has_email = False
    exclude_flagged = False
    if show_emails:
        has_email = st.sidebar.checkbox("Has email only")
        exclude_flagged = st.sidebar.checkbox("Hide flagged-for-review emails")

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
    if has_email and "email" in filtered.columns:
        filtered = filtered[filtered["email"].notna() & (filtered["email"] != "")]
    if exclude_flagged and "email_needs_manual_review" in filtered.columns:
        filtered = filtered[filtered["email_needs_manual_review"] != "yes"]

    # Limit how many rows public (non-Cypher) viewers can see. Applied
    # after all other filters, sorted by citation count first so the
    # most notable people are the ones shown in the limited public view.
    PUBLIC_ROW_LIMIT = 75
    total_matching = len(filtered)
    if not show_emails and total_matching > PUBLIC_ROW_LIMIT:
        sort_col = "citation_count" if "citation_count" in filtered.columns else filtered.columns[0]
        filtered = filtered.sort_values(by=sort_col, ascending=False).head(PUBLIC_ROW_LIMIT)
        st.info(f"Showing top {PUBLIC_ROW_LIMIT} of {total_matching} researchers. Enter the Cypher in the sidebar to see all.")
    else:
        st.write(f"Showing {len(filtered)} of {len(df)} researchers")

    # -- Main table --
    # Rendered as a plain HTML table (not st.dataframe) so that GitHub and
    # LinkedIn links are genuine, un-wrapped <a> tags on the page. Streamlit's
    # interactive st.dataframe renders through its own internal grid
    # component, and links clicked from inside it get treated the same as a
    # link inside any other embedded frame -- which is exactly what Google's
    # search page blocks, regardless of click type. A plain HTML table has
    # no such wrapping, so its links behave like any normal link on any
    # normal webpage.
    #
    # Trade-off: this table isn't click-to-sort by column the way
    # st.dataframe is. The sidebar filters and the default citation-count
    # sort below make up for most of that.
    display_cols = [c for c in [
        "name", "source", "affiliation", "paper_count", "h_index",
        "citation_count", "github_url", "linkedin_search_url",
    ] if c in filtered.columns]
    if show_emails and "email" in filtered.columns:
        # Inserted after citation_count, before github_url, matching the
        # original column order -- only happens when the password matched.
        insert_at = display_cols.index("github_url") if "github_url" in display_cols else len(display_cols)
        display_cols.insert(insert_at, "email")

    display_labels = {
        "name": "Name", "source": "Source", "affiliation": "Affiliation",
        "paper_count": "Papers", "h_index": "H-Index", "citation_count": "Citations",
        "email": "Email", "github_url": "GitHub", "linkedin_search_url": "LinkedIn Search",
    }

    table_df = filtered[display_cols].sort_values(
        by="citation_count" if "citation_count" in display_cols else display_cols[0],
        ascending=False,
    ).copy()

    if "github_url" in table_df.columns:
        table_df["github_url"] = table_df["github_url"].apply(
            lambda u: f'<a href="{u}" target="_blank" rel="noopener noreferrer">GitHub</a>' if isinstance(u, str) and u.strip() else ""
        )
    if "linkedin_search_url" in table_df.columns:
        table_df["linkedin_search_url"] = table_df["linkedin_search_url"].apply(
            lambda u: f'<a href="{u}" target="_blank" rel="noopener noreferrer">Search</a>' if isinstance(u, str) and u.strip() else ""
        )
    if "email" in table_df.columns:
        # Show a small warning marker next to emails flagged as a possible
        # name mismatch, so it's visible right in the table, not just in
        # the raw CSV.
        review_flags = filtered.loc[table_df.index, "email_needs_manual_review"] if "email_needs_manual_review" in filtered.columns else None
        def format_email(idx):
            val = table_df.at[idx, "email"]
            if not isinstance(val, str) or not val.strip():
                return ""
            if review_flags is not None and review_flags.get(idx) == "yes":
                return f'{val} <span title="Commit author name did not match -- verify before using" style="color:#E07B00;">⚠️</span>'
            return val
        table_df["email"] = [format_email(idx) for idx in table_df.index]

    table_df = table_df.rename(columns=display_labels)


    html_table = table_df.to_html(escape=False, index=False, na_rep="")
    st.markdown(
        """
        <style>
        .researcher-table-wrap { max-height: 600px; overflow-y: auto; overflow-x: auto; }
        .researcher-table-wrap table { width: max-content; min-width: 100%; border-collapse: collapse; font-size: 0.85em; }
        .researcher-table-wrap th { background-color: #2E4057; color: white; text-align: left;
            padding: 8px; position: sticky; top: 0; }
        .researcher-table-wrap td { padding: 6px 8px; border-bottom: 1px solid #eee; }
        .researcher-table-wrap tr:nth-child(even) { background-color: #F8F9FB; }
        .researcher-table-wrap a { color: #FF4B4B; text-decoration: none; font-weight: 600; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="researcher-table-wrap">{html_table}</div>', unsafe_allow_html=True)

    # -- Detail view for one author --
    st.subheader("Researcher detail")
    if len(filtered) > 0:
        selected = st.selectbox("Pick a researcher", filtered["name"].tolist())
        row = filtered[filtered["name"] == selected].iloc[0]

        # st.link_button, not a plain HTML link -- Ctrl/Cmd+click reliably
        # works with this version; a plain <a> tag made things worse, not
        # better, so reverted back to this after testing both.
        col1, col2 = st.columns(2)
        with col1:
            gh = row.get("github_url", "")
            if isinstance(gh, str) and gh.strip():
                st.link_button("Open GitHub", gh)
        with col2:
            li = row.get("linkedin_search_url", "")
            if isinstance(li, str) and li.strip():
                st.link_button("Search LinkedIn", li)

        st.json(row.dropna().to_dict())
    else:
        st.info("No researchers match the current filters.")


if __name__ == "__main__":
    main()