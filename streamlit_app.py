
import io
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
import pandas as pd
import streamlit as st


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Indie Author Lead Generator",
    page_icon="✍️",
    layout="wide",
)

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
    "Romance", "Contemporary Romance", "Historical Romance",
    "Paranormal Romance", "Fantasy", "Epic Fantasy",
    "Urban Fantasy", "Science Fiction", "Mystery",
    "Cozy Mystery", "Thriller", "Psychological Thriller",
    "Crime", "Horror", "Suspense", "Literary Fiction",
    "Contemporary Fiction", "Historical Fiction",
    "Women's Fiction", "Young Adult", "New Adult",
    "Middle Grade", "Children's Books", "Adventure",
    "Western", "Christian Fiction", "Inspirational Fiction",
    "LGBTQ+ Fiction", "Poetry", "Drama", "Comedy", "Humor",
    "Dystopian", "Speculative Fiction", "Magical Realism",
    "Short Stories", "Novellas", "Biography", "Memoir",
    "Autobiography", "Self-Help", "Business",
    "Entrepreneurship", "Finance", "Marketing",
    "Personal Development", "Health & Fitness", "Cooking",
    "Travel", "Religion & Spirituality", "Education",
    "Technology", "Science", "History", "True Crime",
    "Art", "Music", "Crafts", "Parenting", "Reference",
]

AUTHOR_TERMS = [
    "indie author",
    "independent author",
    "self-published author",
    "self published author",
    "self-publishing author",
    "KDP author",
    "indie novelist",
    "independent novelist",
    "self-published novelist",
    "author-publisher",
    "independently published",
    "small press author",
    "hybrid author",
    "author-owned publisher",
    "IngramSpark author",
    "Draft2Digital author",
]

STATES = ["All States", "Unknown"] + [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California",
    "Colorado", "Connecticut", "Delaware", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas",
    "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts",
    "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana",
    "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota",
    "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
    "South Carolina", "South Dakota", "Tennessee", "Texas",
    "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
    "Wisconsin", "Wyoming",
]

EMAIL_EXTENSIONS = [
    "All extensions", "@gmail.com", "@yahoo.com", "@outlook.com",
    "@hotmail.com", "@icloud.com", "@proton.me",
    "@protonmail.com", "@aol.com", "@live.com", "@me.com",
    "@mail.com", "@zoho.com", "@fastmail.com", "Other",
]


# ============================================================
# API CONFIGURATION
# ============================================================

def get_secret(name):
    """Read a secret from Streamlit secrets or environment variables."""
    try:
        value = st.secrets.get(name)
        if value:
            return str(value).strip()
    except Exception:
        pass

    return os.getenv(name, "").strip()


GOOGLE_API_KEY = get_secret("AIzaSyD7g6oJMAI4CxyoM0oY8M7TVKxCDqfzbvE")
GOOGLE_CX = get_secret("e639296ccd4574416")

GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
OPEN_LIBRARY_URL = "https://openlibrary.org/search.json"


# ============================================================
# SEARCH QUERY GENERATION
# ============================================================

def generate_queries(platforms, genres, terms, state, extensions):
    selected_domains = [
        PLATFORMS[p]
        for p in platforms
        if PLATFORMS.get(p)
    ]

    # No domain restriction means search across the web.
    if not selected_domains:
        selected_domains = [None]

    queries = []

    for genre in genres or ["author"]:
        for term in terms or ["indie author"]:
            for domain in selected_domains:
                pieces = [
                    f'"{term}"',
                    f'"{genre}"',
                ]

                if state not in ("All States", "Unknown"):
                    pieces.append(f'"{state}"')

                # Search for public contact-address patterns only.
                if extensions and "All extensions" not in extensions:
                    email_terms = [
                        f'"{extension}"'
                        for extension in extensions
                        if extension != "Other"
                    ]

                    if email_terms:
                        pieces.append(
                            "(" + " OR ".join(email_terms) + ")"
                        )

                prefix = f"site:{domain} " if domain else ""
                queries.append(prefix + " ".join(pieces))

    # Google Custom Search returns up to 10 results per request.
    return list(dict.fromkeys(queries))[:30]


# ============================================================
# GOOGLE CUSTOM SEARCH JSON API
# ============================================================

