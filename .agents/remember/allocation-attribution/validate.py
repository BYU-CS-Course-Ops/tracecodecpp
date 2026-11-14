import json,sys,collections
x=json.load(open(sys.argv[1])); es=x['events']
assert x['exit_status']==0
counts=collections.Counter(e['case'] for e in es)
assert dict(counts)=={1:1,2:1,3:1,4:2,5:1,6:2,7:1,8:1,9:1,10:2,11:1}, counts
matches={r['event_id'] for r in x['expression_results']}
assert len(matches)==2 and None not in matches
for e in es:
    e['expected']=e['case'] in (1,2,3,4,5,11) or (e['case']==10 and e['id'] in matches)
print('case id size expected any immediate skip_known skip_registered expression_match')
for e in es:
    print(e['case'],e['id'],e['size'],int(e['expected']),*[int(e['policies'][k]) for k in ('any_student','immediate','skip_known','skip_registered')],int(e['id'] in matches))
for key in ('any_student','immediate','skip_known','skip_registered'):
    fp=[e['id'] for e in es if e['policies'][key] and not e['expected']]
    fn=[e['id'] for e in es if not e['policies'][key] and e['expected']]
    print(key,'false positives',fp,'false negatives',fn)
assert all(e['policies']['skip_registered']==e['expected'] for e in es)
assert [e['id'] for e in es if e['policies']['skip_known'] and not e['expected']]==[10,11]
assert matches=={13,14}
json.dump(x,open(sys.argv[1].replace('.json','-evaluated.json'),'w'),indent=2)
