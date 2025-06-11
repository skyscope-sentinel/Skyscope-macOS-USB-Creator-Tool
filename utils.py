# This is utils.py

# ANSI escape codes
GREEN = '\033[92m'
RESET = '\033[0m'

def cprint(text, color=None):
    """Prints text in a specified color."""
    if color == "green":
        print(GREEN + text + RESET)
    else:
        print(text)

def head(text):
    """Prints a heading in green."""
    cprint(text, color="green")

# Example usage (optional, for testing)
if __name__ == "__main__":
    head("This is a green heading")
    cprint("This is also green text", color="green")
    print("This is default color text")
