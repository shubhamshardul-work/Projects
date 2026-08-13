# The two pointer technique uses two pointers/indices moving through 
# a data structure (usually an array or string) to solve problems efficiently. 
# Instead of nested loops, you move two pointers strategically.

def two_sum(list, target):
    left = 0
    right = len(list)-1

    while left < right:
        current_sum = list[left] +list[right]

        if current_sum == target:
            return True
        elif current_sum < target:
            left += 1
        else:
            right -= 1
    return False

print(two_sum([1, 2, 3, 4, 5], 7))  

# Two Pointer Patterns
# Pattern -- When to Use -- Example
# Start-End -- Compare from both sides -- Palindrome, two sum
# Slow-Fast -- One moves faster -- Remove duplicates, linked list cycle
# Same Direction -- Both move forward -- Merge sorted arrays, partition
# Advantages
# ✅ Time: O(n) instead of O(n²)
# ✅ Space: O(1) - no extra data structures needed
# ✅ Works great with SORTED data
# ✅ Clean, readable code
# When to Use Two Pointers
# ✅ Sorted arrays/strings
# ✅ Find pairs, triplets
# ✅ Palindrome problems
# ✅ Container/window problems
# ✅ Partition/rearrange problems

def two_sum_all_pairs(list, target):
    pairs = []
    left = 0
    right = len(list) - 1
    while left < right:
        current_sum = list[left] +list[right]
        if current_sum == target:
            pairs.append([list[left], list[right]])
            left += 1
            right -= 1
        elif current_sum > target:
            right -= 1
        else:
            left += 1
    return pairs

print(two_sum_all_pairs([1, 2, 3, 4, 5], 7))


# palindrome - two pointer - O(n) solution

def is_palindrome(text):
    left = 0
    right = len(text) - 1

    while left < right:
        if text[left] != text[right]:
            return False
        else:
            left += 1
            right -= 1
    return True

print(is_palindrome("kayak"))
print(is_palindrome("abhay"))
print(is_palindrome("12321"))


# Removing duplicates **in place** using two pointers IN THE SAME DIRECTION
# O(n) time
# O(1) space

def remove_duplicates(lst):
    left = 0
    for right in range(1,len(lst)):
        if lst[left] != lst[right]:
            left += 1
            lst[left] = lst[right]
    return lst[:left+1]
            
print(remove_duplicates([1, 2, 3, 4, 5, 5, 5, 5, 5, 6, 6, 7, 7, 7]))