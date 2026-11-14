# Matching LLVM packages are pinned; transitive OS packages use Ubuntu updates.
FROM ubuntu:24.04@sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5
ARG LLVM_VERSION=1:18.1.3-1ubuntu1
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    clang-18=${LLVM_VERSION} llvm-18=${LLVM_VERSION} \
    lldb-18=${LLVM_VERSION} python3-lldb-18=${LLVM_VERSION} \
    python3 libstdc++-13-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONPATH=/usr/lib/llvm-18/lib/python3.12/site-packages
# Ubuntu's versioned Python extension points at an absent unversioned library.
RUN ln -s liblldb.so.1 /usr/lib/llvm-18/lib/liblldb.so \
    && clang++-18 --version && lldb-18 --version \
    && lldb-18 --batch -o 'script import lldb; print(lldb.SBDebugger.GetVersionString())'
WORKDIR /work
CMD ["/bin/bash"]
