def score_lead(author, books):
 score=min(100,25+20*bool(books)+5*bool(author.get("website"))+author.get("indie_score",0)*.25)
 score=int(score); return score, "HOT" if score>=90 else "STRONG" if score>=75 else "POTENTIAL" if score>=60 else "WEAK" if score>=40 else "LOW"
