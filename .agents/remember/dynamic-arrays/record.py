"""LLDB embedded Python; hook-only stops, no expression evaluation in inferior."""
import json
import os
import sys
import lldb

root = os.path.realpath('.agents/remember/dynamic-arrays')
out = os.path.realpath('.agents/scratch/dynamic-arrays')
n = int(os.environ.get('ARRAY_N', '3'))
d = lldb.SBDebugger.Create()
d.SetAsync(False)
d.HandleCommand('settings set target.disable-aslr false')
t = d.CreateTarget(out + '/student')
for name in ('request', 'complete', 'life', 'checkpoint', 'failed', 'allocation_event'):
    t.BreakpointCreateByName(name)
launch = lldb.SBLaunchInfo([str(n)])
launch.SetLaunchFlags(launch.GetLaunchFlags() & ~lldb.eLaunchFlagDisableASLR)
e = lldb.SBError()
p = t.Launch(launch, e)
assert e.Success(), str(e)
events = []
blocks = []

def raw(address, size):
    err = lldb.SBError()
    b = p.ReadMemory(address, size, err) if size else b''
    return b.hex() if err.Success() else None

def val(v):
    ty = v.GetType()
    result = dict(type=v.GetTypeName(), size=ty.GetByteSize(), value=v.GetValue(),
                  address=v.GetLoadAddress(), children=v.GetNumChildren(),
                  is_array=ty.IsArrayType(), error=str(v.GetError()))
    if ty.IsPointerType():
        pt = ty.GetPointeeType()
        result.update(target=v.GetValueAsUnsigned(), pointee=pt.GetName(), stride=pt.GetByteSize(),
                      fields=[dict(name=pt.GetFieldAtIndex(i).GetName(),
                                   type=pt.GetFieldAtIndex(i).GetType().GetName(),
                                   offset=pt.GetFieldAtIndex(i).GetOffsetInBytes())
                              for i in range(pt.GetNumberOfFields())])
    return result

for stop in range(300):
    if p.GetState() == lldb.eStateExited:
        break
    assert p.GetState() == lldb.eStateStopped
    thread = p.GetSelectedThread()
    assert thread.GetStopReason() == lldb.eStopReasonBreakpoint, thread.GetStopDescription(256)
    f = thread.GetFrameAtIndex(0)
    name = f.GetFunctionName().split('(')[0].lstrip(':')
    args = {v.GetName(): v.GetValueAsSigned() for v in f.GetVariables(True, False, False, True)}
    event = dict(hook=name, args=args)
    if name == 'request':
        event['type_text'] = f.FindVariable('type').GetSummary()
    if name == 'allocation_event':
        a, size, kind = args['address'], args['size'], args['kind']
        if kind > 0:
            blocks.append(dict(id=len(blocks)+1, base=a, size=size, live=True))
            event['block_id'] = blocks[-1]['id']
        else:
            matches = [b for b in blocks if b['live'] and b['base'] == a]
            if matches:
                matches[-1]['live'] = False
                event['block_id'] = matches[-1]['id']
    if name in ('complete', 'life'):
        a = args['pointer']
        matches = [b for b in blocks if b['live'] and b['base'] <= a <= b['base']+b['size']]
        if matches:
            b = matches[-1]
            event.update(block=dict(b), offset=a-b['base'], bytes=raw(b['base'], b['size']))
    if name == 'checkpoint':
        main = next(thread.GetFrameAtIndex(i) for i in range(thread.GetNumFrames())
                    if thread.GetFrameAtIndex(i).GetFunctionName() == 'main')
        event['locals'] = {v.GetName(): val(v) for v in main.GetVariables(True, True, False, True)}
        # Explicitly synthesized typed view: its count is supplied by this driver, not recovered by LLDB.
        ptr = main.FindVariable('list')
        ty = ptr.GetType().GetPointeeType()
        if args['stage'] < 4:
            synthetic = t.CreateValueFromAddress('manual_view', lldb.SBAddress(ptr.GetValueAsUnsigned(), t), ty.GetArrayType(n))
            event['synthesized_list'] = dict(count_source='driver n, NOT inferred',
                type=synthetic.GetTypeName(), children=synthetic.GetNumChildren(),
                values=[synthetic.GetChildAtIndex(i).GetValueAsSigned() for i in range(n)])
            obj = main.FindVariable('objects')
            obj_view = t.CreateValueFromAddress('manual_objects', lldb.SBAddress(obj.GetValueAsUnsigned(), t), obj.GetType().GetPointeeType().GetArrayType(n))
            event['synthesized_object_ids'] = [obj_view.GetChildAtIndex(i).GetChildMemberWithName('id').GetValueAsSigned() for i in range(n)]
        event['blocks'] = [dict(b) for b in blocks]
    events.append(event)
    p.Continue()
else:
    p.Kill()
    raise RuntimeError('stop limit')
assert p.GetExitStatus() == 0, p.GetExitStatus()
with open(out + '/trace-%d.json' % n, 'w') as stream:
    json.dump(dict(triple=t.GetTriple(), n=n, exit=p.GetExitStatus(), events=events), stream, indent=2)
print('Recorded', len(events), 'events for n =', n)
