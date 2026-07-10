# Build034 M1-T01 Legacy Asset Inventory

本报告由仓库当前 `main` 工作树自动扫描生成。

## 扫描结论

- **excel_parser**: 10 个候选资产
- **pdf_parser**: 3 个候选资产
- **compare**: 8 个候选资产
- **review**: 6 个候选资产
- **error_report**: 6 个候选资产
- **sales_db**: 11 个候选资产
- **bank**: 20 个候选资产

## 文件级资产

| Category | Path | Symbol | Evidence | Score | Recommendation |
|---|---|---|---|---:|---|
| bank | `apps/request-employee-platform/src/api/routes/bank.py` | `BankReconciliationSettingIn, list_reconciliation_settings, upsert_reconciliation_setting, export_reconciliation_settings_excel, export_reconciliation_settings_pdf, get_reconciliation_period, list_transactions, list_reconciliation` | /api/bank, bank reconciliation, transactions, reconciliation | 4 | REUSE_OR_REFACTOR |
| bank | `apps/request-employee-platform/tests/test_build032r1_delivery_smoke.py` | `-` | /api/bank, reconciliation | 2 | REUSE_TEST |
| bank | `apps/request-employee-platform/tests/test_build032r3_bank_reconciliation_cutoff.py` | `test_bank_reconciliation_cutoff_is_persistent_and_calculates_next_start, test_bank_reconciliation_period_endpoint, test_bank_reconciliation_settings_exports` | /api/bank, reconciliation | 2 | REUSE_TEST |
| bank | `apps/request-employee-platform/src/api/routes/customer_reconciliation.py` | `CustomerReconciliationCutoffIn, get_next_reconciliation_scope, customer_reconciliation_page, export_customer_reconciliation_cutoffs_csv, export_customer_reconciliation_cutoffs_excel, export_customer_reconciliation_cutoffs_pdf` | reconciliation | 1 | REVIEW_MANUALLY |
| bank | `apps/request-employee-platform/src/main.py` | `-` | reconciliation | 1 | REVIEW_MANUALLY |
| bank | `apps/request-employee-platform/src/services/customer_reconciliation_export_adapter.py` | `customer_reconciliation_columns, normalize_customer_reconciliation_row, build_customer_reconciliation_export_model` | reconciliation | 1 | REVIEW_MANUALLY |
| bank | `apps/request-employee-platform/src/services/customer_reconciliation_route_export_bridge.py` | `build_customer_reconciliation_route_export_model, export_customer_reconciliation_excel, export_customer_reconciliation_pdf, export_customer_reconciliation_csv` | reconciliation | 1 | REVIEW_MANUALLY |
| bank | `apps/request-employee-platform/tests/test_build032r4_customer_reconciliation_v2.py` | `test_customer_reconciliation_page_available` | reconciliation | 1 | REUSE_TEST |
| bank | `apps/request-employee-platform/tests/test_build032r4_v21_dashboard_guard.py` | `-` | reconciliation | 1 | REUSE_TEST |
| bank | `apps/request-employee-platform/tests/test_build032r4_v25_contract_multilang_search_edit_export.py` | `-` | reconciliation | 1 | REUSE_TEST |
| bank | `apps/request-employee-platform/tests/test_build032r4_v261_pdf_data_selfcheck.py` | `-` | reconciliation | 1 | REUSE_TEST |
| bank | `apps/request-employee-platform/tests/test_build032r4_v264_pdf_bom_compat_mixed_language.py` | `-` | reconciliation | 1 | REUSE_TEST |
| bank | `apps/request-employee-platform/tests/test_build032r4_v26_priority_acceptance.py` | `-` | reconciliation | 1 | REUSE_TEST |
| bank | `apps/request-employee-platform/tests/test_build033r2_t001_customer_route_export_bridge.py` | `-` | reconciliation | 1 | REUSE_TEST |
| bank | `apps/request-employee-platform/tests/test_build033r2_t002_customer_csv_endpoint.py` | `test_customer_reconciliation_csv_export_endpoint_uses_export_engine` | reconciliation | 1 | REUSE_TEST |
| bank | `apps/request-employee-platform/tests/test_build033r2_t003_customer_excel_endpoint.py` | `test_customer_reconciliation_excel_export_endpoint_uses_export_engine_without_openpyxl` | reconciliation | 1 | REUSE_TEST |
| bank | `apps/request-employee-platform/tests/test_build033r2_t004_customer_pdf_endpoint.py` | `test_customer_reconciliation_pdf_export_endpoint_uses_export_engine` | reconciliation | 1 | REUSE_TEST |
| bank | `apps/request-employee-platform/tests/test_build033r2a_customer_reconciliation_export_model.py` | `test_customer_reconciliation_columns_multilang, test_customer_reconciliation_export_model_excludes_action_and_totals, test_normalize_customer_reconciliation_row_removes_ui_fields, test_customer_reconciliation_export_model_csv_bridge, test_customer_reconciliation_export_model_pdf_selfcheck` | reconciliation | 1 | REUSE_TEST |
| bank | `apps/request-employee-platform/tests/test_build033r3_t001_ui_excel_integration.py` | `test_customer_reconciliation_page_contains_build033_excel_binding` | reconciliation | 1 | REUSE_TEST |
| bank | `apps/request-employee-platform/tests/test_build033r3_t002_ui_pdf_integration.py` | `test_customer_reconciliation_page_contains_build033_pdf_binding` | reconciliation | 1 | REUSE_TEST |
| compare | `apps/request-employee-platform/src/services/request_compare_service.py` | `-` | compare(, diff, mismatch, difference, CompareResult | 5 | REUSE_OR_REFACTOR |
| compare | `apps/request-employee-platform/src/domain/request_compare.py` | `CompareDifference, RequestCompareResult` | diff, mismatch, difference, CompareResult | 4 | REUSE_OR_REFACTOR |
| compare | `apps/request-employee-platform/src/repositories/review_repository.py` | `-` | compare(, diff, mismatch, difference | 4 | REUSE_OR_REFACTOR |
| compare | `apps/request-employee-platform/src/services/request_compare_persistence_service.py` | `-` | compare(, diff, difference | 3 | REUSE_OR_REFACTOR |
| compare | `apps/request-employee-platform/src/api/routes/request_auto_compare.py` | `-` | compare-parser-json, compare( | 2 | REUSE_OR_REFACTOR |
| compare | `apps/request-employee-platform/src/db/models.py` | `-` | diff, difference | 2 | REUSE_OR_REFACTOR |
| compare | `apps/request-employee-platform/src/web/static/review.html` | `-` | diff, difference | 2 | REUSE_OR_REFACTOR |
| compare | `apps/request-employee-platform/src/api/routes/request_compare.py` | `-` | compare( | 1 | REVIEW_MANUALLY |
| error_report | `apps/request-employee-platform/src/domain/request_compare.py` | `CompareDifference` | mismatch, difference | 2 | REFACTOR |
| error_report | `apps/request-employee-platform/src/repositories/review_repository.py` | `-` | mismatch, difference | 2 | REFACTOR |
| error_report | `apps/request-employee-platform/src/services/request_compare_service.py` | `-` | mismatch, difference | 2 | REFACTOR |
| error_report | `apps/request-employee-platform/src/db/models.py` | `-` | difference | 1 | REVIEW_MANUALLY |
| error_report | `apps/request-employee-platform/src/services/request_compare_persistence_service.py` | `-` | difference | 1 | REVIEW_MANUALLY |
| error_report | `apps/request-employee-platform/src/web/static/review.html` | `-` | difference | 1 | REVIEW_MANUALLY |
| excel_parser | `apps/request-employee-platform/tests/test_build033r2_t003_customer_excel_endpoint.py` | `_xlsx_text, test_customer_reconciliation_excel_export_endpoint_uses_export_engine_without_openpyxl` | openpyxl, xlsx | 2 | REUSE_TEST |
| excel_parser | `apps/request-employee-platform/src/api/routes/bank.py` | `-` | xlsx | 1 | REVIEW_MANUALLY |
| excel_parser | `apps/request-employee-platform/src/api/routes/customer_reconciliation.py` | `-` | xlsx | 1 | REVIEW_MANUALLY |
| excel_parser | `apps/request-employee-platform/src/api/routes/sales.py` | `-` | xlsx | 1 | REVIEW_MANUALLY |
| excel_parser | `apps/request-employee-platform/src/services/export_engine.py` | `-` | xlsx | 1 | REVIEW_MANUALLY |
| excel_parser | `apps/request-employee-platform/src/services/export_service.py` | `export_xlsx` | xlsx | 1 | REVIEW_MANUALLY |
| excel_parser | `apps/request-employee-platform/tests/test_build032r2_sales_search_export.py` | `test_sales_xlsx_export_is_real_zip_package` | xlsx | 1 | REUSE_TEST |
| excel_parser | `apps/request-employee-platform/tests/test_build032r3_bank_reconciliation_cutoff.py` | `-` | xlsx | 1 | REUSE_TEST |
| excel_parser | `apps/request-employee-platform/tests/test_build032r4_customer_reconciliation_v2.py` | `-` | xlsx | 1 | REUSE_TEST |
| excel_parser | `apps/request-employee-platform/tests/test_build032r4_v25_contract_multilang_search_edit_export.py` | `-` | xlsx | 1 | REUSE_TEST |
| pdf_parser | `apps/request-employee-platform/src/api/routes/customer_reconciliation.py` | `-` | application/pdf | 1 | REVIEW_MANUALLY |
| pdf_parser | `apps/request-employee-platform/src/services/export_engine.py` | `-` | application/pdf | 1 | REVIEW_MANUALLY |
| pdf_parser | `apps/request-employee-platform/src/services/export_service.py` | `-` | application/pdf | 1 | REVIEW_MANUALLY |
| review | `apps/request-employee-platform/src/api/routes/request_compare.py` | `ResolveRequest, resolve` | review-tasks, resolve | 2 | REUSE_OR_REFACTOR |
| review | `apps/request-employee-platform/src/api/routes/customer_reconciliation.py` | `-` | cancel | 1 | REVIEW_MANUALLY |
| review | `apps/request-employee-platform/src/db/migrations.py` | `-` | resolve | 1 | REVIEW_MANUALLY |
| review | `apps/request-employee-platform/src/db/models.py` | `-` | resolve | 1 | REVIEW_MANUALLY |
| review | `apps/request-employee-platform/src/repositories/review_repository.py` | `resolve` | resolve | 1 | REVIEW_MANUALLY |
| review | `apps/request-employee-platform/src/web/static/review.html` | `-` | review-tasks | 1 | REVIEW_MANUALLY |
| sales_db | `apps/request-employee-platform/src/api/routes/sales.py` | `-` | SalesRecordORM, /api/sales, request_no | 3 | REUSE_OR_REFACTOR |
| sales_db | `apps/request-employee-platform/src/db/models.py` | `SalesRecordORM` | SalesRecordORM, request_no, sales_record | 3 | REUSE_OR_REFACTOR |
| sales_db | `apps/request-employee-platform/src/web/static/sales.html` | `-` | /api/sales, request_no | 2 | REUSE_OR_REFACTOR |
| sales_db | `apps/request-employee-platform/src/db/migrations.py` | `-` | sales_record | 1 | REVIEW_MANUALLY |
| sales_db | `apps/request-employee-platform/src/domain/request_compare.py` | `-` | request_no | 1 | REVIEW_MANUALLY |
| sales_db | `apps/request-employee-platform/src/repositories/review_repository.py` | `-` | request_no | 1 | REVIEW_MANUALLY |
| sales_db | `apps/request-employee-platform/src/services/dashboard_service.py` | `-` | SalesRecordORM | 1 | REVIEW_MANUALLY |
| sales_db | `apps/request-employee-platform/src/services/request_compare_service.py` | `-` | request_no | 1 | REVIEW_MANUALLY |
| sales_db | `apps/request-employee-platform/src/services/request_snapshot_adapter.py` | `-` | request_no | 1 | REVIEW_MANUALLY |
| sales_db | `apps/request-employee-platform/tests/fixtures/request_excel_parser_sample.json` | `-` | request_no | 1 | REUSE_TEST |
| sales_db | `apps/request-employee-platform/tests/test_build032r2_sales_search_export.py` | `-` | /api/sales | 1 | REUSE_TEST |

## 下一步决策规则

- `REUSE_TEST`：保留为回归基线。
- `REUSE_OR_ADAPT`：优先封装为 Import/Parser Adapter，不重写解析核心。
- `REUSE_OR_REFACTOR`：保留现有 API/DB 兼容，内部逐步重构。
- `REFACTOR`：保留机器结果，补错误文件与 Web 展示。
- `REVIEW_MANUALLY`：下一 Task 人工确认。

## M1-T02 输入

从本报告中选出 Excel Parser 的最高分候选文件，制作标准 `RequestDocument` Adapter。
