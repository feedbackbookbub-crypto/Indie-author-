from datetime import datetime
class MockSearchProvider:
 async def search(self, query, limit=10):
  return [{"title":"Jane Smith | Independent Romance Author","url":"https://example.com/jane-smith","domain":"example.com","snippet":"Jane Smith is a self-published romance author with a 2026 book.","position":i+1,"query":query,"timestamp":datetime.utcnow().isoformat()} for i in range(min(limit,2))]
