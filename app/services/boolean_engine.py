def generate_queries(filters):
    genres=filters.get("genres") or ["author"]
    states=[filters.get("state")] if filters.get("state") not in (None,"All States","Unknown") else [""]
    platforms=filters.get("platforms") or ["All platforms"]
    synonyms=filters.get("synonyms") or ["indie author"]
    sites={"X/Twitter":"x.com","Facebook":"facebook.com","LinkedIn":"linkedin.com","Reddit":"reddit.com","Substack":"substack.com","Medium":"medium.com","All platforms":None}
    qs=[]
    for g in genres:
      for s in synonyms[:4]:
       siteparts=[sites[p] for p in platforms if p in sites and sites[p]] or [None]
       for domain in siteparts:
        bits=[f'"{s}"',f'"{g}"']
        if states[0]: bits.append(f'"{states[0]}"')
        qs.append((f"site:{domain} " if domain else "")+" ".join(bits))
    return list(dict.fromkeys(qs))[:30]
