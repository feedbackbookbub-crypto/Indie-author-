import asyncio
import io
import re
from datetime import datetime

import httpx
import pandas as pd
import streamlit as st

# -----------------------------
# Configuration
# -----------------------------
PLATFORMS = {
    "All platforms": None,
    "X / Twitter": "x.com",
    "Facebook": "facebook.com",
    "LinkedIn": "linkedin.com",
    "Reddit": "reddit.com",
    "Substack": "substack.com",
    "Medium": "medium.com",
    "Amazon": "amazon.com",
    "BookBub": "bookbub.com",
    "Goodreads": "goodreads.com",
    "Instagram": "instagram.com",
    "TikTok": "tiktok.com",
    "YouTube": "youtube.com",
    "Personal websites": None,
}

GENRES = [
    "Romance", "Contemporary Romance", "Historical Romance", "Paranormal Romance",
    "Fantasy", "Epic Fantasy", "Urban Fantasy", "Science Fiction", "Mystery",
    "Cozy Mystery", "Thriller", "Psychological Thriller", "Crime", "Horror",
    "Suspense", "Literary Fiction", "Contemporary Fiction", "Historical Fiction",
    "Women's Fiction", "Young Adult", "New Adult", "Middle Grade",
    "Children's Books", "Adventure", "Western", "Christian Fiction",
    "Inspirational Fiction", "LGBTQ+ Fiction", "Poetry", "Drama", "Comedy",
    "Humor", "Dystopian", "Speculative Fiction", "Magical Realism",
    "Short Stories", "Novellas", "Biography", "Memoir", "Autobiography",
    "Self-Help", "Business", "Entrepreneurship", "Finance", "Marketing",
    "Personal Development", "Health & Fitness", "Cooking", "Travel",
    "Religion & Spirituality", "Education", "Technology", "Science", "History",
    "True Crime", "Art", "Music", "Crafts", "Parenting", "Reference",
]

AUTHOR_TERMS = [
    "indie author", "independent author", "self-published author",
    "self published author", "self-publishing author", "KDP author",
    "indie novelist", "independent novelist", "self-published novelist",
    "author-publisher", "independently published", "small press author",
    "hybrid author", "author-owned publisher", "IngramSpark author",
    "Draft2Digital author",
]

STATES = ["All States", "Unknown"] + [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming",
]

EMAIL_EXTENSIONS = [
    "All extensions", "@gmail.com", "@yahoo.com", "@outlook.com",
    "@hotmail.com", "@icloud.com", "@proton.me", "@protonmail.com",
    "@aol.com", "@live.com", "@me.com", "@mail.com", "@zoho.com",
    "@fastmail.com", "Other",
]


def generate_queries(platforms, genres, terms, state, extensions):
    selected_domains = [PLATFORMS[p] for p in platforms if PLATFORMS.get(p)]
    if not selected_domains:
        selected_domains = [None]

    queries = []
    for genre in genres or ["author"]:
        for term in terms or ["indie author"]:
            for domain in selected_domains:
                pieces = [f'"{term}"', f'"{genre}"']
                if state not in ("All States", "Unknown"):
                    pieces.append(f'"{state}"')
                if extensions and "All extensions" not in extensions:
                    pieces.append("(" + " OR ".join(f'"{x}"' for x in extensions) + ")")
                prefix = f"site:{domain} " if domain else ""
                queries.append(prefix + " ".join(pieces))
    return list(dict.fromkeys(queries))[:30]


async def mock_search(query, limit):
    timestamp = datetime.utcnow().isoformat()
    return [{
        "title": "Jane Smith | Independent Romance Author",
        "url": "https://example.com/jane-smith",
        "domain": "example.com",
        "snippet": "Jane Smith is a self-published romance author with a 2026 book.",
        "position": index + 1, "query": query, "timestamp": timestamp,
    } for index in range(min(limit, 3))]


def extract_authors(results):
    authors = {}
    for result in results:
        text = result.get("title", "") + " " + result.get("snippet", "")
        match = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", text)
        if not match:
            continue
        name = match.group(1).strip()
        key = " ".join(name.lower().split())
        authors.setdefault(key, {
            "Author": name,
            "Website": result.get("url", ""),
            "State": "UNKNOWN",
            "Indie Status": "LIKELY",
            "Indie Score": 85,
            "Indie Evidence": "Self-published or independent-author wording detected.",
            "Email": "",
            "Email Status": "NOT_CHECKED",
        })
    return list(authors.values())


