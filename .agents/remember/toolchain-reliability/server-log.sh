#!/bin/sh
# Optional diagnostic LLDB_DEBUGSERVER_PATH; executable bit required.
command=$1
shift
exec /usr/lib/llvm-14/bin/lldb-server "$command" --log-file /work/.agents/scratch/toolchain-reliability/server-amd64.log --log-channels 'posix all' "$@"
