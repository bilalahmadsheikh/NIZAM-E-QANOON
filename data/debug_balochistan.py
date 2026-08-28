#!/usr/bin/env python3
"""
Debug script - paste this in your pakcode_scraper folder and run it.
It fetches the 2026 year page and shows exactly what the server returns.
"""

import requests
from bs4 import BeautifulSoup

BASE_URL = "http://balochistancode.gob.pk"
URL = BASE_URL + "/Document.aspx?wise=chronological&year=2026&opento=2&dst="

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": BASE_URL,
}

session = requests.Session()
session.headers.update(HEADERS)

# Warm up with homepage first
print("Visiting homepage...")
r0 = session.get(BASE_URL + "/Home.aspx", timeout=15)
print(f"Homepage status: {r0.status_code}")
print(f"Cookies after homepage: {dict(session.cookies)}")
print()

# Now fetch the year page
print(f"Fetching: {URL}")
resp = session.get(URL, timeout=30)
print(f"Status code: {resp.status_code}")
print(f"Content-Type: {resp.headers.get('Content-Type', 'unknown')}")
print(f"Response length: {len(resp.text)} chars")
print()

# Check for datafield input
soup = BeautifulSoup(resp.text, "html.parser")
datafield = soup.find("input", {"id": "datafield"})

if datafield:
    value = datafield.get("value", "")
    print(f"Found #datafield input!")
    print(f"Value length: {len(value)} chars")
    print(f"Value preview (first 500 chars):")
    print(value[:500])
    print()
    chunks = [c.strip() for c in value.split("@") if c.strip()]
    print(f"Number of '@'-separated chunks: {len(chunks)}")
else:
    print("NO #datafield input found in response!")
    print()
    print("All input elements found:")
    for inp in soup.find_all("input"):
        print(f"  id={inp.get('id','?')} name={inp.get('name','?')} type={inp.get('type','?')}")
    print()
    print("First 2000 chars of response body:")
    print(resp.text[:2000])