import asyncio
import io
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Make the repository root importable when Streamlit runs this file.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.boolean_engine import generate_queries
from app.services.search_engine import MockSearchProvider
from app.services.author_extractor import extract_authors
from app.services.openlibrary import verify_author
from app.services.lead_scoring import score_lead


def run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


st.set_page_config(
    page_title="Indie Author Lead Generator V2",
    page_icon="✍️",
    layout="wide",
)

st.title("✍️ Indie Author Lead Generator V2")
st.caption("Automated author discovery, book verification, and lead scoring")

with st.sidebar:
    st.header("Search filters")

    platforms = st.multiselect(
        "Platforms",
        ["All platforms", "X/Twitter", "Facebook", "LinkedIn", "Reddit", "Substack", "Medium"],
        default=["All platforms"],
    )

    genres = st.multiselect(
        "Genres",
        [
            "Romance", "Contemporary Romance", "Historical Romance",
            "Fantasy", "Mystery", "Thriller", "Science Fiction",
            "Young Adult", "Self-Help", "Business",
        ],
        default=["Romance"],
    )

    synonyms = st.multiselect(
        "Independent-author synonyms",
        [
            "indie author", "independent author", "self-published author",
            "KDP author", "indie novelist", "author-publisher",
        ],
        default=["indie author", "self-published author"],
    )

    state = st.selectbox(
        "State",
        ["All States", "Unknown", "Texas", "California", "Florida", "New York"],
    )

    years = st.multiselect(
        "Publication years",
        list(range(2026, 2009, -1)),
        default=[2026],
    )

    amount = st.selectbox(
        "Amount of results per query",
        [10, 25, 50, 100],
        index=1,
    )

filters = {
    "platforms": platforms,
    "genres": genres,
    "synonyms": synonyms,
    "state": state,
    "years": years,
    "amount": amount,
}

queries = generate_queries(filters)
st.subheader("Search preview")
st.write(f"Generated queries: **{len(queries)}**")

with st.expander("View generated queries"):
    for query in queries:
        st.code(query)

if st.button("START AUTOMATIC SEARCH", type="primary"):
    progress = st.progress(0)
    status = st.empty()
    results = []
    provider = MockSearchProvider()

    status.info("Collecting search results...")
    for index, query in enumerate(queries):
        results.extend(run_async(provider.search(query, min(amount, 10))))
        progress.progress((index + 1) / max(len(queries), 1))

    status.info("Extracting and deduplicating authors...")
    authors = extract_authors(results)
    rows = []

    for index, author in enumerate(authors):
        status.info(f"Checking Open Library for {author['name']}...")
        books = run_async(verify_author(author["name"], years, genres))
        lead_score, category = score_lead(author, books)

        rows.append({
            "Author": author.get("name", "UNKNOWN"),
            "Website": author.get("website", ""),
            "State": author.get("state", "UNKNOWN"),
            "Indie Score": author.get("indie_score", 0),
            "Indie Status": author.get("indie_status", "UNCERTAIN"),
            "Indie Evidence": author.get("indie_evidence", ""),
            "Books": len(books),
            "Latest Book": books[0].get("title", "UNKNOWN") if books else "UNKNOWN",
            "Email": author.get("email", ""),
            "Email Status": author.get("email_status", "NOT_CHECKED"),
            "Lead Score": lead_score,
            "Category": category,
        })
        progress.progress((index + 1) / max(len(authors), 1))

    status.success(
        f"Completed: {len(queries)} queries, {len(results)} results, and {len(rows)} authors."
    )

    if rows:
        dataframe = pd.DataFrame(rows)
        st.subheader("Author leads")
        st.dataframe(dataframe, use_container_width=True, hide_index=True)

        st.download_button(
            "Export CSV",
            dataframe.to_csv(index=False).encode("utf-8"),
            "author_leads.csv",
            "text/csv",
        )

        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name="Author Leads")

        st.download_button(
            "Export Excel",
            excel_buffer.getvalue(),
            "author_leads.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.warning("No author candidates were found.")
