def find_fibonacci_n(n):
    if n == 1 or n == 2:
        return 1
    if n > 2:
        return find_fibonacci_n(n-1) + find_fibonacci_n(n-2)

print(find_fibonacci_n(5))
