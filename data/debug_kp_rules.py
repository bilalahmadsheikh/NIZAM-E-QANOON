#!/usr/bin/env python3
"""Run: python debug_kp_rules.py"""
import requests
from bs4 import BeautifulSoup

BASE_URL  = "https://kpcode.kp.gov.pk"
RULES_URL = BASE_URL + "/homepage/rules"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": BASE_URL,
}

session = requests.Session()
session.headers.update(HEADERS)

resp = session.get(RULES_URL, timeout=30)
print(f"Status: {resp.status_code}, Length: {len(resp.text)}")

soup = BeautifulSoup(resp.text, "html.parser")

# Show all div classes used in the content area
content = soup.find(id="content")
if content:
    divs = content.find_all("div", class_=True)
    classes = {}
    for d in divs:
        for c in d.get("class", []):
            classes[c] = classes.get(c, 0) + 1
    print(f"\nDiv classes in #content: {classes}")

    # Show all links in content
    links = content.find_all("a", href=True)
    print(f"\nLinks in #content: {len(links)}")
    for a in links[:10]:
        print(f"  {a.get_text(strip=True)!r} -> {a['href']}")
else:
    print("No #content div found")

# Show the middle chunk of the page (skip headers/footers)
print("\nMiddle 2000 chars of page:")
mid = len(resp.text) // 3
print(resp.text[mid:mid+2000])