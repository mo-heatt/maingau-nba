import json, gzip, urllib.request, sys
B = "http://127.0.0.1:8001/api"
def get(p): return json.load(urllib.request.urlopen(B + p))
S = {}
for p in ["/health", "/radar", "/overview", "/settings", "/catalog", "/marketing", "/replay", "/ai/status", "/ai/batches/latest"]:
    S[p] = get(p)
S["/ai/status"]["configured"] = False
S["__list"] = get("/customers?limit=750")["items"]
for c in S["__list"]:
    i = c["id"]
    for suf in ["", "/insights", "/ai-nba"]:
        S[f"/customers/{i}{suf}"] = get(f"/customers/{i}{suf}")
raw = json.dumps(S, ensure_ascii=False, separators=(",", ":")).encode()
gz = gzip.compress(raw, 9)
open("snapshot.json.gz", "wb").write(gz)
print(len(S), "keys", len(raw)//1024, "KB raw", len(gz)//1024, "KB gz")
