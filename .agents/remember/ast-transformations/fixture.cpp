#include <cstdio>
#include <type_traits>
#include <new>
int calls=0, alive=0, serial=0;
int bound(){std::printf("bound %d\n",++calls);return 3;}
int badbound(){std::puts("badbound");throw 17;}
struct Obj {
 int id;
 Obj():id(serial++){++alive;std::printf("ctor %d\n",id);}
 ~Obj(){--alive;std::printf("dtor %d\n",id);}
};
struct Throw {
 int id;
 Throw():id(serial++){std::printf("try %d\n",id);if(id==2)throw 42;++alive;}
 ~Throw(){--alive;std::printf("cleanup %d\n",id);}
};
struct Nested {int* p; Nested():p(new int(77)){std::puts("Nested");} ~Nested(){delete p;}};
int main(){
 int n=2;
 auto a=new int[n++]{7}; static_assert(std::is_same<decltype(a),int*>::value); std::printf("a %d %d %d\n",n,a[0],a[1]);delete[] a;
 auto b=new int[bound()]();static_assert(std::is_same<decltype(b),int*>::value);std::printf("b %d %d\n",calls,b[2]);delete[] b;
 auto c=new const int(9);static_assert(std::is_same<decltype(c),const int*>::value);std::printf("c %d\n",*c);delete c;
 auto d=new int*(new int{11});static_assert(std::is_same<decltype(d),int**>::value);std::printf("d %d\n",**d);delete *d;delete d;
 auto e=new Nested;std::printf("e %d\n",*e->p);delete e;
 auto f=new Obj[2];delete[] f;
 auto z=new Obj[0];delete[] z;
 auto zi=new int[0];delete[] zi;
 try {auto p=new int[badbound()];delete[] p;}catch(int e){std::printf("caught bound %d\n",e);}
 serial=0;
 try {auto p=new Throw[4];delete[] p;}catch(int e){std::printf("caught ctor %d alive %d\n",e,alive);}
 serial=2;
 try {auto p=new Throw;delete p;}catch(int e){std::printf("caught scalar %d\n",e);}
 try {int neg=-1;auto p=new int[neg];delete[] p;}catch(const std::bad_alloc&){std::puts("negative");}
 std::printf("done %d %d %d\n",n,calls,alive);
}
