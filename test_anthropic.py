import sys
print("Python:", sys.executable)
print("Version:", sys.version)
try:
    import anthropic
    print("anthropic OK:", anthropic.__version__)
except Exception as e:
    print("anthropic HATA:", e)