def google_search(query, limit=10):
    """
    Fetch real search results from Google Custom Search JSON API.

    Requires:
        GOOGLE_API_KEY
        GOOGLE_CX
    """
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        raise RuntimeError(
            "Google API credentials are missing. "
            "Configure GOOGLE_API_KEY and GOOGLE_CX."
        )

    limit = max(1, min(int(limit), 10))

    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CX,
        "q": query,
        "num": limit,
        "safe": "active",
        "hl": "en",
    }

    try:
        response = httpx.get(
            GOOGLE_SEARCH_URL,
            params=params,
            timeout=30,
        )
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Could not connect to Google: {exc}"
        ) from exc

    if response.status_code != 200:
        try:
            error_data = response.json()
            error_message = (
                error_data.get("error", {}).get("message")
                or response.text[:300]
            )
        except Exception:
            error_message = response.text[:300]

        raise RuntimeError(
            f"Google API error ({response.status_code}): "
            f"{error_message}"
        )

    data = response.json()
    results = []

    for position, item in enumerate(data.get("items", []), start=1):
        url = item.get("link", "")
        domain = urlparse(url).netloc.lower()

        results.append({
            "title": item.get("title", ""),
            "url": url,
            "domain": domain,
            "snippet": item.get("snippet", ""),
            "position": position,
            "query": query,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
        })

    return results


# ============================================================
# AUTHOR EXTRACTION
# ============================================================

def clean_name(name):
    return re.sub(r"\s+", " ", name).strip(" -|,.")


def extract_authors(results):
    """
    Extract likely author names from titles and snippets.

    This is a heuristic. Google results do not guarantee that
    every extracted name is a real author.
    """
    authors = {}

    name_patterns = [
        r"\bby\s+([A-Z][A-Za-z'’-]+"
        r"(?:\s+[A-Z][A-Za-z'’-]+){1,3})",
        r"\b([A-Z][A-Za-z'’-]+"
        r"(?:\s+[A-Z][A-Za-z'’-]+){1,3})"
        r"\s*\|\s*(?:indie|independent|self-published)",
    ]

    for result in results:
        text = (
            result.get("title", "")
            + " "
            + result.get("snippet", "")
        )

        match = None

        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                break

        if not match:
            continue

        name = clean_name(match.group(1))
        key = name.lower()

        if len(name.split()) < 2:
            continue

        if key not in authors:
            authors[key] = {
                "Author": name,
                "Website": result.get("url", ""),
                "State": "UNKNOWN",
                "Indie Status": "LIKELY",
                "Indie Score": 85,
                "Indie Evidence": (
                    "Independent-author wording detected "
                    "in a Google search result."
                ),
                "Email": "",
                "Email Status": "NOT_CHECKED",
            }

    return list(authors.values())


# ============================================================
# OPEN LIBRARY LOOKUP
# ============================================================

