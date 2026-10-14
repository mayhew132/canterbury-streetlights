#!/usr/bin/env python3
"""Build the map data from the master records.

Master data: data/columns/<MapID>.json, one file per column on the map (edited by hand,
by the admin page, or by importing the confirmation spreadsheet).
Outputs (generated, never edit by hand):
  data/columns.geojson  - what the public map reads
  data/records.json     - every record in one file, for the admin page

Run from the repository root:  python3 scripts/build_geojson.py [--check]
Standard library only. GitHub Actions runs this automatically after every change to data/columns/.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLS = ROOT / 'data' / 'columns'
KCC = ROOT / 'data' / 'kcc.json'

VARIANTS = {'A1', 'A2', 'A3', 'A4', 'B1', 'B2', 'C', 'X-stub', 'X-mod', 'U'}
CONF_ORDER = ['Confirmed', 'Strong', 'Probable', 'Likely', 'Uncertain', 'No match']
ASSET_OK = {'Confirmed', 'Strong', 'Probable', 'Likely'}   # secure enough to sit at the KCC position
COND = {
    'overall': {'Excellent', 'Good', 'Poor', 'Missing'},
    'paint': {'Excellent', 'Good', 'Poor'},
    'structure': {'Intact', 'Damaged'},
    'lantern': {'Intact', 'Damaged', 'None', 'Not seen'},
    'door': {'Present', 'Missing', 'Not seen'},
    'colour': {'Moss Green', 'Black', 'Other'},
}
OWNERS = {'KCC': 'Kent County Council', 'CCC': 'Canterbury City Council (not adopted)', '': ''}


def load():
    kcc = json.loads(KCC.read_text(encoding='utf-8'))
    recs = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(COLS.glob('*.json'))]
    return kcc, recs


def validate(kcc, recs):
    errs, seen = [], set()
    for r in recs:
        i = r.get('id', '?')
        if i in seen: errs.append(f'{i}: duplicate id')
        seen.add(i)
        if r.get('variant') not in VARIANTS: errs.append(f"{i}: unknown variant {r.get('variant')!r}")
        if r.get('confidence') not in CONF_ORDER: errs.append(f"{i}: unknown confidence {r.get('confidence')!r}")
        if r.get('owner') not in OWNERS: errs.append(f"{i}: owner must be KCC, CCC or blank")
        if r.get('owner') == 'KCC' and r.get('asset') and r['asset'] not in kcc:
            errs.append(f"{i}: asset {r['asset']} is not in the KCC extract")
        for c in r.get('candidates', []):
            if r.get('owner') != 'CCC' and c not in kcc: errs.append(f'{i}: candidate {c} is not in the KCC extract')
        for k, ok in COND.items():
            v = (r.get('condition') or {}).get(k, '')
            if v and v not in ok: errs.append(f'{i}: condition {k} {v!r} not one of {sorted(ok)}')
        if not r.get('gps'): errs.append(f'{i}: no position')
    return errs


def position(r, kcc):
    if r.get('owner') == 'KCC' and r.get('asset') in kcc and r.get('confidence') in ASSET_OK:
        a = kcc[r['asset']]
        return a[0], a[1], 'KCC asset position'
    return r['gps'][0], r['gps'][1], 'Photo GPS position'


def feature(r, kcc):
    lat, lon, placed = position(r, kcc)
    props = dict(
        id=r['id'], asset=r.get('asset', ''), owner=OWNERS.get(r.get('owner', ''), ''),
        confirmed_by_guy=bool(r.get('confirmed_by')),
        candidates='; '.join(r.get('candidates', [])), street=r.get('street', ''), variant=r['variant'],
        confidence=r['confidence'], basis=r.get('basis', ''), painted=r.get('painted', ''), note=r.get('note', ''),
        placed=placed, dates=r.get('dates', []), visits=r.get('visits', []), photos=r.get('photos', []),
        condition=r.get('condition', {}), defects=r.get('defects', ''))
    return dict(type='Feature', geometry=dict(type='Point', coordinates=[round(lon, 6), round(lat, 6)]), properties=props)


def main():
    kcc, recs = load()
    errs = validate(kcc, recs)
    if errs:
        print('Problems in data/columns:'); [print('  -', e) for e in errs]
        sys.exit(1)
    order = lambda r: (r.get('order', 10**6), r['id'])
    recs.sort(key=order)
    gj = dict(type='FeatureCollection', features=[feature(r, kcc) for r in recs])
    from collections import Counter
    print(f'{len(recs)} columns')
    print('confidence:', dict(Counter(r['confidence'] for r in recs)))
    print('condition:', dict(Counter((r.get('condition') or {}).get('overall', '') for r in recs)))
    if '--check' in sys.argv:
        return
    (ROOT / 'data' / 'columns.geojson').write_text(json.dumps(gj, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')
    (ROOT / 'data' / 'records.json').write_text(json.dumps(recs, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')
    print('wrote data/columns.geojson and data/records.json')


if __name__ == '__main__':
    main()
