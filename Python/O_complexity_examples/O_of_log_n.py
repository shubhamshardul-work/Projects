# definition of O of log n
# in this approach we divide the problem size by 2 in each step
# for example binary search

def binary_search(arr, target):
    left = 0
    right = len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

print(binary_search([1, 2, 3, 4, 5], 3))

# this is O(log n) because we divide the problem size by 2 in each step 
