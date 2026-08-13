# sliding window example
l = [4, 5, 2, 9, 1, 3, 4]
def highest_sum(l, wSize):
    current_sum = sum(l[0:wSize])
    highest_sum = current_sum
    
    print("window: ", l[:3], "  Sum: ", current_sum)
    
    for i in range(wSize, len(l)):
        left = l[i - wSize]
        rightOut = l[i]
        # ❌ Recalculating: O(wSize) per iteration
        # cur_sum = sum(current_window)
        # With the above redundant sum(): O(n × wSize) — not optimal!
        # O(n) — true sliding window efficiency below
        current_sum = current_sum - left + rightOut
        current_window = l[i-wSize+1 : i+1]
        print("window: ", current_window, "  Sum: ", current_sum)
        
        if current_sum > highest_sum:
            highest_sum = current_sum
    return highest_sum
    
s = highest_sum(l, 3)
print("Highest sum: ", s) 