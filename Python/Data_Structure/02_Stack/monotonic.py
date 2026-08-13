s = [1, 19, 4, 2, 7, 5, 6]
# Replace the element with its next greater element in the array
# O(n) solution possible using Stack

def find_next_greater(arr):
    stack = []
    result = [-1] * len(arr)
    for i in range(len(arr)-1, -1, -1):
        # if the top of the stack is smaller than the ith element, 
        # then pop it out, do this till none smaller is left
        while stack and arr[i] >= stack[-1]: 
            stack.pop()
        # if stack is not empty, then the top of the stack is 
        # the next greater element for that ith element
        # else, it remains -1
        if stack:
            result[i] = stack[-1]
        # push the current element into the stack
        stack.append(arr[i])
    return result

print("result1 ",find_next_greater([1, 19, 4, 2, 7, 5, 6]))    


# IN-PLACE VERSION OF THE ABOVE CODE:

def find_next_greater_in_place(arr):
    stack = []
    
    for i in range(len(arr) - 1, -1, -1):
        current = arr[i]
        
        while stack and current >= stack[-1]:
            stack.pop()
        
        arr[i] = stack[-1] if stack else -1
        stack.append(current)
    
    return arr

s2 = [1, 19, 4, 2, 7, 5, 6]
result = find_next_greater_in_place(s2)

print("result2 ", result)  # [19, -1, 5, 5, -1, 6, -1] 
        

# Detailed Breakdown
# 1st Approach Space Usage
# pythonSpace = result array + stack
#       = O(n)          + O(n)
#       = O(n)  ← Total (dominant term)
# Where space is used:

# result = [-1] * len(arr) → O(n)
# stack → O(n) worst case
# current variable → O(1)

# Total: O(n) ❌ (allocates unnecessary result array)

# 2nd Approach Space Usage
# pythonSpace = stack only
#       = O(n)  ← Total
# Where space is used:

# stack → O(n) worst case
# current variable → O(1)
# No result array!

# Total: O(n) ✅ (no unnecessary allocation)

# Time Complexity Analysis
# Both are O(n) because:
# python# Each element is:
# # 1. Pushed to stack ONCE: O(n) total
# # 2. Popped from stack AT MOST ONCE: O(n) total
# # 3. Compared with current element: O(1)

# Total operations: n pushes + n pops = 2n = O(n)
# Visual:
# arr = [1, 5, 0, 3, 4, 5]

# Processing:
# - i=5: Push 5 → stack = [5]
# - i=4: Compare 4 with 5, Push 4 → stack = [5,4]
# - i=3: Compare 3 with 4, Push 3 → stack = [5,4,3]
# - i=2: Compare 0 with 3,4,5, Pop 3,4,5, Push 0 → stack = [5,0]
#   (Each element pushed/popped once total)
# - i=1: Compare 5 with 0,5, Pop 0,5, Push 5 → stack = [5]
# - i=0: Compare 1 with 5, Push 1 → stack = [5,1]

# Total operations: 6 pushes + 5 pops = 11 ≈ O(n)

# Comparison Table
# Metric1st Approach2nd ApproachTimeO(n)O(n)Space (stack)O(n)O(n)Space (result array)O(n) ← Extra!0Space (variables)O(1)O(1)Total SpaceO(n) + O(n) = O(n)O(n) onlyIn-place?No ❌Yes ✅Better for interviews?❌✅

# The Key Difference
# 1st Approach
# Space breakdown:
# ┌─────────────┐
# │ result array│ O(n) ← Unnecessary allocation
# ├─────────────┤
# │ stack       │ O(n)
# ├─────────────┤
# │ variables   │ O(1)
# └─────────────┘
# Total: O(n)
# 2nd Approach
# Space breakdown:
# ┌─────────────┐
# │ stack       │ O(n)
# ├─────────────┤
# │ variables   │ O(1)
# └─────────────┘
# Total: O(n) (no wasted allocation)

# When Allocating a Result Array Is Necessary
# python# If you need BOTH original and result:
# arr = [1, 5, 0, 3, 4, 5]

# original = [1, 5, 0, 3, 4, 5]
# result   = [5, -1, 3, 4, 5, -1]

# Then you MUST use O(n) space for result array ✅
# (Can't modify arr if you need original values elsewhere)

# # But if you only need the result:
# Use in-place approach ✅ (still O(n) for stack, but don't allocate result)

# Bottom Line
# Time Complexity: O(n) for BOTH
#                 (Each element pushed/popped once)

# Space Complexity:
#   1st: O(n)      (stack + result array)
#   2nd: O(n)      (stack only, in-place modification)

# ✅ Use 2nd approach!
#    - Same time complexity
#    - More space-efficient (no result array)
#    - Shows better coding practices
#    - Impresses interviewers
# The 2nd approach is better.