async def lookup_openlibrary(author, years, selected_genres):
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(
                "https://openlibrary.org/search.json",
                params={"author": author, "limit": 50},
            )
            response.raise_for_status()
            data = response.json()
        wanted_years = set(years)
        books = []
        for doc in data.get("docs", []):
            subjects = doc.get("subject", []) or []
            for year in doc.get("publish_year", []) or []:
                if wanted_years and year not in wanted_years:
                    continue
                books.append({
                    "Book Title": doc.get("title", "UNKNOWN"),
                    "Publication Year": year,
                    "Genre": subjects[0] if subjects else "UNKNOWN",
                    "ISBN": (doc.get("isbn") or [""])[0],
                    "Publisher": (doc.get("publisher") or [""])[0],
                })
        return books[:15]
    except Exception:
        return []


def calculate_lead_score(author, books):
    score = 25
    score += 20 if books else 0
    score += 5 if author.get("Website") else 0
    score += 25 if author.get("Indie Score", 0) >= 80 else 15
    score += 20 if author.get("Email") else 0
    score = min(100, score)
    category = ("HOT" if score >= 90 else "STRONG" if score >= 75 else
                "POTENTIAL" if score >= 60 else "WEAK" if score >= 40 else "LOW")
    return score, category


st.set_page_config(page_title="Indie Author Lead Generator V2", page_icon="✍️", layout="wide")
st.title("✍️ Indie Author Lead Generator V2")
st.caption("All-in-one Streamlit MVP — no services folder required")

with st.sidebar:
    st.header("Search configuration")
    platforms = st.multiselect("Platforms", list(PLATFORMS), ["All platforms"])
    genres = st.multiselect("Genres", GENRES, ["Romance"])
    terms = st.multiselect("Independent-author synonyms", AUTHOR_TERMS, ["indie author", "self-published author"])
    state = st.selectbox("State", STATES)
    years = st.multiselect("Publication years", list(range(2026, 2009, -1)), [2026])
    extensions = st.multiselect("Email extensions", EMAIL_EXTENSIONS, ["All extensions"])
    amount = st.selectbox("Amount of results", [10, 25, 50, 100], index=1)

queries = generate_queries(platforms, genres, terms, state, extensions)
st.subheader("Search preview")
col1, col2, col3 = st.columns(3)
col1.metric("Generated queries", len(queries))
col2.metric("Estimated search results", len(queries) * amount)
col3.metric("Selected email extensions", len(extensions))

with st.expander("View generated queries"):
    for query in queries:
        st.code(query)

if st.button("START AUTOMATIC SEARCH", type="primary"):
    status = st.empty()
    progress = st.progress(0)
    results = []

    status.info("Collecting search results...")
    for index, query in enumerate(queries):
        results.extend(asyncio.run(mock_search(query, min(amount, 10))))
        progress.progress((index + 1) / max(len(queries), 1))

    status.info("Extracting and deduplicating authors...")
    authors = extract_authors(results)
    rows = []

    for index, author in enumerate(authors):
        status.info(f"Checking Open Library: {author['Author']}")
        books = asyncio.run(lookup_openlibrary(author["Author"], years, genres))
        lead_score, category = calculate_lead_score(author, books)
        rows.append({
            **author,
            "Books": len(books),
            "Latest Book": books[0]["Book Title"] if books else "UNKNOWN",
            "Lead Score": lead_score,
            "Lead Category": category,
        })
        progress.progress((index + 1) / max(len(authors), 1))

    status.success(f"Completed: {len(results)} results and {len(rows)} author candidates.")

    if rows:
        dataframe = pd.DataFrame(rows)
        st.subheader("Results")
        st.dataframe(dataframe, use_container_width=True, hide_index=True)

        csv_bytes = dataframe.to_csv(index=False).encode("utf-8")
        st.download_button("Export CSV", csv_bytes, "author_leads.csv", "text/csv")

        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name="Author Leads")
        st.download_button(
            "Export Excel", excel_buffer.getvalue(), "author_leads.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.warning("No author candidates were found.")
