list1 = [1,10,2,4,7,6]
target = 9

def two_sum(list1, target):
    hashmap = {}
    for i in range(0, len(list1)):
        x = target - list1[i]
        if x in hashmap:
            return [hashmap[x], i]
        else:
            hashmap[list1[i]] = i
    return "not found"  

print(two_sum(list1, target))



# Time complexity: O(n)

# Cleaner code
def two_sum2(nums, target):
    seen = {}

    for i, num in enumerate(nums):
        complement = target - num

        if complement in seen:
            return [seen[complement], i]

        seen[num] = i

    return None

# What is enumerate()?

# Normally, if you do:

# nums = [2, 7, 11, 15]

# for num in nums:
#     print(num)

# Output:

# 2
# 7
# 11
# 15

# You get only the values.

# But in Two Sum, we need both:

# the value (2, 7, etc.)
# the index (0, 1, etc.)

# That's where enumerate() helps.

# nums = [2, 7, 11, 15]

# for i, num in enumerate(nums):
#     print(i, num)

# Output:

# 0 2
# 1 7
# 2 11
# 3 15

# So:

# enumerate(nums)

# produces:

# (0, 2)
# (1, 7)
# (2, 11)
# (3, 15)

# One tuple at a time.