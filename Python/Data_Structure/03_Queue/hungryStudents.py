from collections import deque

def students_unable_to_eat(students, sandwiches):
    """
    students = [1,1,1,0,0,1]  (1=circular preference, 0=square)
    sandwiches = [0,1,0,1,0,1]
    Return: how many students can't eat
    """
    queue = deque(students)
    stack = sandwiches
    index = 0
    rotation = 0
    
    while len(queue) > index and queue:
        # If top student matches top sandwich
        print("-----1-----")
        if queue[0] == stack[-1]:
            print("-----2-----")
            queue.popleft()
            print("-----3-----")
            stack.pop()
            print("-----4-----")
        else:
            print("-----5-----")
            # Student goes to back of queue
            queue.append(queue.popleft())
            print("-----6-----")
    
    return len(queue)

print(students_unable_to_eat([1,1,1,0,0,1], [0,1,0,1,0,1]))