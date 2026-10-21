#!/bin/bash
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
rm -rf /mnt/e/nizam-data/scraper-venv
uv venv -q /mnt/e/nizam-data/scraper-venv && uv pip install -q --python /mnt/e/nizam-data/scraper-venv/bin/python requests beautifulsoup4 pymupdf
/mnt/e/nizam-data/scraper-venv/bin/python -c 'import requests, bs4, pymupdf; print("ok")'
