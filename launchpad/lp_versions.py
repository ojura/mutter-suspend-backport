"""Prints the published versions of mutter in the given Ubuntu series.

usage: python3 -I launchpad/lp_versions.py <series...>   e.g. jammy noble resolute
"""
import json
import sys
import urllib.request

H = {"Accept": "application/json", "User-Agent": "mutter-backport-research"}
for series in sys.argv[1:]:
    url = ("https://api.launchpad.net/1.0/ubuntu/+archive/primary?ws.op=getPublishedSources"
           f"&source_name=mutter&exact_match=true&status=Published"
           f"&distro_series=https://api.launchpad.net/1.0/ubuntu/{series}")
    d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60))
    print(series, sorted({(e["source_package_version"], e["pocket"]) for e in d["entries"]}))
