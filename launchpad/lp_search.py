"""Searches Ubuntu bugs of the given source packages, in every status.

usage: python3 -I launchpad/lp_search.py <package,package...> <search text...>
"""
import json, sys, urllib.parse, urllib.request
STATUSES = ["New", "Incomplete", "Opinion", "Invalid", "Won't Fix", "Expired", "Confirmed",
            "Triaged", "In Progress", "Fix Committed", "Fix Released", "Deferred"]
for pkg in sys.argv[1].split(','):
    for q in sys.argv[2:]:
        params = [("ws.op", "searchTasks"), ("search_text", q), ("ws.size", "75")] + \
                 [("status", s) for s in STATUSES]
        url = f"https://api.launchpad.net/1.0/ubuntu/+source/{pkg}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                   "User-Agent": "mutter-backport-research"})
        d = json.load(urllib.request.urlopen(req, timeout=60))
        print(f"== {pkg} / {q}: {d.get('total_size')}")
        for e in d.get("entries", []):
            print("  ", e["bug_link"].rsplit("/", 1)[1], e["status"], "|", e["title"][:150])
