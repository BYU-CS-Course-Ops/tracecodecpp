"""LLDB embedded Python; no EvaluateExpression or inferior function evaluation."""
import json
import sys
import lldb

binary, output = sys.argv[1:3]
debugger = lldb.SBDebugger.Create()
debugger.SetAsync(False)
debugger.HandleCommand('settings set target.disable-aslr false')
target = debugger.CreateTarget(binary)
bp = target.BreakpointCreateByName('event')
assert bp.GetNumLocations() == 1
launch = lldb.SBLaunchInfo([])
launch.SetLaunchFlags(launch.GetLaunchFlags() & ~lldb.eLaunchFlagDisableASLR)
error = lldb.SBError()
process = target.Launch(launch, error)
assert error.Success(), str(error)

def observe(v, depth=0):
    v.SetPreferSyntheticValue(False)
    a = v.GetLoadAddress()
    row = {'name': v.GetName(), 'type': v.GetTypeName(),
           'address': None if a == lldb.LLDB_INVALID_ADDRESS else hex(a),
           'debugger_value_uncertain': v.GetValue(),
           'error': str(v.GetError()) if v.GetError().Fail() else None,
           'initialization': 'unknown', 'lifetime': 'unknown'}
    # Never dereference pointers. These are DWARF-declared object/field views only.
    if depth < 1 and not v.GetType().IsPointerType():
        row['children'] = [observe(v.GetChildAtIndex(i), depth+1)
                           for i in range(min(v.GetNumChildren(), 8))]
    return row

rows = []
for _ in range(100):
    if process.GetState() == lldb.eStateExited:
        break
    assert process.GetState() == lldb.eStateStopped
    thread = process.GetSelectedThread()
    assert thread.GetStopReason() == lldb.eStopReasonBreakpoint, thread.GetStopDescription(200)
    frame = thread.GetFrameAtIndex(0)
    args = {name: frame.FindVariable(name).GetValueAsUnsigned()
            for name in ('tag', 'address', 'size', 'instance')}
    raw = None
    if args['size']:
        error = lldb.SBError()
        data = process.ReadMemory(args['address'], args['size'], error)
        assert error.Success(), str(error)
        raw = data.hex()
    frames = []
    for i in range(1, thread.GetNumFrames()):
        f = thread.GetFrameAtIndex(i)
        if f.GetLineEntry().GetFileSpec().GetFilename() == 'fixture.cpp':
            frames.append({'function': f.GetFunctionName(),
                           'line': f.GetLineEntry().GetLine(),
                           'variables': [observe(v) for v in f.GetVariables(True, True, False, True)]})
    rows.append({**args, 'address': hex(args['address']),
                 'raw_bytes_uncertain': raw, 'frames': frames})
    process.Continue()
else:
    process.Kill()
    raise AssertionError('stop cap')
assert process.GetExitStatus() == 0
with open(output, 'w') as f:
    json.dump({'triple': target.GetTriple(), 'exit': process.GetExitStatus(),
               'evidence': 'manual source events plus uncertain debugger observations',
               'events': rows}, f, indent=2)
lldb.SBDebugger.Destroy(debugger)
