def is_valid_paranthesis(stringg):
    stack = []
    matching = {"[":"]", "{":"}", "(":")"}

    for char in stringg:
        if char in matching:
            stack.append(char)
        else:
            if not stack or matching[stack.pop()] != char:
                return False
    return len(stack) == 0

print(is_valid_paranthesis("{[()]}"))
print(is_valid_paranthesis("{[()]}}"))
print(is_valid_paranthesis("([)]"))
