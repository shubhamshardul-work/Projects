# next greater element extended version
# Problem statement 
# Replace the element with its next greater element in the array extended
# Example : 
#  s = [1, 19, 4, 2, 7, 5, 6]
#  output = [19, -1, 7, 7, 19, 6, 19]

def find_next_greater2(s):
    stack = []
    n = len(s)
    results = [-1] * n
    for i in range(2*n -1 , -1 , -1):
        while len(stack)!=0 and s[i%n] >= stack[-1]:
            stack.pop()
        if stack and i < n:
            results[i] = stack[-1]
        stack.append(s[i%n])
    return results
    
print("result1 ",find_next_greater2([1, 19, 4, 2, 7, 5, 6]))  