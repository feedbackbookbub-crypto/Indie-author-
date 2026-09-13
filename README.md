# Indie Author Lead Generator V2

Runnable FastAPI MVP for automated author discovery. It generates provider-compatible Boolean queries, uses mock search data by default, extracts and deduplicates author candidates, verifies books through Open Library, filters years/genres, scores leads, and exports CSV/XLSX.

## Run
```bash
python -m venv venv
# Windows: venv\Scripts\activate; macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env  # Windows; use cp on macOS/Linux
python run.py
```
Open http://127.0.0.1:8000.

Set SEARCH_API_PROVIDER and SEARCH_API_KEY for a compatible provider. External integrations remain modular and safe: unavailable services return NOT_CHECKED rather than fabricated data.
