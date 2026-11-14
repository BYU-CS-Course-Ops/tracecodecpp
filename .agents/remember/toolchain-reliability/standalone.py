"""Host the unmodified feasibility recorder in standalone Python."""
import runpy
import sys
import lldb

lldb.SBDebugger.Initialize()
try:
    sys.argv[0] = '/work/.agents/remember/feasibility/record.py'
    runpy.run_path(sys.argv[0], run_name='__main__')
finally:
    lldb.SBDebugger.Terminate()
