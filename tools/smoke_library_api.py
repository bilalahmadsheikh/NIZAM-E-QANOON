"""Read-only real-corpus proof: API hierarchy and selected-date text match L2."""
import argparse
from datetime import date, datetime
from zoneinfo import ZoneInfo
import json
from pathlib import Path
import time
from uuid import UUID
import httpx
from nizam.storage.library_read import LibraryRead


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--url', default='http://127.0.0.1:8080')
    ap.add_argument('--out',type=Path)
    ap.add_argument('--query',default='Usurious Loans')
    ap.add_argument('--fixtures',type=Path,help='Optional test-only recorded response map')
    args=ap.parse_args()
    as_of = datetime.now(ZoneInfo('Asia/Karachi')).date().isoformat()
    timings=[]
    recorded={}
    def get(path, **params):
        start=time.monotonic()
        r=httpx.get(args.url+path,params={'as_of':as_of,**params},timeout=20)
        r.raise_for_status()
        recorded[str(r.request.url).split(args.url)[-1]]=r.json()
        timings.append({'path':path,'ms':round((time.monotonic()-start)*1000)})
        return r.json()
    listing=get('/v1/law/instruments',q=args.query,limit=10)
    assert listing['items'], 'No matching title currently available in release view'
    inst=listing['items'][0]
    detail=get('/v1/law/instruments/'+inst['id'])
    assert detail['item']==inst
    children=get(f"/v1/law/instruments/{inst['id']}/children",limit=10)
    stack=list(reversed(children['items']))
    selected=None
    inspected=0
    while stack and inspected<50:
        node=stack.pop(); inspected+=1
        candidate=get('/v1/law/provisions/'+node['id'])
        if candidate['item']['text_en']:
            selected=candidate; break
        if node['has_children']:
            page=get(f"/v1/law/instruments/{inst['id']}/children",parent=node['id'],limit=10)
            stack.extend(reversed(page['items']))
    assert selected, 'No readable node found in bounded traversal'
    repo=LibraryRead(); repo.open()
    try:
        stored=repo.provision(UUID(selected['item']['id']),as_of=date.fromisoformat(selected['as_of']))
        assert stored['text_en']==selected['item']['text_en']
        assert str(stored['instrument_id'])==inst['id']
        assert stored['instrument']['source_hash']==selected['item']['instrument']['source_hash']
    finally: repo.close()
    evidence={'instrument':inst,'provision_id':selected['item']['id'],'text_chars':len(stored['text_en']),
              'exact_database_text_match':True,'timings':timings,
              'scope':'API-to-stored-version equality; not an independent PDF accuracy certification'}
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(evidence,indent=2),encoding='utf8')
    if args.fixtures:
        args.fixtures.parent.mkdir(parents=True,exist_ok=True)
        args.fixtures.write_text(json.dumps(recorded,indent=2),encoding='utf8')
    print(json.dumps(evidence,indent=2))


if __name__=='__main__': main()
