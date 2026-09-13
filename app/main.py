from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from .services.boolean_engine import generate_queries
from .services.search_engine import MockSearchProvider
from .services.author_extractor import extract_authors
from .services.openlibrary import verify_author
from .services.lead_scoring import score_lead
import io, csv
app=FastAPI(title="Indie Author Lead Generator V2")
templates=Jinja2Templates(directory="app/templates")
class SearchRequest(BaseModel):
    genres:list[str]=["Romance"]; years:list[int]=[2026]; state:str="All States"; platforms:list[str]=["All platforms"]; synonyms:list[str]=["indie author"]; email_extensions:list[str]=[]; amount:int=25
@app.get("/", response_class=HTMLResponse)
async def home(request:Request): return templates.TemplateResponse("dashboard.html", {"request":request})
@app.post("/api/search")
async def search(payload:SearchRequest):
    queries=generate_queries(payload.model_dump()); results=[]
    provider=MockSearchProvider()
    for q in queries:
        results.extend(await provider.search(q, min(payload.amount,10)))
    authors=extract_authors(results)
    leads=[]
    for a in authors:
        books=await verify_author(a["name"], payload.years, payload.genres)
        a["books"]=books; a["lead_score"],a["category"]=score_lead(a,books)
        leads.append(a)
    return {"queries":queries,"results_count":len(results),"authors":leads}
@app.post("/api/export")
async def export(payload:list[dict]):
    out=io.StringIO(); fields=["name","website","state","indie_score","indie_status","email","lead_score","category"]
    w=csv.DictWriter(out,fieldnames=fields); w.writeheader()
    for x in payload: w.writerow({k:x.get(k,"") for k in fields})
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=leads.csv"})
