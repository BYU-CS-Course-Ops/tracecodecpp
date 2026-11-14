import json, os, sys, re
import lldb
root='/work/.agents/remember/allocation-attribution/'
out=sys.argv[1]
d=lldb.SBDebugger.Create(); d.SetAsync(False)
d.HandleCommand('settings set target.disable-aslr false')
t=d.CreateTarget('/work/.agents/scratch/allocation-attribution/student')
t.BreakpointCreateByName('allocation_event'); t.BreakpointCreateByName('expression_result')
launch=lldb.SBLaunchInfo([]); launch.SetWorkingDirectory('/work')
launch.SetLaunchFlags(launch.GetLaunchFlags() & ~lldb.eLaunchFlagDisableASLR)
err=lldb.SBError(); p=t.Launch(launch,err)
assert err.Success(), str(err)
events=[]; results=[]; live={}
def loc(f):
    le=f.GetLineEntry()
    return dict(function=f.GetFunctionName() or '',file=str(le.GetFileSpec()),line=le.GetLine())
def student(f): return f['file']==root+'student.cpp'
def global_forward(f): return f['file']==root+'allocations.cpp'
def known_forward(f):
    n=f['function']
    return global_forward(f) or (('StudentAllocator<' in n or 'std::allocator<' in n or 'std::__new_allocator<' in n or '__gnu_cxx::new_allocator<' in n or 'std::allocator_traits<' in n) and ('::allocate(' in n or '::allocate<' in n))
for stop in range(300):
    if p.GetState()==lldb.eStateExited: break
    assert p.GetState()==lldb.eStateStopped
    th=p.GetSelectedThread(); f=th.GetFrameAtIndex(0)
    assert th.GetStopReason()==lldb.eStopReasonBreakpoint
    case=t.FindFirstGlobalVariable('case_id').GetValueAsSigned()
    if 'expression_result' in (f.GetFunctionName() or ''):
        address=f.FindVariable('p').GetValueAsUnsigned()
        results.append(dict(case=case,address=hex(address),event_id=live.get(address)))
    else:
        kind=f.FindVariable('kind').GetValueAsSigned()
        address=f.FindVariable('address').GetValueAsUnsigned()
        frames=[loc(th.GetFrameAtIndex(i)) for i in range(1,th.GetNumFrames())]
        if kind>0:
            base=[x for x in frames if not global_forward(x)]
            skipped=[x for x in frames if not known_forward(x)]
            registered=[x for x in skipped if not ('StudentAllocator<' in x['function'] and '::forward_storage(' in x['function'])]
            event=dict(id=len(events)+1,case=case,address=hex(address),size=f.FindVariable('size').GetValueAsUnsigned(),kind=kind,frames=frames,
                policies={'any_student':any(student(x) for x in frames),'immediate':bool(base and student(base[0])), 'skip_known':bool(skipped and student(skipped[0])), 'skip_registered':bool(registered and student(registered[0]))})
            events.append(event); live[address]=event['id']
        else: live.pop(address,None)
    p.Continue()
else: p.Kill(); raise RuntimeError('stop cap')
assert p.GetExitStatus()==0
json.dump(dict(events=events,expression_results=results,exit_status=p.GetExitStatus()),open(out,'w'),indent=2)
print('recorded',len(events),'allocations')
