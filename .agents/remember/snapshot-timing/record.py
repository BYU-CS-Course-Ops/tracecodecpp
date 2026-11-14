import lldb, sys, os, json, time
source, binary, mode, output = sys.argv[1:]
d = lldb.SBDebugger.Create(); d.SetAsync(False)
d.HandleCommand('settings set target.disable-aslr false')
t = d.CreateTarget(binary)
if mode == 'step':
    t.BreakpointCreateByName('main')
else:
    # Only executable source lines, excluding the manual hook implementation.
    for i in range(5, len(open(source).readlines()) + 1):
        t.BreakpointCreateByLocation(source, i)
if mode == 'hybrid': t.BreakpointCreateByName('timing_event')
launch = lldb.SBLaunchInfo([]); launch.SetWorkingDirectory('/work')
launch.SetLaunchFlags(launch.GetLaunchFlags() & ~lldb.eLaunchFlagDisableASLR)
e = lldb.SBError(); p = t.Launch(launch, e)
assert e.Success(), str(e)
rows=[]; blocks=[]; start=time.monotonic()
def loc(f):
    le=f.GetLineEntry()
    return dict(function=f.GetFunctionName(), file=str(le.GetFileSpec()), line=le.GetLine(), pc=hex(f.GetPC()))
def val(v, depth=0):
    r={'name':v.GetName(), 'type':v.GetTypeName(), 'value':v.GetValue(), 'address':hex(v.GetLoadAddress()), 'error':str(v.GetError()) if v.GetError().Fail() else None}
    if depth<1 and v.GetName()=='this':
        obj=v.Dereference()
        r['pointee_observed']=[val(obj.GetChildAtIndex(i),depth+1) for i in range(min(obj.GetNumChildren(),8))]
    if depth<1 and not v.GetType().IsPointerType(): r['children']=[val(v.GetChildAtIndex(i),depth+1) for i in range(min(v.GetNumChildren(),8))]
    return r
for seq in range(2000):
    if p.GetState()==lldb.eStateExited: break
    assert p.GetState()==lldb.eStateStopped
    th=p.GetSelectedThread(); f=th.GetFrameAtIndex(0); where=loc(f)
    event=None
    if 'timing_event(' in (f.GetFunctionName() or '') and mode=='hybrid':
        event={k:f.FindVariable(k).GetValueAsUnsigned() for k in ('kind','address','size','type','site')}
        if event['kind']==1:
            blocks.append(dict(id=len(blocks)+1,address=event['address'],size=event['size'],type=event['type'],state='storage',site=event['site']))
        else:
            b=next(b for b in reversed(blocks) if b['address']==event['address'] and b['state']!='released')
            b['state']={2:'initialized',3:'released',4:'destroyed'}[event['kind']]
    frames=[dict(location=loc(th.GetFrameAtIndex(i)),variables=[val(v) for v in th.GetFrameAtIndex(i).GetVariables(True,True,False,True)]) for i in range(th.GetNumFrames()) if loc(th.GetFrameAtIndex(i))['file']==source]
    heap=[]
    for b in blocks:
        copy=dict(b)
        if b['state'] not in ('released','destroyed'):
            err=lldb.SBError(); raw=p.ReadMemory(b['address'],b['size'],err)
            copy['raw_ints']=[int.from_bytes(raw[i:i+4],'little',signed=True) for i in range(0,len(raw),4)] if err.Success() else None
            copy['initialization']='known complete (manual hook)' if b['state']=='initialized' else 'unknown'
        heap.append(copy)
    rows.append(dict(seq=seq,location=where,event=event,x=t.FindFirstGlobalVariable('x').GetValueAsSigned(),frames=frames,heap=heap))
    if mode=='step':
        if seq==0:
            for bp in t.breakpoint_iter(): bp.SetEnabled(False)
        # Enter student callees; immediately return from nonstudent library/hook frames.
        if where['file']!=source or 'timing_event(' in (where['function'] or ''):
            th.StepOut()
        else: th.StepInto()
    else: p.Continue()
else:
    p.Kill(); raise AssertionError('stop cap')
trace=dict(mode=mode,exit=p.GetExitStatus(),elapsed=time.monotonic()-start,stops=rows,triple=t.GetTriple(),lldb=lldb.SBDebugger.GetVersionString())
json.dump(trace,open(output,'w'),indent=2)
print(mode,len(rows),'stops',trace['exit'],'exit',trace['elapsed'],'seconds')
assert trace['exit']==0
lldb.SBDebugger.Destroy(d)
