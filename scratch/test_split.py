
val = None
try:
    res = val.split(":")[1] if val and ":" in val else 0
    print(f"Result 1: {res}")
except Exception as e:
    print(f"Error 1: {e}")

try:
    # This is what I have in code (roughly)
    res = val.split(": ")[1] if ": " in str(val) else 0
    print(f"Result 2: {res}")
except Exception as e:
    print(f"Error 2: {e}")
