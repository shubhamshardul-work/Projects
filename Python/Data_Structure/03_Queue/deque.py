queue = []

# ENQUEUE - Add to back
queue.append(1)
queue.append(2)
queue.append(3)
print(queue)  # [1, 2, 3]

# DEQUEUE - Remove from front
front = queue.pop(0)  # ❌ O(n) - shifts all elements!
print(front)  # 1
print(queue)  # [2, 3]
# Problem: pop(0) is O(n) because it shifts all remaining elements!
# Using collections.deque (Recommended) ✅

from collections import deque

queue = deque()

# ENQUEUE - Add to back
queue.append(1)
queue.append(2)
queue.append(3)
print(queue)  # deque([1, 2, 3])

# DEQUEUE - Remove from front
front = queue.popleft()  # ✅ O(1)
print(front)  # 1
print(queue)  # deque([2, 3])

# PEEK - View front
print(queue[0])  # 2

# SIZE
print(len(queue))  # 2

# IS EMPTY
print(len(queue) == 0)  # False
# Why deque? Both append() and popleft() are O(1)!