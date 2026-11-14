"""Small synchronous LLDB feasibility recorder, not a production trace schema."""
import json
import os
import platform
import sys
import time
import lldb

source = os.path.realpath(sys.argv[1])
binary, output = sys.argv[2:4]
debugger = lldb.SBDebugger.Create()
debugger.SetAsync(False)
# Keep ASLR enabled: disabling it may require extra container permissions.
debugger.HandleCommand('settings set target.disable-aslr false')
target = debugger.CreateTarget(binary)
for line in range(1, len(open(source).readlines()) + 1):
    target.BreakpointCreateByLocation(source, line)
hook = target.BreakpointCreateByName('allocation_event')
error = lldb.SBError()
launch = lldb.SBLaunchInfo([])
launch.SetWorkingDirectory('/work')
launch.SetLaunchFlags(launch.GetLaunchFlags() & ~lldb.eLaunchFlagDisableASLR)
process = target.Launch(launch, error)
if error.Fail():
    raise RuntimeError(str(error))
allocations, events, snapshots = {}, [], []
next_id = 1

def location(frame):
    entry = frame.GetLineEntry()
    return {'function': frame.GetFunctionName(), 'file': str(entry.GetFileSpec()), 'line': entry.GetLine()}

def serialize(value, depth=0):
    value.SetPreferSyntheticValue(False)
    typ = value.GetType()
    reference = typ.IsReferenceType()
    obj = value.Dereference() if reference else value
    address = obj.GetLoadAddress()
    result = {'name': value.GetName(), 'type': value.GetTypeName(),
              'address': None if address == lldb.LLDB_INVALID_ADDRESS else hex(address),
              'address_meaning': 'referent' if reference else 'object',
              'value': obj.GetValue(), 'read_error': str(obj.GetError()) if obj.GetError().Fail() else None,
              'initialization': 'unknown'}
    # Library internals are intentionally opaque.
    if 'std::' in (value.GetTypeName() or ''):
        result['opaque'] = True
        return result
    if typ.IsPointerType():
        pointer = value.GetValueAsUnsigned()
        result['target'] = hex(pointer)
        for block in allocations.values():
            if block['live'] and block['address_int'] <= pointer < block['address_int'] + block['size']:
                result['allocation_id'] = block['id']
                result['offset'] = pointer - block['address_int']
                # Static pointee type is evidence, not proof of object lifetime/type.
                if depth < 2 and typ.GetPointeeType().GetByteSize() <= block['size'] - result['offset']:
                    result['pointee_candidate'] = serialize(value.Dereference(), depth + 1)
                break
    elif depth < 3:
        children = [serialize(obj.GetChildAtIndex(i), depth + 1) for i in range(min(obj.GetNumChildren(), 16))]
        if children:
            result['children'] = children
    return result

start = time.monotonic()
for stop in range(500):
    if process.GetState() == lldb.eStateExited:
        break
    if process.GetState() != lldb.eStateStopped:
        raise RuntimeError(f'unexpected state {process.GetState()}')
    thread = process.GetSelectedThread()
    if thread.GetStopReason() != lldb.eStopReasonBreakpoint:
        raise RuntimeError(f'unexpected stop {thread.GetStopDescription(200)}')
    frame = thread.GetFrameAtIndex(0)
    loc = location(frame)
    if 'allocation_event(' in (frame.GetFunctionName() or ''):
        address = frame.FindVariable('address').GetValueAsUnsigned()
        size = frame.FindVariable('size').GetValueAsUnsigned()
        kind = frame.FindVariable('kind').GetValueAsSigned()
        callers = [location(thread.GetFrameAtIndex(i)) for i in range(1, min(thread.GetNumFrames(), 12))]
        # Deliberately narrow experiment: direct student new only, not STL internals.
        student = len(callers) > 1 and callers[1]['file'] == source
        event = {'address': hex(address), 'size': size, 'kind': kind, 'student': student, 'callers': callers}
        if kind > 0 and student:
            allocations[address] = {'id': next_id, 'address_int': address, 'address': hex(address), 'size': size, 'live': True}
            next_id += 1
        elif kind < 0 and address in allocations:
            allocations[address]['live'] = False
            event['note'] = 'deallocation requested; hook stops before free'
        events.append(event)
    frames = []
    for i in range(thread.GetNumFrames()):
        f = thread.GetFrameAtIndex(i)
        if location(f)['file'] == source:
            frames.append({**location(f), 'variables': [serialize(v) for v in f.GetVariables(True, True, False, True)]})
    blocks = []
    for block in sorted(allocations.values(), key=lambda b: b['address_int']):
        b = dict(block)
        if b['live']:
            read_error = lldb.SBError()
            raw = process.ReadMemory(b['address_int'], b['size'], read_error)
            b['bytes'] = raw.hex() if read_error.Success() else None
            b['initialization'] = 'unknown'
        blocks.append(b)
    snapshots.append({'stop': stop, 'location': loc, 'frames': frames, 'heap': blocks, 'event_count': len(events)})
    process.Continue()
else:
    process.Kill()
    raise RuntimeError('stop limit exceeded')
trace = {'schema': 'tracecpp-feasibility-1', 'architecture': platform.machine(), 'triple': target.GetTriple(),
         'pointer_bytes': target.GetAddressByteSize(), 'lldb': lldb.SBDebugger.GetVersionString(),
         'source': open(source).read(), 'events': events, 'snapshots': snapshots,
         'exit_status': process.GetExitStatus(), 'elapsed_seconds': time.monotonic() - start}
with open(output, 'w') as f:
    json.dump(trace, f, indent=2)
print(json.dumps({k: v for k, v in trace.items() if k not in ('source', 'events', 'snapshots')}))
print(f'{len(snapshots)} snapshots; {len(events)} allocation events; {len(allocations)} student blocks')
assert trace['exit_status'] == 0
lldb.SBDebugger.Destroy(debugger)
