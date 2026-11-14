#include <cstddef>
#include <cstdlib>

// Manually inserted semantic hooks: NOT an AST transformation.
extern "C" __attribute__((noinline)) void request(int site, const char* type, std::size_t count, std::size_t stride, int init) {
    asm volatile("" : : "r"(site), "r"(type), "r"(count), "r"(stride), "r"(init) : "memory");
}
extern "C" __attribute__((noinline)) void complete(int site, void* pointer) {
    asm volatile("" : : "r"(site), "r"(pointer) : "memory");
}
extern "C" __attribute__((noinline)) void life(int phase, int index, void* pointer) {
    asm volatile("" : : "r"(phase), "r"(index), "r"(pointer) : "memory");
}
extern "C" __attribute__((noinline)) void checkpoint(int stage) {
    asm volatile("" : : "r"(stage) : "memory");
}
extern "C" __attribute__((noinline)) void failed(int site) {
    asm volatile("" : : "r"(site) : "memory");
}
struct Plain { int x; double y; };
struct Obj {
    static int next;
    int id;
    Obj() : id(next++) { life(1, id, this); }
    ~Obj() { life(-1, id, this); }
};
int Obj::next = 0;
struct Throw {
    static int next;
    int id;
    Throw() : id(next++) {
        life(2, id, this); // ctor body entered, not construction completed
        if (id == 2) throw 42;
        life(3, id, this); // fixture-specific successful body end
    }
    ~Throw() { life(-2, id, this); }
};
int Throw::next = 0;
int main(int argc, char** argv) {
    const std::size_t n = argc > 1 ? std::strtoul(argv[1], nullptr, 10) : 3;
    if (n < 3 || n > 8) return 2;
    request(1, "int", n, sizeof(int), 0);
    int* uninit = new int[n];
    complete(1, uninit);
    request(2, "int", n, sizeof(int), 1);
    int* zeros = new int[n]();
    complete(2, zeros);
    request(3, "int", n, sizeof(int), 2);
    int* list = new int[n]{7};
    complete(3, list);
    request(4, "Plain", n, sizeof(Plain), 0);
    Plain* plain = new Plain[n];
    complete(4, plain);
    request(5, "Obj", n, sizeof(Obj), 3);
    Obj* objects = new Obj[n];
    complete(5, objects);
    request(6, "Obj", 0, sizeof(Obj), 3);
    Obj* empty_objects = new Obj[0];
    complete(6, empty_objects);
    request(7, "int", 0, sizeof(int), 0);
    int* empty_ints = new int[0];
    complete(7, empty_ints);
    int* interior = list + 1;
    int* one_past = list + n;
    int fixed[3] = {1,2,3};
    checkpoint(1);
    *interior = 99;
    checkpoint(2);
    request(8, "Throw", n + 1, sizeof(Throw), 3);
    try {
        Throw* throwing = new Throw[n + 1];
        complete(8, throwing);
        delete[] throwing;
    } catch (int value) {
        if (value != 42) return 3;
        failed(8);
    }
    checkpoint(3);
    delete[] uninit;
    delete[] zeros;
    delete[] list;
    delete[] plain;
    delete[] objects;
    delete[] empty_objects;
    delete[] empty_ints;
    checkpoint(4);
    return fixed[0] - 1;
}
