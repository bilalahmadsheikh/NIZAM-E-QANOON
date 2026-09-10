# -*- coding: utf-8 -*-
"""Land the scraped statutory archives into the content-addressed blob store.

Implements Document 02 §3.1: read each archive without mutating it, verify the
bytes, and promote them to `raw/{source_id}/{sha256}` -- writing to a temporary
object and renaming, so an interrupted run never leaves a half-written blob.

The archives ship a `manifest.csv` alongside the PDFs whose columns map almost
one-to-one onto §3.1's `source_observation`: the official URL, the referring
page, the HTTP status, the byte length and the scraper's own SHA-256. That is
the only record tying a blob back to the portal it came from, so it is carried
through into `observations.csv` rather than discarded.

Failures and missing links in the manifest become observations too, with no
object_key -- §3.1: "Record missing links and parse errors as first-class
observations. A disappearing official file triggers review; it does not delete
the published corpus."

    python tools/corpus-land/land.py --archives data --out E:/nizam-data

Re-running is cheap and safe: a blob whose hash already exists is skipped.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone

# Top-level directory inside each archive -> (source_id, expected host).
# Hosts are asserted, not assumed: a manifest pointing somewhere else means the
# archive is not what its name claims.
SOURCES = {
    'Federal Laws':     ('pk-federal',     'pakistancode.gov.pk'),
    'punjab_code':      ('pk-punjab',      'punjabcode.punjab.gov.pk'),
    'sindh_code':       ('pk-sindh',       'sindhlaws.gov.pk'),
    'kp_code':          ('pk-kp',          'kpcode.kp.gov.pk'),
    'balochistan_code': ('pk-balochistan', 'balochistancode.gob.pk'),
}

OBS_COLUMNS = [
    'source_id', 'canonical_url', 'referring_url', 'discovered_at', 'fetched_at',
    'http_status', 'etag', 'last_modified', 'media_type', 'byte_length', 'sha256',
    'object_key', 'scraper_version', 'source_metadata', 'outcome', 'error_code',
]

CHUNK = 1 << 20


def norm(p: str) -> str:
    """Normalise a path for matching across the zip (/) and manifest (\\) forms."""
    return p.replace('\\', '/').strip().lower().lstrip('./')


def load_manifest(zf: zipfile.ZipFile, top: str) -> dict:
    """Index manifest rows by the archive-relative path they describe.

    Federal's local_path omits the top-level directory; the provincial archives
    include it. Index both spellings so either matches.
    """
    names = [n for n in zf.namelist() if n.endswith('manifest.csv')]
    if not names:
        return {}
    raw = zf.read(names[0]).decode('utf-8', 'replace')
    rows = list(csv.DictReader(io.StringIO(raw)))
    idx = {}
    for r in rows:
        lp = norm(r.get('local_path') or '')
        if not lp:
            continue
        idx.setdefault(lp, r)
        idx.setdefault(norm(top + '/' + lp), r)
        if lp.startswith(norm(top) + '/'):
            idx.setdefault(lp[len(norm(top)) + 1:], r)
    return {'by_path': idx, 'rows': rows}


def fetched_at(info: zipfile.ZipInfo) -> str:
    try:
        return datetime(*info.date_time).replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        return ''


def land_archive(path: str, out_root: str, dry: bool, report: dict, writer) -> None:
    zf = zipfile.ZipFile(path)
    entries = [i for i in zf.infolist() if not i.is_dir()]
    top = entries[0].filename.split('/')[0]
    if top not in SOURCES:
        raise SystemExit('unknown archive root %r in %s' % (top, path))
    source_id, host = SOURCES[top]
    man = load_manifest(zf, top)
    by_path = man.get('by_path', {})

    st = report['sources'].setdefault(source_id, Counter())
    seen_hashes = report['_hashes'].setdefault(source_id, {})
    blob_dir = os.path.join(out_root, 'raw', source_id)
    if not dry:
        os.makedirs(blob_dir, exist_ok=True)

    for info in entries:
        rel = info.filename
        if not rel.lower().endswith('.pdf'):
            st['skipped_non_pdf'] += 1
            continue

        with zf.open(info) as fh:
            head = fh.read(5)
            if head[:5] != b'%PDF-':
                # §3.1 acceptance: MIME sniffing and %PDF- must agree.
                st['rejected_not_pdf'] += 1
                report['rejected'].append({'archive': os.path.basename(path), 'entry': rel})
                continue
            h = hashlib.sha256(head)
            size = len(head)
            tmp = None
            dest = None
            if not dry:
                tmp = os.path.join(blob_dir, '.tmp-%d' % info.header_offset)
                out = open(tmp, 'wb')
                out.write(head)
            while True:
                b = fh.read(CHUNK)
                if not b:
                    break
                h.update(b)
                size += len(b)
                if not dry:
                    out.write(b)
            if not dry:
                out.close()

        digest = h.hexdigest()
        object_key = 'raw/%s/%s' % (source_id, digest)

        if digest in seen_hashes:
            st['duplicate_bytes'] += 1
            report['duplicates'].append(
                {'source_id': source_id, 'sha256': digest,
                 'kept': seen_hashes[digest], 'also': rel})
            if not dry:
                os.remove(tmp)
        else:
            seen_hashes[digest] = rel
            dest = os.path.join(blob_dir, digest)
            if not dry:
                if os.path.exists(dest):
                    os.remove(tmp)
                    st['already_present'] += 1
                else:
                    os.replace(tmp, dest)          # atomic promote, §3.1
                    st['written'] += 1
            else:
                st['written'] += 1

        row = by_path.get(norm(rel))
        st['matched_manifest' if row else 'no_manifest_row'] += 1

        declared = (row or {}).get('sha256', '').strip().lower()
        if declared and declared != digest:
            st['hash_mismatch'] += 1
            report['mismatches'].append(
                {'source_id': source_id, 'entry': rel,
                 'manifest_sha256': declared, 'actual_sha256': digest})

        meta = {k: (row or {}).get(k) for k in ('title', 'year', 'year_or_dept', 'type', 'doc_type')}
        meta = {k: v for k, v in meta.items() if v}
        meta['archive_path'] = rel
        writer.writerow({
            'source_id': source_id,
            'canonical_url': (row or {}).get('pdf_url', ''),
            'referring_url': (row or {}).get('detail_url', ''),
            'discovered_at': '',
            'fetched_at': fetched_at(info),
            'http_status': (row or {}).get('http_status', ''),
            'etag': '',
            'last_modified': '',
            'media_type': 'application/pdf',
            'byte_length': size,
            'sha256': digest,
            'object_key': object_key,
            'scraper_version': report['scraper_version'].get(source_id, ''),
            'source_metadata': json.dumps(meta, ensure_ascii=False),
            'outcome': 'landed',
            'error_code': '',
        })
        st['landed'] += 1

    # §3.1: failures and missing links are observations, not silence.
    for r in man.get('rows', []):
        status = (r.get('status') or '').lower()
        if status in ('success', 'skipped'):
            continue
        st['manifest_' + (status or 'unknown')] += 1
        writer.writerow({
            'source_id': source_id,
            'canonical_url': r.get('pdf_url', ''),
            'referring_url': r.get('detail_url', ''),
            'discovered_at': '', 'fetched_at': '',
            'http_status': r.get('http_status', ''),
            'etag': '', 'last_modified': '', 'media_type': '',
            'byte_length': r.get('file_size', ''), 'sha256': '',
            'object_key': '',
            'scraper_version': report['scraper_version'].get(source_id, ''),
            'source_metadata': json.dumps(
                {k: v for k, v in r.items()
                 if k in ('title', 'year', 'year_or_dept', 'type', 'doc_type') and v},
                ensure_ascii=False),
            'outcome': status or 'unknown',
            'error_code': (r.get('error') or '')[:300],
        })

    hosts = Counter()
    for r in man.get('rows', []):
        u = r.get('pdf_url') or ''
        if '//' in u:
            hosts[u.split('//', 1)[1].split('/', 1)[0]] += 1
    off = {h: c for h, c in hosts.items() if h and h != host}
    if off:
        report['unexpected_hosts'].append({'source_id': source_id, 'hosts': off})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--archives', default='data', help='directory holding the .zip archives')
    ap.add_argument('--out', required=True, help='blob store root, e.g. E:/nizam-data')
    ap.add_argument('--dry-run', action='store_true', help='hash and report, write nothing')
    a = ap.parse_args()

    zips = sorted(
        os.path.join(a.archives, f) for f in os.listdir(a.archives) if f.lower().endswith('.zip'))
    if not zips:
        raise SystemExit('no archives in %s' % a.archives)

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'archives': [os.path.basename(z) for z in zips],
        'sources': {}, 'duplicates': [], 'mismatches': [], 'rejected': [],
        'unexpected_hosts': [], '_hashes': {},
        'scraper_version': {},
    }
    for sid, script in (('pk-federal', 'scraper.py'), ('pk-punjab', 'punjab_scraper.py'),
                        ('pk-sindh', 'sindh_scraper.py'), ('pk-kp', 'kp_scraper.py'),
                        ('pk-balochistan', 'balochistan_scraper.py')):
        p = os.path.join(a.archives, script)
        if os.path.exists(p):
            with open(p, 'rb') as fh:
                report['scraper_version'][sid] = script + '@' + hashlib.sha256(fh.read()).hexdigest()[:12]

    if not a.dry_run:
        os.makedirs(a.out, exist_ok=True)
    obs_path = os.path.join(a.out, 'observations.csv')
    sink = open(obs_path, 'w', encoding='utf-8', newline='') if not a.dry_run else io.StringIO()
    writer = csv.DictWriter(sink, fieldnames=OBS_COLUMNS)
    writer.writeheader()

    for z in zips:
        print('landing %-52s' % os.path.basename(z), end='', flush=True)
        land_archive(z, a.out, a.dry_run, report, writer)
        print(' ok')
    sink.close()

    uniq = {k: len(v) for k, v in report['_hashes'].items()}
    del report['_hashes']
    report['unique_blobs'] = uniq
    report['unique_blobs_total'] = sum(uniq.values())
    report['sources'] = {k: dict(v) for k, v in report['sources'].items()}

    if not a.dry_run:
        with open(os.path.join(a.out, 'landing-report.json'), 'w', encoding='utf-8') as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)

    print()
    print('%-16s %8s %8s %8s %8s %8s' % ('source', 'landed', 'unique', 'dupes', 'nomanif', 'badhash'))
    for sid, c in report['sources'].items():
        print('%-16s %8d %8d %8d %8d %8d' % (
            sid, c.get('landed', 0), uniq.get(sid, 0), c.get('duplicate_bytes', 0),
            c.get('no_manifest_row', 0), c.get('hash_mismatch', 0)))
    print('%-16s %8d %8d' % (
        'TOTAL', sum(c.get('landed', 0) for c in report['sources'].values()),
        report['unique_blobs_total']))

    for label, key in (('hash mismatches', 'mismatches'), ('rejected (not PDF)', 'rejected'),
                       ('unexpected hosts', 'unexpected_hosts')):
        if report[key]:
            print('\n%s: %d' % (label, len(report[key])))
            for x in report[key][:5]:
                print('   ', x)
    if not a.dry_run:
        print('\nblobs   -> %s' % os.path.join(a.out, 'raw'))
        print('observations -> %s' % obs_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
