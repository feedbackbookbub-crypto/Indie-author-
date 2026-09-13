import asyncio
import io

import pandas as pd
import streamlit as st

from services.boolean_engine import generate_queries
from services.search_engine import MockSearchProvider
from services.author_extractor import extract_authors
from services.openlibrary import verify_author
from services.lead_scoring import score_lead


st.set_page_config(
    page_title="Indie Author Lead Generator V2",
    page_icon="✍️",
    layout="wide",
)

st.title("✍️ Indie Author Lead Generator V2")
st.caption("Automated author discovery and book verification")

st.sidebar.header("Search filters")

platforms = st.sidebar.multiselect(
    "Platforms",
    [
        "All platforms",
        "X/Twitter",
        "Facebook",
        "LinkedIn",
        "Reddit",
        "Substack",
        "Medium",
    ],
    default=["All platforms"],
)

genres = st.sidebar.multiselect(
    "Genres",
    [
        "Romance",
        "Contemporary Romance",
        "Fantasy",
        "Mystery",
        "Thriller",
        "Science Fiction",
        "Young Adult",
        "Self-Help",
        "Business",
    ],
    default=["Romance"],
)

synonyms = st.sidebar.multiselect(
    "Independent-author synonyms",
    [
        "indie author",
        "independent author",
        "self-published author",
        "KDP author",
        "indie novelist",
        "author-publisher",
    ],
    default=["indie author", "self-published author"],
)

state = st.sidebar.selectbox(
    "State",
    [
        "All States",
        "Unknown",
        "Texas",
        "California",
        "Florida",
        "New York",
    ],
)

years = st.sidebar.multiselect(
    "Publication years",
    list(range(2026, 2009, -1)),
    default=[2026],
)

amount = st.sidebar.selectbox(
    "Amount of results per query",
    [10, 25, 50, 100],
    index=1,
)

search_filters = {
    "platforms": platforms,
    "genres": genres,
    "synonyms": synonyms,
    "state": state,
    "years": years,
    "amount": amount,
}

queries = generate_queries(search_filters)

st.subheader("Search preview")
st.write(f"Generated queries: **{len(queries)}**")

with st.expander("View generated queries"):
    for query in queries:
        st.code(query)

if st.button("START AUTOMATIC SEARCH", type="primary"):
    progress = st.progress(0)
    status = st.empty()

    status.info("Collecting search results...")
    provider = MockSearchProvider()
    results = []

    for index, query in enumerate(queries):
        batch = asyncio.run(provider.search(query, min(amount, 10)))
        results.extend(batch)
        progress.progress((index + 1) / max(len(queries), 1))

    status.info("Extracting and deduplicating authors...")
    authors = extract_authors(results)

    leads = []

    for index, author in enumerate(authors):
        status.info(f"Checking Open Library: {author['name']}")

        books = asyncio.run(
            verify_author(
                author["name"],
                years,
                genres,
            )
        )

        lead_score, category = score_lead(author, books)

        author["books"] = books
        author["lead_score"] = lead_score
        author["category"] = category

        leads.append(author)

        progress.progress((index + 1) / max(len(authors), 1))

    status.success(
        f"Completed: {len(results)} results and {len(leads)} author candidates."
    )

    if leads:
        table_rows = []

        for lead in leads:
            table_rows.append(
                {
                    "Author": lead.get("name", "UNKNOWN"),
                    "State": lead.get("state", "UNKNOWN"),
                    "Indie Score": lead.get("indie_score", 0),
                    "Books": len(lead.get("books", [])),
                    "Lead Score": lead.get("lead_score", 0),
                    "Category": lead.get("category", "LOW"),
                    "Email Status": lead.get("email_status", "NOT_CHECKED"),
                }
            )

        dataframe = pd.DataFrame(table_rows)

        st.subheader("Results")
        st.dataframe(
            dataframe,
            use_container_width=True,
            hide_index=True,
        )

        csv_data = dataframe.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Export CSV",
            data=csv_data,
            file_name="author_leads.csv",
            mime="text/csv",
        )

        excel_buffer = io.BytesIO()

        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            dataframe.to_excel(
                writer,
                index=False,
                sheet_name="Author Leads",
            )

        st.download_button(
            "Export Excel",
            data=excel_buffer.getvalue(),
            file_name="author_leads.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
    else:
        st.warning("No author candidates were found.")
