def binary_search(nums, target):
    left = 0
    right = len(nums) - 1

    while left <= right:
        mid = (left + right)//2    # middle = left + (right-left)//2 to avoid integer overflow in other languages like JAVA, in Python its okay

        if nums[mid] == target:
            return mid

        if nums[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1
list2 = [12, 32, 34, 45, 49, 58, 63, 80]
print(binary_search([58], 58))
    
def linear_search(slist, target):
    for i in range(len(slist)):
        if slist[i] == target:
            return i
    return "not found"
    
    
s = [2, 1, 13, 21, 12, 45, 32]
t = 21
print(linear_search(s, t))   


# Approach	Time
# Linear Search	O(n)
# Binary Search	O(log n)

# You cannot generally beat O(log n) for searching in a sorted array using comparisons.