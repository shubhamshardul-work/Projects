def bsort(arr):
    for pass_num in range(len(arr)-1):
        for i in range(len(arr)-1-pass_num):
            if arr[i] > arr[i+1]:
                arr[i], arr[i+1] = arr[i+1], arr[i]
    return arr
    
    
print(bsort([23, 43, 35, 65, 13]))