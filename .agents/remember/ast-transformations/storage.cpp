#include "runtime.hpp"
#include <cstdlib>
#include <new>
static void* alloc(std::size_t n) {
 void* p=std::malloc(n?n:1); if(!p) throw std::bad_alloc();
 if(tc::nb==4096) std::abort();
 auto id=tc::nb+1; unsigned owner=tc::active?tc::active->token:0;
 tc::blocks[tc::nb++]={p,n,id,owner,true};
 std::fprintf(stderr,"A %u %p %zu %u\n",id,p,n,owner); return p;
}
static void release(void* p) noexcept {
 if(!p)return;
 unsigned id=0;
 for(unsigned i=tc::nb;i>0;--i)if(tc::blocks[i-1].live&&tc::blocks[i-1].p==p){tc::blocks[i-1].live=false;id=tc::blocks[i-1].id;break;}
 std::fprintf(stderr,"D %u %p\n",id,p); std::free(p);
}
void* operator new(std::size_t n){return alloc(n);}
void* operator new[](std::size_t n){return alloc(n);}
void operator delete(void* p) noexcept {release(p);}
void operator delete[](void* p) noexcept {release(p);}
void operator delete(void* p,std::size_t) noexcept {release(p);}
void operator delete[](void* p,std::size_t) noexcept {release(p);}
