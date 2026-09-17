-- Phase 7: row-level filtering.
--
-- Like column masks, row filters are BIAC objects managed through the REST
-- API (POST /api/v1/biac/expressions/rowFilter,
-- POST /api/v1/biac/roles/{roleId}/rowFilters) - there is no SQL syntax.
-- scripts/configure_row_filters.py applies them idempotently.
--
-- SEMANTICS (verified live on this cluster): the expression is a
-- VISIBILITY condition - rows where it evaluates TRUE are returned,
-- everything else is hidden. NULL -> hidden.

-- gov_demo_fraud_only     -> shows only fraud_flag OR risk_score >= 0.70
--   COALESCE(fraud_flag, false) OR COALESCE(risk_score, 0) >= 0.70

-- gov_demo_thailand_only  -> shows only country_code = 'TH' rows
--   country_code = 'TH'

-- gov_demo_approved_only  -> shows only transaction_status = 'APPROVED'
--   transaction_status = 'APPROVED'
