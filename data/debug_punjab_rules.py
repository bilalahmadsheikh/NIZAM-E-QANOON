#!/usr/bin/env python3
"""
Debug script for Punjab Code rules — run: python debug_punjab_rules.py
"""
import requests
from bs4 import BeautifulSoup
import re

BASE_URL   = "https://punjabcode.punjab.gov.pk"
RULES_URL  = BASE_URL + "/en/get_rules"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": BASE_URL,
}

session = requests.Session()
session.headers.update(HEADERS)

print("=" * 60)
print("1. RULES INDEX PAGE")
print("=" * 60)
resp = session.get(RULES_URL, timeout=30)
print(f"Status: {resp.status_code}")
print(f"Length: {len(resp.text)} chars")

soup = BeautifulSoup(resp.text, "html.parser")

# Find all links matching the pattern we expect for department rules
service_links = []
general_links = []
for a in soup.find_all("a", href=True):
    href = a["href"].strip()
    text = a.get_text(strip=True)
    if re.search(r"/en/get_service_rules/\d+", href):
        service_links.append((text, href))
    elif re.search(r"/en/get_general_rules/\d+", href):
        general_links.append((text, href))

print(f"\nService Rules department links found: {len(service_links)}")
for t, h in service_links[:5]:
    print(f"  {t!r} -> {h}")

print(f"\nGeneral Rules department links found: {len(general_links)}")
for t, h in general_links[:5]:
    print(f"  {t!r} -> {h}")

if not service_links and not general_links:
    print("\nNO MATCHING LINKS — showing ALL links with 'rule' in href (case insensitive):")
    for a in soup.find_all("a", href=True):
        if "rule" in a["href"].lower():
            print(f"  {a.get_text(strip=True)!r} -> {a['href']}")

print()
print("=" * 60)
print("2. TESTING A SPECIFIC DEPARTMENT PAGE (Agriculture, if found)")
print("=" * 60)

# Try to fetch the Agriculture department page if we found a link
test_url = None
if service_links:
    for t, h in service_links:
        if "agriculture" in t.lower():
            test_url = h if h.startswith("http") else BASE_URL + h
            break
    if not test_url:
        test_url = service_links[0][1]
        if not test_url.startswith("http"):
            test_url = BASE_URL + test_url

if test_url:
    print(f"Fetching: {test_url}")
    resp2 = session.get(test_url, timeout=30)
    print(f"Status: {resp2.status_code}")
    soup2 = BeautifulSoup(resp2.text, "html.parser")
    artlists = soup2.find_all("div", class_="artlist")
    print(f"<div class='artlist'> elements: {len(artlists)}")
    if artlists:
        for div in artlists[:5]:
            a = div.find("a")
            if a:
                print(f"  {a.get_text(strip=True)!r} -> {a.get('href','?')}")
    else:
        print("No artlist divs found. First 1500 chars of response:")
        print(resp2.text[:1500])
else:
    print("No department URL found to test")