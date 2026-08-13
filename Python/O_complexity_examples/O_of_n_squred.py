# defination of O of n Squred 
# in this approach we iterate through the list n times and n times again 
# that is one loop inside another

# this is O(n^2) because we iterate through the list n times and n times again

def find_duplicates(list):
    dup_names_list = []
    dedup_list = list.copy()

    for i in range(len(list)):
        for j in range(len(list)):
            if i == j:
                continue
        
            if list[i] == list[j] and list[i] not in dup_names_list:
                dup_names_list.append(list[i])
                print(f"dup name = {list[i]}")
    return dup_names_list

list = ["anirudh", "satyam", "rahul", "manisha", "sachin", "anirudh", "manisha", "shardul", "anirudh", "manisha", "sachin", "anirudh", "manisha", "shardul"]

dup_names_list= find_duplicates(list)
print("dup name list", dup_names_list)

for names in dup_names_list:
    while names in list:
        list.remove(names)

print("list =",list)

list.extend(dup_names_list)
print("final list =",list)


# better way to do this is using sets but that is O(n log n)
