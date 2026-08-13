# space time complexity examples
# space complexity is the amount of space used by an algorithm
# time complexity is the amount of time taken by an algorithm

def return_duplicate_slow(list):
    for i in range(len(list)):
        for j in range(len(list)):
            if i != j and list[i] == list[j]:
                return True
    return False

def return_duplicate_fast(list):
    seen = set()
    for name in list:
        if name in seen:
            return True
        seen.add(name)
    return False    

list = ['anirudh', 'satyam', 'rahul', 'manisha', 'sachin', 'anirudh', 'manisha', 'shardul', 'anirudh', 'manisha', 'sachin', 'anirudh', 'manisha', 'shardul']

# calculate actual time
# O(n) is theoretically better at any size, but the practical difference becomes obvious around n=10-20 due to measurement overhead

import timeit
print("actual time taken by slow method = ", timeit.timeit(lambda: return_duplicate_slow(list), number=1000))
print("actual time taken by fast method = ", timeit.timeit(lambda: return_duplicate_fast(list), number=1000))

