#pragma once
#include <cstdio>
#include <cstddef>
#include <cstdint>
namespace tc {
struct Block { void* p; std::size_t size; unsigned id, owner; bool live; };
inline Block blocks[4096]{};
inline unsigned nb=0, next=0;
struct Request;
inline thread_local Request* active=nullptr;
struct Request {
 unsigned site, token; bool array, known; long long count; Request* prev;
 Request(unsigned s,bool a):site(s),token(++next),array(a),known(!a),count(a?0:1),prev(active) { active=this; std::fprintf(stderr,"R %u %u\n",token,site); }
 ~Request(){active=prev;}
 void success(const void* p) noexcept {
   unsigned match=0, matches=0;
   auto addr=reinterpret_cast<std::uintptr_t>(p);
   for(unsigned i=0;i<nb;++i) {auto &b=blocks[i]; auto base=reinterpret_cast<std::uintptr_t>(b.p);
     if(b.live && b.owner==token && addr>=base && (addr<base+b.size || (known && count==0 && addr==base+b.size))) {match=b.id; ++matches;}}
   std::fprintf(stderr,"S %u %p %u %u\n",token,p,matches==1?match:0,matches);
 }
 void failure() noexcept {std::fprintf(stderr,"F %u\n",token);}
};
template<class T> T bound(Request& r,T n) noexcept { static_assert(__is_integral(T) && sizeof(T)<=4,"only integral bounds up to 32 bits supported"); r.known=true; r.count=static_cast<long long>(n); std::fprintf(stderr,"C %u %lld\n",r.token,r.count); return n; }
}
