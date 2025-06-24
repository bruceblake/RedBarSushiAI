# Comprehensive Test Report

## Executive Summary

### Test Results Overview:
- **FSM Unit Tests**: ✅ **37/37 passed** (100% success)
- **AI Components Tests**: ⚠️ 10 passed, 4 failed
- **Cart Agent Tests**: ✅ **8/8 passed** (100% success)
- **Other Unit Tests**: ❌ 11 collection errors (import issues)
- **Integration Tests**: ❌ 1 collection error
- **E2E Tests**: ❌ 2 collection errors

### Key Issues:
1. **OpenAI API Key**: The API key is being rejected (401 errors)
2. **Missing Modules**: Several imports failing (e.g., `app.db.crud_order_async`)
3. **Redis Connection**: Cannot connect to Redis (Error 22)
4. **Pydantic Warnings**: Multiple deprecation warnings for Pydantic v2 migration

## Detailed Results

## FSM Unit Tests
../usr/local/lib/python3.11/site-packages/pydantic/fields.py:1042: 65 warnings
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 37 passed, 65 warnings in 1.49s ========================

## AI Components Tests
../usr/local/lib/python3.11/site-packages/pydantic/fields.py:1042: 65 warnings
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================== 4 failed, 10 passed, 65 warnings in 1.80s ===================

## Cart Agent Tests
  /app/app/schemas/menu.py:226: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.10/migration/
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 8 passed, 71 warnings in 1.58s ========================

## All Unit Tests Summary
  /usr/local/lib/python3.11/site-packages/pydantic/fields.py:1042: PydanticDeprecatedSince20: Using extra keyword arguments on `Field` is deprecated and will be removed. Use `json_schema_extra` instead. (Extra keys: 'env'). Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.10/migration/
  /usr/local/lib/python3.11/site-packages/pydantic/_internal/_config.py:295: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.10/migration/
  /app/app/schemas/menu.py:226: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.10/migration/
!!!!!!!!!!!!!!!!!!! Interrupted: 11 errors during collection !!!!!!!!!!!!!!!!!!!
======================= 71 warnings, 11 errors in 3.57s ========================

## Integration Tests Summary
  /usr/local/lib/python3.11/site-packages/pydantic/fields.py:1042: PydanticDeprecatedSince20: Using extra keyword arguments on `Field` is deprecated and will be removed. Use `json_schema_extra` instead. (Extra keys: 'env'). Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.10/migration/
  /usr/local/lib/python3.11/site-packages/pydantic/_internal/_config.py:295: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.10/migration/
  /app/app/schemas/menu.py:226: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.10/migration/
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
======================== 71 warnings, 1 error in 1.64s =========================

## E2E Tests Summary
  /app/app/api/order/checkout.py:62: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.10/migration/
  /app/app/api/order/confirmation.py:45: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.10/migration/
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
======================== 80 warnings, 2 errors in 2.38s ========================