def lookup_openlibrary(author, years):
    try:
        response = httpx.get(
            OPEN_LIBRARY_URL,
            params={
                "author": author,
                "limit": 50,
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

    except (httpx.HTTPError, ValueError):
        return []

    wanted_years = set(years or [])
    books = []

    for doc in data.get("docs", []):
        title = doc.get("title", "UNKNOWN")
        subjects = doc.get("subject", []) or []
        isbn_list = doc.get("isbn", []) or []
        publishers = doc.get("publisher", []) or []

        for year in doc.get("publish_year", []) or []:
            if wanted_years and year not in wanted_years:
                continue

            books.append({
                "Book Title": title,
                "Publication Year": year,
                "Genre": subjects[0] if subjects else "UNKNOWN",
                "ISBN": isbn_list[0] if isbn_list else "",
                "Publisher": publishers[0] if publishers else "",
            })

    # Sort by publication year, newest first.
    books.sort(
        key=lambda book: book["Publication Year"],
        reverse=True,
    )

    return books[:15]


# ============================================================
# LEAD SCORING
# ============================================================

def calculate_lead_score(author, books):
    score = 25

    score += 20 if books else 0
    score += 5 if author.get("Website") else 0
    score += (
        25
        if author.get("Indie Score", 0) >= 80
        else 15
    )
    score += 20 if author.get("Email") else 0

    score = min(100, score)

    if score >= 90:
        category = "HOT"
    elif score >= 75:
        category = "STRONG"
    elif score >= 60:
        category = "POTENTIAL"
    elif score >= 40:
        category = "WEAK"
    else:
        category = "LOW"

    return score, category


# ============================================================
# STREAMLIT INTERFACE
# ============================================================

st.title("✍️ Indie Author Lead Generator")
st.caption(
    "Google Custom Search API + Open Library | Real search results"
)

if not GOOGLE_API_KEY or not GOOGLE_CX:
    st.warning(
        "Google API credentials are not configured. "
        "Add GOOGLE_API_KEY and GOOGLE_CX before searching."
    )

with st.sidebar:
    st.header("Search configuration")

    platforms = st.multiselect(
        "Platforms",
        list(PLATFORMS),
        default=["All platforms"],
    )

    genres = st.multiselect(
        "Genres",
        GENRES,
        default=["Romance"],
    )

    terms = st.multiselect(
        "Independent-author synonyms",
        AUTHOR_TERMS,
        default=[
            "indie author",
            "self-published author",
        ],
    )

    state = st.selectbox("State", STATES)

    years = st.multiselect(
        "Publication years",
        list(range(2026, 2009, -1)),
        default=[2026],
    )

    extensions = st.multiselect(
        "Email extensions",
        EMAIL_EXTENSIONS,
        default=["All extensions"],
    )

    amount = st.selectbox(
        "Results per Google query",
        [10, 25, 50, 100],
        index=1,
    )

queries = generate_queries(
    platforms,
    genres,
    terms,
    state,
    extensions,
)

st.subheader("Search preview")

col1, col2, col3 = st.columns(3)
col1.metric("Generated queries", len(queries))
col2.metric(
    "Maximum Google results",
    len(queries) * min(amount, 10),
)
col3.metric(
    "Selected email extensions",
    len(extensions),
)

with st.expander("View generated queries"):
    for query in queries:
        st.code(query)

if st.button(
    "START GOOGLE SEARCH",
    type="primary",
    disabled=not (GOOGLE_API_KEY and GOOGLE_CX),
):
    status = st.empty()
    progress = st.progress(0)
    results = []

    try:
        status.info("Collecting results from Google...")

        for index, query in enumerate(queries):
            results.extend(
                google_search(query, min(amount, 10))
            )

            progress.progress(
                (index + 1) / max(len(queries), 1)
            )

        # Deduplicate identical result URLs.
        unique_results = {}
        for result in results:
            unique_results[result["url"]] = result

        results = list(unique_results.values())

        status.info("Extracting author candidates...")
        authors = extract_authors(results)

        rows = []

        for index, author in enumerate(authors):
            status.info(
                f"Checking Open Library: {author['Author']}"
            )

            books = lookup_openlibrary(
                author["Author"],
                years,
            )

            lead_score, category = calculate_lead_score(
                author,
                books,
            )

            rows.append({
                **author,
                "Books": len(books),
                "Latest Book": (
                    books[0]["Book Title"]
                    if books
                    else "UNKNOWN"
                ),
                "Lead Score": lead_score,
                "Lead Category": category,
            })

            progress.progress(
                (index + 1) / max(len(authors), 1)
            )

        status.success(
            f"Completed: {len(results)} Google results "
            f"and {len(rows)} author candidates."
        )

        if rows:
            dataframe = pd.DataFrame(rows)

            st.subheader("Results")
            st.dataframe(
                dataframe,
                use_container_width=True,
                hide_index=True,
            )

            csv_bytes = dataframe.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                "Export CSV",
                csv_bytes,
                "author_leads.csv",
                "text/csv",
            )

            excel_buffer = io.BytesIO()

            with pd.ExcelWriter(
                excel_buffer,
                engine="openpyxl",
            ) as writer:
                dataframe.to_excel(
                    writer,
                    index=False,
                    sheet_name="Author Leads",
                )

            st.download_button(
                "Export Excel",
                excel_buffer.getvalue(),
                "author_leads.xlsx",
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet",
            )

        else:
            st.warning(
                "No author candidates were found. "
                "Try different genres or search terms."
            )

    except RuntimeError as exc:
        status.error(str(exc))

    except Exception as exc:
        status.error(
            f"Unexpected error: {type(exc).__name__}: {exc}"
        )
