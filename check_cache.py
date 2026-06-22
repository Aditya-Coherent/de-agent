import sqlite3, json, sys
conn = sqlite3.connect("output/.llm_cache.db")
total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
print(f"Cache entries: {total}")
rows = conn.execute("SELECT k, v FROM cache LIMIT 3").fetchall()
for k, v in rows:
    d = json.loads(v)
    print(f"  keys in response: {list(d.keys())[:6]}")

# Check network with short timeout
import urllib.request
try:
    req = urllib.request.urlopen("https://openrouter.ai", timeout=5)
    print(f"\nOpenRouter reachable: HTTP {req.status}")
except Exception as e:
    print(f"\nOpenRouter NOT reachable: {type(e).__name__}: {e}")
