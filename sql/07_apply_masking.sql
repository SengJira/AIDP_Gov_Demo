-- Phase 6: dynamic column masking.
--
-- SEP built-in access control does NOT expose SQL syntax for column masks.
-- Masks are BIAC objects created through the REST API
-- (POST /api/v1/biac/expressions/columnMask) and attached to a role's
-- table entity (POST /api/v1/biac/roles/{roleId}/columnMasks).
-- scripts/configure_masking.py performs these calls idempotently.
--
-- This file documents the expressions for review. "@column" is the
-- placeholder SEP substitutes with the masked column's value.

-- gov_demo_mask_nid_partial  (national ID, fraud analyst: *********0123)
--   CASE WHEN "@column" IS NULL THEN NULL
--        WHEN length("@column") <= 4 THEN repeat('*', length("@column"))
--        ELSE repeat('*', length("@column") - 4) || substr("@column", -4) END

-- gov_demo_mask_mobile_partial  (fraud analyst: ******5678)
--   same shape as above

-- gov_demo_mask_email_partial  (fraud analyst: j******@example.com)
--   CASE WHEN "@column" IS NULL THEN NULL
--        WHEN strpos("@column",'@') > 1
--          THEN substr("@column",1,1) || '******' || substr("@column", strpos("@column",'@'))
--        ELSE 'hidden@example.com' END

-- gov_demo_mask_name_partial   (fraud analyst: Somchai P******)
--   CASE WHEN "@column" IS NULL THEN NULL
--        WHEN "@column" ~ '^\S+\s+\S'
--          THEN regexp_replace("@column", '^(\S+)\s+(\S).*', '$1 $2******')
--        ELSE "@column" || ' ******' END

-- gov_demo_mask_full_string    (business/regional: *************)
--   CASE WHEN "@column" IS NULL THEN NULL ELSE repeat('*', length("@column")) END

-- gov_demo_mask_mobile_full    (business/regional: **********)
--   CASE WHEN "@column" IS NULL THEN NULL ELSE '**********' END

-- gov_demo_mask_email_full     (business/regional: hidden@example.com)
--   CASE WHEN "@column" IS NULL THEN NULL ELSE 'hidden@example.com' END

-- gov_demo_mask_name_full      (business/regional: Protected Customer)
--   CASE WHEN "@column" IS NULL THEN NULL ELSE 'Protected Customer' END

-- gov_demo_mask_account_partial (business/regional: ************1234)
--   CASE WHEN "@column" IS NULL THEN NULL
--        WHEN length("@column") <= 4 THEN repeat('*', length("@column"))
--        ELSE repeat('*', length("@column") - 4) || substr("@column", -4) END
