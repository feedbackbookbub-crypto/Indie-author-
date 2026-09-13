import asyncio
import io
import re
from datetime import datetime

import httpx
import pandas as pd
import streamlit as st


def generate_queries(platforms, genres, synonyms, state):
    sites = {
        "X/Twitter": "x.com", "Facebook": "facebook.com",
        "LinkedIn": "linkedin.com", "Reddit": "reddit.com",
        "Substack": "substack.com", "Medium": "medium.com"
    }
    domains = [sites[p] for p in platforms if p in sites]
    queries = []
    for genre in genres or ["author"]:
        for synonym in synonyms or ["indie author"]:
            parts = [f'"{synonym}"', f'"{genre}"']
            if state not in ("All States", "Unknown", ""):
                parts.append(f'"{state}"')
            prefix = "" if not domains else "site:" + domains[len(queries) % len(domains)] + " "
            queries.append(prefix + " ".join(parts))
    return list(dict.fromkeys(queries))[:30]


async def mock_search(query, limit):
    now = datetime.utcnow().isoformat()
    return [{
        "title": "Jane Smith | Independent Romance Author",
        "url": "https://example.com/jane-smith",
        "domain": "example.com", "snippet": "Jane Smith is a self-published romance author with a 2026 book.",
        "position": i + 1, "query": query, "timestamp": now
    } for i in range(min(limit, 2))]


def extract_authors(results):
    found = {}
    for result in results:
        text = result.get("title", "") + " " + result.get("snippet", "")
        match = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", text)
        if match:
            name = match.group(1).strip()
            key = " ".join(name.lower().split())
            found.setdefault(key, {
                "Author": name, "Website": result.get("url", ""),
                "State": "UNKNOWN", "Indie Score": 85,
                "Indie Status": "LIKELY",
                "Indie Evidence": "Independent or self-published wording found.",
                "Email": "", "Email Status": "NOT_CHECKED"
            })
    return list(found.values())


async def openlibrary_books(author, years):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://openlibrary.org/search.json",
                params={"author": author, "limit": 20}
            )
            response.raise_for_status()
            data = response.json()
        wanted = set(years)
        books = []
        for doc in data.get("docs", []):
            for year in doc.get("publish_year", []):
                if not wanted or year in wanted:
                    books.append({
                        "Title": doc.get("title", "UNKNOWN"),
                        "Publication Year": year,
                        "ISBN": (doc.get("isbn") or [""])[0],
                        "Genre": (doc.get("subject") or ["UNKNOWN"])[0]
                    })
        return books[:10]
    except Exception:
        return []


def score_lead(author, books):
    score = 25 + (20 if books else 0) + (5 if author.get("Website") else 0)
    score += round(author.get("Indie Score", 0) * 0.25)
    score = min(100, score)
    category = ("HOT" if score >= 90 else "STRONG" if score >= 75 else
                "POTENTIAL" if score >= 60 else "WEAK" if score >= 40 else "LOW")
    return score, category


st.set_page_config(page_title="Indie Author Lead Generator V2", page_icon="✍️", layout="wide")
st.title("✍️ Indie Author Lead Generator V2")
st.caption("Automated author discovery, Open Library verification, and lead scoring")

with st.sidebar:
    st.header("Search filters")
    platforms = st.multiselect("Platforms", ["All platforms", "X/Twitter", "Facebook", "LinkedIn", "Reddit", "Substack", "Medium"], ["All platforms"])
    genres = st.multiselect("Genres", ["Romance", "Contemporary Romance", "Historical Romance", "Fantasy", "Mystery", "Thriller", "Science Fiction", "Young Adult", "Self-Help", "Business"], ["Romance"])
    synonyms = st.multiselect("Independent-author synonyms", ["indie author", "independent author", "self-published author", "KDP author", "indie novelist", "author-publisher"], ["indie author", "self-published author"])
    state = st.selectbox("State", ["All States", "Unknown", "Texas", "California", "Florida", "New York"])
    years = st.multiselect("Publication years", list(range(2026, 2009, -1)), [2026])
    amount = st.selectbox("Amount of results per query", [10, 25, 50, 100], index=1)

queries = generate_queries(platforms, genres, synonyms, state)
st.subheader("Search preview")
st.write(f"Generated queries: **{len(queries)}**")
with st.expander("View generated queries"):
    for query in queries:
        st.code(query)

if st.button("START AUTOMATIC SEARCH", type="primary"):
    progress = st.progress(0)
    status = st.empty()
    results = []
    for i, query in enumerate(queries):
        results.extend(asyncio.run(mock_search(query, min(amount, 10))))
        progress.progress((i + 1) / max(len(queries), 1))
    status.info("Extracting authors and checking Open Library...")
    authors = extract_authors(results)
    rows = []
    for i, author in enumerate(authors):
        books = asyncio.run(openlibrary_books(author["Author"], years))
        lead_score, category = score_lead(author, books)
        row = {**author, "Books": len(books), "Latest Book": books[0]["Title"] if books else "UNKNOWN", "Lead Score": lead_score, "Category": category}
        rows.append(row)
        progress.progress((i + 1) / max(len(authors), 1))
    status.success(f"Completed: {len(results)} results and {len(rows)} author candidates.")
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Export CSV", df.to_csv(index=False).encode(), "author_leads.csv", "text/csv")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Author Leads")
        st.download_button("Export Excel", buffer.getvalue(), "author_leads.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("No author candidates were found.")
