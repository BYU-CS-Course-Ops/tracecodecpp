"""Isolate emulator/syscall support from LLDB launch or binding errors."""
import ctypes
import os

pid = os.fork()
if pid == 0:
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.ptrace(0, 0, None, None)  # PTRACE_TRACEME, as debugger child
    error = ctypes.get_errno()
    print(f'PTRACE_TRACEME result={result} errno={error} ({os.strerror(error)})', flush=True)
    if result != 0:
        os._exit(1)
    import signal
    os.kill(os.getpid(), signal.SIGSTOP)
    os._exit(0)
_, status = os.waitpid(pid, os.WUNTRACED)
print(f'child wait status={status}', flush=True)
if not os.WIFSTOPPED(status):
    raise SystemExit(1)
class IOVec(ctypes.Structure):
    _fields_ = [('base', ctypes.c_void_p), ('length', ctypes.c_size_t)]
buf = ctypes.create_string_buffer(4096)
iov = IOVec(ctypes.cast(buf, ctypes.c_void_p), len(buf))
libc = ctypes.CDLL(None, use_errno=True)
result = libc.ptrace(0x4204, pid, 1, ctypes.byref(iov))  # GETREGSET, NT_PRSTATUS
error = ctypes.get_errno()
print(f'PTRACE_GETREGSET result={result} errno={error} ({os.strerror(error)}) bytes={iov.length}', flush=True)
# Always clean up child, even if emulator's TRACEME is only a stub.
import signal
os.kill(pid, signal.SIGKILL)
os.waitpid(pid, 0)
raise SystemExit(0 if result == 0 else 1)
