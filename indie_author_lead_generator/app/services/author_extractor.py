import re
def extract_authors(results):
 out={}
 for r in results:
  m=re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", r["title"])
  if not m: continue
  name=m.group(1); key=" ".join(name.lower().split())
  out.setdefault(key,{"name":name,"website":r.get("url"),"state":"UNKNOWN","indie_score":85,"indie_status":"LIKELY","indie_evidence":"Self-published/independent language found in search snippet.","email":"","email_status":"NOT_CHECKED"})
 return list(out.values())
