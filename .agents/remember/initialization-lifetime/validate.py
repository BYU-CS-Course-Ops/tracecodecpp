import json
import sys

traces = [json.load(open(p)) for p in sys.argv[1:]]
for trace in traces:
    rows = trace['events']
    tags = [r['tag'] for r in rows]
    assert tags == [1,2,3,4,5,10,20,21,11,22,12,20,21,13,22,14,30,31,32,40,41,40,41,40,42,42,43], tags
    by = lambda tag: next(r for r in rows if r['tag'] == tag)
    assert trace['exit'] == 0
    # Known initialized values only; raw equality after lifetime end is an observation,
    # NOT permission to read the dead object from C++ or display it as live.
    assert by(2)['raw_bytes_uncertain'] == '25000000'
    assert by(4)['raw_bytes_uncertain'] == '0b0000000c000000'
    assert by(5)['raw_bytes_uncertain'] == '0b00000000000000'
    assert by(10)['raw_bytes_uncertain'] == '5a'*8
    assert by(11)['address'] == by(12)['address'] == by(13)['address'] == by(14)['address']
    assert by(11)['raw_bytes_uncertain'] == by(12)['raw_bytes_uncertain']
    assert by(13)['raw_bytes_uncertain'] == by(14)['raw_bytes_uncertain']
    assert by(11)['raw_bytes_uncertain'] == '070000000e000000'
    assert by(13)['raw_bytes_uncertain'] == '0800000010000000'
    constructor_entries = [r for r in rows if r['tag'] == 20]
    assert constructor_entries[0]['raw_bytes_uncertain'] == '070000005a5a5a5a'
    assert constructor_entries[1]['raw_bytes_uncertain'] == '080000000e000000'
    uninit = next(v for f in by(1)['frames'] if f['function'] == 'main'
                  for v in f['variables'] if v['name'] == 'uninitialized')
    assert uninit['error'] is None and uninit['debugger_value_uncertain'] is not None
    assert by(30)['address'] == by(31)['address'] == by(32)['address']
    assert by(31)['raw_bytes_uncertain'] == by(32)['raw_bytes_uncertain']
    assert [r['instance'] for r in rows if r['tag'] == 42] == [2,1]
    assert [r['instance'] for r in rows if r['tag'] == 41] == [1,2]
    # At the first hook, DWARF already exposes later-declared main locals.
    names = [v['name'] for f in by(1)['frames'] if f['function'] == 'main'
             for v in f['variables']]
    assert 'uninitialized' in names and 'partial' in names and 'first' in names, names
    print('PASS:', trace['triple'], len(rows), 'events; lifetime/initialization is not inferred from bytes')
if len(traces) == 2:
    a,b = [t['events'][0]['raw_bytes_uncertain'] for t in traces]
    assert b == 'aa'*4, b
    print('Uninitialized local bytes: default=', a, 'pattern=', b,
          '(both source states unknown to debugger)')
