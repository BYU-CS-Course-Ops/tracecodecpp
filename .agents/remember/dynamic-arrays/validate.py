"""Portable checks: ABI-specific assertions are tests, not recorder heuristics."""
import json
import sys

for path in sys.argv[1:]:
    trace = json.load(open(path))
    n, events = trace['n'], trace['events']
    assert trace['exit'] == 0
    req = {e['args']['site']: e for e in events if e['hook'] == 'request'}
    done = {e['args']['site']: e for e in events if e['hook'] == 'complete'}
    assert set(req) == set(range(1, 9)) and set(done) == set(range(1, 8))
    for site, result in done.items():
        r = req[site]['args']
        assert r['count'] == (0 if site in (6, 7) else n)
        cookie = 8 if site in (5, 6) else 0
        assert result['offset'] == cookie
        assert result['block']['size'] == r['count'] * r['stride'] + cookie
        if cookie:
            assert int.from_bytes(bytes.fromhex(result['bytes'])[:8], 'little') == r['count']
    assert bytes.fromhex(done[2]['bytes']) == bytes(4*n)
    assert bytes.fromhex(done[3]['bytes']) == (7).to_bytes(4, 'little') + bytes(4*(n-1))
    stages = {e['args']['stage']: e for e in events if e['hook'] == 'checkpoint'}
    for stage in (1, 2, 3):
        vs = stages[stage]['locals']
        for name in ('uninit', 'zeros', 'list', 'plain', 'objects', 'interior'):
            assert not vs[name]['is_array']
            assert vs[name]['size'] == 8
        assert vs['fixed']['is_array'] and vs['fixed']['children'] == 3
        assert vs['interior']['target'] - vs['list']['target'] == 4
        assert vs['one_past']['target'] - vs['list']['target'] == 4*n
        assert stages[stage]['synthesized_list']['values'] == [7, 0 if stage == 1 else 99] + [0]*(n-2)
        assert stages[stage]['synthesized_object_ids'] == list(range(n))
        assert vs['plain']['fields'] == [dict(name='x', type='int', offset=0), dict(name='y', type='double', offset=8)]
        assert vs['objects']['fields'] == [dict(name='id', type='int', offset=0)]
    life = [e for e in events if e['hook'] == 'life']
    assert [e['args']['index'] for e in life if e['args']['phase'] == 1] == list(range(n))
    assert [e['args']['index'] for e in life if e['args']['phase'] == -1] == list(reversed(range(n)))
    throwing = [e for e in life if e['args']['phase'] in (2, 3, -2)]
    assert [(e['args']['phase'], e['args']['index']) for e in throwing] == [(2,0),(3,0),(2,1),(3,1),(2,2),(-2,1),(-2,0)]
    tb = throwing[0]['block']
    assert tb['size'] == (n+1)*4 + 8
    for e in throwing:
        # Cookie already says requested count even when only a prefix has constructed.
        assert int.from_bytes(bytes.fromhex(e['bytes'])[:8], 'little') == n+1
        assert e['offset'] == 8 + 4*e['args']['index']
    cleanup = next(i for i,e in enumerate(events) if e['hook'] == 'allocation_event' and e.get('block_id') == tb['id'] and e['args']['kind'] == -2)
    failure = next(i for i,e in enumerate(events) if e['hook'] == 'failed')
    assert cleanup < failure
    # operator delete[] receives storage base, not the element pointer.
    for site in (5, 6):
        assert any(e['hook'] == 'allocation_event' and e['args']['kind'] == -2 and e['args']['address'] == done[site]['args']['pointer'] - 8 for e in events)
    assert any(e['hook'] == 'allocation_event' and e['args']['kind'] == -2 and e.get('block_id') == tb['id'] for e in events)
    assert len([e for e in events if e['hook'] == 'failed']) == 1
    assert not any(b['live'] for b in stages[4]['blocks'])
    print('PASS', path, 'events=', len(events), 'n=', n, 'throw bytes=', tb['size'])
