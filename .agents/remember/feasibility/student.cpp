#include <vector>
struct Node { int value; Node* next; };
__attribute__((noinline)) void inner(int& alias, int* pointer) {
    ++alias;
    *pointer += 2;
}
__attribute__((noinline)) void outer(int& ref) {
    inner(ref, &ref);
}
int main() {
    int x = 10;
    int* p = &x;
    int stack_array[3] = {1, 2, 3};
    outer(x);
    Node* head = new Node{10, nullptr};
    head->next = new Node{20, nullptr};
    int* array = new int[4]{1, 2, 3, 4};
    int* interior = array + 2;
    *interior = 30;
    std::vector<int> opaque(16, 7);
    delete head->next;
    delete head;
    delete[] array;
    return x == 13 && stack_array[1] == 2 && p == &x ? 0 : 1;
}
