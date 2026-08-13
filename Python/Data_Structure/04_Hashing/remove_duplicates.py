all_email_signups = [
    "ram@gmail.com",
    "shyam@gmail.com",
    "ram@gmail.com",
    "sita@gmail.com",
    "ram@gmail.com",
    "shyam@gmail.com",
    "ram@gmail.com",
]

def remove_duplicates(list):
    unique = []
    seen = set()

    for email in list:
        if email not in seen:
            unique.append(email)
            seen.add(email)
    return unique

print(remove_duplicates(all_email_signups))

# here O(n) is the time complexity of the function 
# because we are iterating through the list once and 
# adding the elements to the set

# how is this example of hashing ? 
# hashing is a technique of converting an input of any type 
# into a fixed-size value that can be used to 
# access the element in constant time

# in this case we are using a set to store the elements 
# which is a hash table implementation
