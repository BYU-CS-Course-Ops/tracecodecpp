#include <cstdio>
struct Guard {int id; Guard(int x):id(x){std::printf("guard %d\n",id);} ~Guard(){std::printf("unguard %d\n",id);} };
void consume(int* p,const Guard&){std::printf("consume %d\n",*p);delete p;}
int init(){std::puts("initializer");return 7;}
int* make(int &n){return new int[n++]{init()};}
int main(){
 int n=2;auto p=make(n);std::printf("return-bound %d %d\n",n,p[0]);delete[]p;
 int* q=nullptr;
 (std::puts("left"),q=new int(++n),std::printf("right %d %d\n",n,*q));delete q;
 // Existing temporary lives to end of outer full-expression, not lambda return.
 consume(new int(8),Guard(1));std::puts("after full-expression");
 bool b=false; b && (q=new int(99));std::printf("short circuit %d\n",b);
}
