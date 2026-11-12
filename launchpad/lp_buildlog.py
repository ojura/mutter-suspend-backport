"""Saves Ubuntu's amd64 build log of mutter 46.2-1ubuntu0.24.04.18 and lists its builds.

usage: python3 -I launchpad/lp_buildlog.py <output file>
"""
import gzip, json, sys, urllib.request
H = {"Accept": "application/json", "User-Agent": "mutter-backport-research"}
def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60))
pubs = get("https://api.launchpad.net/1.0/ubuntu/+archive/primary?ws.op=getPublishedSources"
           "&source_name=mutter&version=46.2-1ubuntu0.24.04.18&exact_match=true")
pub = pubs["entries"][0]
print(pub["source_package_version"], pub["pocket"], pub["status"])
builds = get(pub["self_link"] + "?ws.op=getBuilds")
for b in builds["entries"]:
    print(b["arch_tag"], b["buildstate"], b["build_log_url"])
    if b["arch_tag"] == "amd64":
        data = urllib.request.urlopen(urllib.request.Request(b["build_log_url"], headers={"User-Agent": H["User-Agent"]}), timeout=120).read()
        text = gzip.decompress(data).decode(errors="replace") if data[:2] == b"\x1f\x8b" else data.decode(errors="replace")
        open(sys.argv[1], "w").write(text)
