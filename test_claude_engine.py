import sys
sys.path.insert(0, r"E:\İNŞAAT METRAJ PRO\yeni_proje")

try:
    from app.core.claude_engine import ClaudeEngine, _ANTHROPIC_OK, _ANTHROPIC_VER
    print(f"claude_engine import OK")
    print(f"_ANTHROPIC_OK: {_ANTHROPIC_OK}")
    print(f"_ANTHROPIC_VER: {_ANTHROPIC_VER}")
    engine = ClaudeEngine()
    print(f"ClaudeEngine OK — model: {engine.model}")
    print(f"api_key_gecerli: {engine.api_key_gecerli()}")
except Exception as e:
    print(f"HATA: {e}")
    import traceback
    traceback.print_exc()
