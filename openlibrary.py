import httpx
async def verify_author(name, years, genres):
 try:
  async with httpx.AsyncClient(timeout=10) as c:
   r=await c.get("https://openlibrary.org/search.json",params={"author":name,"limit":20}); data=r.json()
  wanted=set(years); books=[]
  for d in data.get("docs",[]):
   for y in d.get("publish_year",[]):
    if not wanted or y in wanted:
     books.append({"title":d.get("title","UNKNOWN"),"publication_year":y,"genre":(d.get("subject") or ["UNKNOWN"])[0],"isbn":(d.get("isbn") or [""])[0]})
  return books[:10]
 except Exception: return []
