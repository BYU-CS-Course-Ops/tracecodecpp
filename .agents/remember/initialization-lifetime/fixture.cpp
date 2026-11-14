#include <cstddef>
#include <cstring>
#include <new>

// Hand-authored instrumentation. No payload is evaluated as a C++ value.
extern "C" __attribute__((noinline)) void event(int tag, const void* address,
                                               std::size_t size, int instance) {
    asm volatile("" : : "r"(tag), "r"(address), "r"(size), "r"(instance) : "memory");
}
struct Partial { int a; int b; };
struct Item {
    int x;
    int y;
    explicit Item(int id) : x(id) {
        event(20, this, sizeof(*this), id); // x initialized, y not initialized
        y = 2 * id;
        event(21, this, sizeof(*this), id); // member write completed
    }
    ~Item() { event(22, this, sizeof(*this), x); }
};
struct Other { long z; };
struct Throwing {
    static int count;
    int id;
    Throwing() : id(++count) {
        event(40, this, sizeof(*this), id);
        if (id == 3) throw 3;
        event(41, this, sizeof(*this), id);
    }
    ~Throwing() { event(42, this, sizeof(*this), id); }
};
int Throwing::count = 0;

int main() {
    int uninitialized;
    event(1, &uninitialized, sizeof(uninitialized), 0);
    uninitialized = 37;
    event(2, &uninitialized, sizeof(uninitialized), 0);
    Partial partial;
    partial.a = 11;
    event(3, &partial, sizeof(partial), 0);
    partial.b = 12;
    event(4, &partial, sizeof(partial), 0);
    Partial aggregate{11}; // omitted member is zero-initialized, unlike Partial partial
    event(5, &aggregate, sizeof(aggregate), 0);
    alignas(Item) unsigned char storage[sizeof(Item)];
    // Deliberately recognizable storage bytes. Not proof of a live Item.
    std::memset(storage, 0x5a, sizeof(storage));
    event(10, storage, sizeof(storage), 0);
    Item* first = new (storage) Item(7);
    event(11, first, sizeof(*first), 1);
    first->~Item();
    event(12, storage, sizeof(storage), 1);
    Item* second = new (storage) Item(8);
    event(13, second, sizeof(*second), 2);
    second->~Item();
    event(14, storage, sizeof(storage), 2);
    // Independently aligned storage for the different-type reuse test.
    alignas(Other) unsigned char mixed[sizeof(Other)];
    int* number = new (mixed) int(91);
    event(30, number, sizeof(*number), 3);
    Other* other = new (mixed) Other{123}; // ends overlapping int lifetime
    event(31, other, sizeof(*other), 4);
    other->~Other();
    event(32, mixed, sizeof(mixed), 4);
    try { Throwing* array = new Throwing[4]; delete[] array; }
    catch (int) { event(43, nullptr, 0, 0); }
    return 0;
}
