# definition of O of n
# in this approach we iterate through the list once
# for example linear search

def find_name(list, name):
    for i in list:
        if i == name:
            print(f"name found = {name}")
            return True
    print("name not found")
    return False

print(find_name(["shardul", "anirudh", "manisha", "sachin"], "manisha"))

# this is O(n) because we iterate through the list once

# finding duplicates example in O(n) - also done in the O(n^2) example 


def find_dup_using_sets(list):
    seen = set()
    dup = []

    for name in list:
        if name in seen and name not in dup:
            dup.append(name)
        seen.add(name)
    return dup

list2 = ["anirudh", "satyam", "rahul", "manisha", "sachin", "anirudh", "manisha", "shardul", "anirudh", "manisha", "sachin", "anirudh", "manisha", "shardul"]

dup_name_list = find_dup_using_sets(list2)
print("dup name list", dup_name_list)
