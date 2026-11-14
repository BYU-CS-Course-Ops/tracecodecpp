#include <vector>
#include <memory>
#include <cstdlib>
#include <new>
extern "C" void allocation_event(void*, unsigned long, int);
volatile int case_id = 0;
extern "C" __attribute__((noinline)) void expression_result(void* p) { asm volatile("" : : "r"(p) : "memory"); }
__attribute__((noinline)) int* helper() { return new int(7); }
__attribute__((noinline)) int* nested() { return helper(); }
struct MiniVector {
    int* p = nullptr;
    void grow(int n) { int* q = new int[n]; delete[] p; p = q; }
    ~MiniVector() { delete[] p; }
};
template<class T> struct StudentAllocator {
    using value_type = T;
    StudentAllocator() = default;
    template<class U> StudentAllocator(const StudentAllocator<U>&) {}
    static T* forward_storage(std::size_t n) { return static_cast<T*>(::operator new(n*sizeof(T))); }
    T* allocate(std::size_t n) { return forward_storage(n); }
    void deallocate(T* p, std::size_t) { ::operator delete(p); }
};
__attribute__((noinline)) void stl_helper() { std::vector<int> v; v.reserve(17); }
__attribute__((noinline)) void allocator_stl_helper() { std::vector<int, StudentAllocator<int>> v; v.reserve(19); }
struct Routed {
    int x;
    static void* operator new(std::size_t n) {
        std::vector<char> scratch(71); // implementation noise, NOT object backing storage
        return std::allocator<char>{}.allocate(n); // actual object storage through STL forwarding
    }
    static void operator delete(void* p) { std::allocator<char>{}.deallocate(static_cast<char*>(p), sizeof(Routed)); }
};
struct MallocObject {
    int x;
    static void* operator new(std::size_t n) {
        void* p = std::malloc(n); if (!p) throw std::bad_alloc();
        allocation_event(p, n, 3); // explicit provider hook: global new cannot see malloc
        return p;
    }
    static void operator delete(void* p) { allocation_event(p, 0, -3); std::free(p); }
};
int main() {
    case_id=1; auto a = new int(1); delete a;
    case_id=2; auto b = helper(); delete b;
    case_id=3; auto c = nested(); delete c;
    case_id=4; { MiniVector v; v.grow(3); v.grow(8); }
    case_id=5; { StudentAllocator<int> a; auto p=a.allocate(5); a.deallocate(p,5); }
    case_id=6; { std::vector<int> v; v.reserve(13); v.push_back(2); v.reserve(29); }
    case_id=7; stl_helper();
    case_id=8; { std::vector<int, StudentAllocator<int>> v; v.reserve(23); }
    case_id=9; allocator_stl_helper();
    case_id=10; auto r = new Routed; expression_result(r); delete r;
    case_id=11; auto m = new MallocObject; expression_result(m); delete m;
    case_id=0;
}
