import sys
print("Python:", sys.executable)
try:
    import anthropic
    print("anthropic:", anthropic.__version__, "- OK")
except ImportError as e:
    print("ImportError:", e)

with open(r"E:\İNŞAAT METRAJ PRO\yeni_proje\anthropic_check.txt", "w") as f:
    f.write(f"Python: {sys.executable}\n")
    try:
        import anthropic
        f.write(f"anthropic: {anthropic.__version__} OK\n")
    except ImportError as e:
        f.write(f"ImportError: {e}\n")
