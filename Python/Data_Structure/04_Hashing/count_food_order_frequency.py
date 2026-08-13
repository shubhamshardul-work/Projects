orders = ["pizza","pasta","pizza","burger","pasta","pizza"]

def count_freq(list):
    freq = {}
    for item in list:
        if item in freq:
            freq[item] = freq[item] + 1
        else:
            freq[item] = 1
    return freq

print(count_freq(orders))