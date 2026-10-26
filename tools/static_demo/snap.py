"""Snapshot every API answer the app reads, for the read-only online demo."""
import gzip, json, os, urllib.request
from concurrent.futures import ThreadPoolExecutor

B = os.getenv("NBA_SNAPSHOT_API", "http://127.0.0.1:8001/api")
def get(p): return json.load(urllib.request.urlopen(B + p))
S = {}
for p in ["/health", "/radar", "/overview", "/settings", "/catalog", "/marketing", "/replay", "/ai/status", "/ai/batches/latest", "/developer/ai"]:
    S[p] = get(p)
S["/ai/status"]["configured"] = False
S["__list"] = get("/customers?limit=750")["items"]
paths = [f"/customers/{c['id']}{suf}" for c in S["__list"]
         for suf in ["", "/insights", "/ai-nba", "/products", "/outreach-context", "/outreach", "/newsletter-context", "/newsletters"]]
with ThreadPoolExecutor(8) as pool:
    for p, body in zip(paths, pool.map(get, paths)):
        S[p] = body
raw = json.dumps(S, ensure_ascii=False, separators=(",", ":")).encode()
gz = gzip.compress(raw, 9)
open("snapshot.json.gz", "wb").write(gz)
print(len(S), "keys", len(raw)//1024, "KB raw", len(gz)//1024, "KB gz")
