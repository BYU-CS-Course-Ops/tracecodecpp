import json
from pathlib import Path
root=Path('.agents/scratch/snapshot-timing')
traces={m:json.loads((root/(m+'.json')).read_text()) for m in ['lines','step','hybrid']}
summary={}
for mode,t in traces.items():
    rows=t['stops']; assert t['exit']==0
    assert set(r['x'] for r in rows)=={0,3,9}, 'same-line x=1,2 must be absent'
    phases={}
    for function in ['Item::Item()', 'Item::~Item()']:
        samples=[]
        for r in rows:
            if r['location']['function']==function:
                this=next(v for v in r['frames'][0]['variables'] if v['name']=='this')
                samples.append([int(c['value']) for c in this['pointee_observed']])
        phases[function]=samples
    assert [1,2] in phases['Item::Item()'] and [4,2] in phases['Item::Item()'] and [4,5] in phases['Item::Item()']
    assert [3,2] not in phases['Item::Item()']
    assert [7,5] in phases['Item::~Item()'] and [-2,5] in phases['Item::~Item()'] and [-2,-3] in phases['Item::~Item()']
    assert [-1,5] not in phases['Item::~Item()']
    summary[mode]=dict(stops=len(rows),elapsed=t['elapsed'],phases=phases)
h=traces['hybrid']['stops']; events={r['event']['site']:r for r in h if r['event']}
assert len(events)==13
for site,expected in [(31,[4,5]),(35,[10]),(21,[10,20]),(41,[99])]:
    r=events[site]; b=next(b for b in r['heap'] if b['address']==r['event']['address'] and b['state']=='initialized')
    assert b['raw_ints']==expected
assert [events[s]['event']['kind'] for s in [40,41,42]]==[1,2,3]
assert events[40]['seq']<events[41]['seq']<events[42]['seq']
assert sum(b['state']=='initialized' for b in events[21]['heap'])==2
assert events[22]['heap'][1]['state']=='released'
def main_vars(row):
    return {v['name']:v for f in row['frames'] if f['location']['function']=='main' for v in f['variables']}
old=events[22]['event']['address']; new=events[21]['event']['address']
assert old!=new
before=main_vars(events[22]); after=main_vars(events[36])
assert int(before['alias']['value'],16)==old==int(before['v']['children'][0]['value'],16)
assert int(after['alias']['value'],16)==old and int(after['v']['children'][0]['value'],16)==new
assert len(h[-1]['heap'])==4 and all(b['state']=='released' and 'raw_ints' not in b for b in h[-1]['heap'])
assert len({b['id'] for b in h[-1]['heap']})==4
summary['events']=13
summary['allocation_generations']=4
(root/'summary.json').write_text(json.dumps(summary,indent=2))
print('PASS: all modes, same-line omissions, constructor/destructor phases, vector overlap, immediate lifetime, terminal no-read policy')
print(json.dumps(summary,indent=2))
