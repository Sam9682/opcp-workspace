import sys

print("=== import backend modules ===")
try:
    import app.oracle.ai_providers as aip
    import app.oracle.service
    import app.oracle.router
    import app.oracle.schemas
    import app.config
    print("IMPORT_OK: all backend modules imported cleanly")
except Exception as e:
    print("IMPORT_FAIL:", repr(e))
    sys.exit(1)

print("=== factory check ===")
try:
    from app.oracle.ai_providers import get_ai_provider, OpcpCompanionProvider
    prov = get_ai_provider("opcp_companion")
    ok = isinstance(prov, OpcpCompanionProvider)
    print(f"FACTORY: type={type(prov).__name__} is_OpcpCompanionProvider={ok}")
    if not ok:
        sys.exit(2)
except Exception as e:
    print("FACTORY_FAIL:", repr(e))
    sys.exit(2)

print("=== schemas check ===")
try:
    from app.oracle.schemas import Source, OracleResponse, OracleQuery
    s = Source(title="t", file_path="/p", similarity=0.5)
    r = OracleResponse.model_fields.get("sources")
    q = OracleQuery.model_fields.get("ai_provider")
    print("SCHEMA_OK: Source built; OracleResponse has sources field:", r is not None)
except Exception as e:
    print("SCHEMA_FAIL:", repr(e))
    sys.exit(3)

print("ALL_CHECKS_DONE")
