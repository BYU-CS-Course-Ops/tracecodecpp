"""Validate the portable artifact with host Python; no LLDB dependency."""
import json
import sys

p = json.load(open(sys.argv[1]))
ss = p['snapshots']
assert p['exit_status'] == 0
assert len(p['events']) == 8
assert [e['size'] for e in p['events'] if e['student'] and e['kind'] > 0] == [16, 16, 16]
assert len([e for e in p['events'] if not e['student'] and e['kind'] > 0]) == 1
nested = next(s for s in ss if len(s['frames']) == 3)
inner, outer, main = nested['frames']
variables = {v['name']: v for v in main['variables']}
x = variables['x']
alias, pointer = inner['variables']
assert alias['address'] == outer['variables'][0]['address'] == x['address']
assert pointer['target'] == x['address'] and pointer['address'] != x['address']
assert [c['value'] for c in variables['stack_array']['children']] == ['1', '2', '3']
assert all(not b['live'] for b in ss[-1]['heap'])
assert not any('bytes' in b for b in ss[-1]['heap'])

def values():
    for s in ss:
        for frame in s['frames']:
            yield from frame['variables']

head = next(v for v in values() if v['name'] == 'head' and 'pointee_candidate' in v and v['pointee_candidate'].get('children', [{}])[0].get('value') == '10')
fields = head['pointee_candidate']['children']
assert [f['name'] for f in fields] == ['value', 'next']
assert int(fields[0]['address'], 16) == int(head['target'], 16)
assert int(fields[1]['address'], 16) - int(head['target'], 16) == 8
interior = next(v for v in values() if v['name'] == 'interior' and v.get('offset') == 8 and v.get('pointee_candidate', {}).get('value') == '30')
assert interior['pointee_candidate']['type'] == 'int'
assert any(v['name'] == 'opaque' and v.get('opaque') for v in values())
for s in ss:
    assert [b['address_int'] for b in s['heap']] == sorted(b['address_int'] for b in s['heap'])
assert list(reversed(list(reversed(ss)))) == ss
print(f"PASS: {len(ss)} portable snapshots, aliasing, pointer storage, stack array, Node layout, interior pointer mutation, allocation filtering, deletion, backward indexing")
print(f"Example alias address: {x['address']}; pointer storage: {pointer['address']}; Node member offsets: 0, 8")
