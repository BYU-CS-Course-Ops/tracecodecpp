import json,pathlib,subprocess
R=pathlib.Path('.agents/remember/ast-transformations'); O=pathlib.Path('.agents/scratch/ast-transformations')
meta=json.loads((O/'generated.sites.json').read_text()); assert len(meta['sites'])==14
for opt in (0,):
 lines=[x.split() for x in (O/f'events{opt}.txt').read_text().splitlines()]
 req={};success=[]; fail=[];counts=[];allocated={};deleted=set()
 for e in lines:
  if e[0]=='R': assert e[1] not in req;req[e[1]]=e[2]
  elif e[0]=='C':counts.append(int(e[2]));assert e[1] in req
  elif e[0]=='A':allocated[e[1]]=e
  elif e[0]=='D':deleted.add(e[1])
  elif e[0]=='S':success.append(e[1]);assert e[3]!='0' and e[4]=='1',e;assert e[3] in allocated
  elif e[0]=='F':fail.append(e[1])
 assert len(req)==14 and len(success)==10 and len(fail)==4,(len(req),success,fail)
 assert sorted(success+fail,key=int)==sorted(req,key=int)
 assert counts==[2,3,2,0,0,4,-1],counts
 assert set(allocated)==deleted,(allocated,deleted)
 for e in lines:
  if e[0]=='S' and req[e[1]] in ('8','9','10'):
   block=allocated[e[3]]; offset=int(e[2],16)-int(block[2],16)
   assert offset==(0 if req[e[1]]=='10' else 8),(e,block)
 assert 'cleanup 1\ncleanup 0\ncaught ctor 42 alive 0' in (O/f'transformed{opt}.out').read_text()
 assert 'S 11 ' not in (O/f'events{opt}.txt').read_text()
 assert (O/f'original{opt}.out').read_bytes()==(O/f'transformed{opt}.out').read_bytes()
 print(f'PASS O{opt}: 14 requests, 10 unique storage joins, 4 failures, single bound evaluation, all storage released; stdout/types agree')
seq=(O/'sequence-events.txt').read_text().splitlines()
assert sum(x.startswith('R ') for x in seq)==3 # fourth source site is short-circuited
assert (O/'sequence-original.out').read_bytes()==(O/'sequence-transformed.out').read_bytes()
print('PASS sequencing: return expression, comma, short-circuit, outer temporary lifetime')
# Each is an actual compiler-accepted fixture before transformation; transformed rejection is required.
cases={
 'wide-bound':'int main(){long n=2;auto p=new int[n];delete[]p;}',
 'class-allocator':'#include <cstdlib>\nstruct T{static void* operator new(__SIZE_TYPE__ n){return malloc(n);}};int main(){auto p=new T;delete p;}',
 'temporary':'struct T { ~T(){} operator int(){return 2;} }; int main(){auto p=new int[T()];delete[]p;}',
 'init-temporary':'struct T { ~T(){} operator int(){return 2;} }; int main(){auto p=new int(T());delete p;}',
 'placement':'#include <new>\nint main(){alignas(int) char b[sizeof(int)];auto p=new(b) int;}',
 'nothrow':'#include <new>\nint main(){auto p=new(std::nothrow) int;delete p;}',
 'aligned':'struct alignas(64) T{};int main(){auto p=new T;delete p;}',
 'multi':'int main(){auto p=new int[2][3];delete[]p;}',
 'template':'template<class T> void f(){auto p=new T;delete p;} int main(){f<int>();}',
 'macro':'#define MAKE new int\nint main(){auto p=MAKE;delete p;}',
 'unevaluated':'int main(){return sizeof(new int)==0;}',
 'constexpr':'constexpr int f(bool b){if(b){auto p=new int;delete p;}return 0;} int main(){return f(false);}',
}
for name,text in cases.items():
 src=O/(name+'.cpp');src.write_text(text)
 base=subprocess.run(['clang++-18','-std=c++17','-fsyntax-only',str(src)],capture_output=True,text=True)
 # constexpr new is a C++20 feature: accepted as Clang extension in C++17 on this build.
 assert base.returncode==0,(name,base.stderr)
 p=subprocess.run(['python3',str(R/'transform.py'),str(src),str(O/(name+'.generated.cpp'))],capture_output=True,text=True)
 (O/(name+'.log')).write_text(p.stdout+p.stderr)
 assert p.returncode!=0,(name,p.stdout)
 print('PASS rejected',name)
