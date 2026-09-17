# Schema inventory

Captured 2026-09-17 10:32:23 CDT as `dv-admin` (sysadmin).

## `js_mysql_customer360.customer360.customers`

| column | type |
| --- | --- |
| customer_id | varchar(32) |
| account_id | varchar(32) |
| full_name | varchar(128) |
| national_id_masked | varchar(32) |
| date_of_birth | date |
| age_group | varchar(16) |
| gender | varchar(16) |
| email | varchar(128) |
| mobile_number_masked | varchar(32) |
| city | varchar(64) |
| province | varchar(64) |
| country | char(2) |
| postal_code | varchar(16) |
| customer_tier | varchar(16) |
| occupation | varchar(64) |
| annual_income | decimal(14,2) |
| risk_rating | varchar(16) |
| kyc_status | varchar(16) |
| pep_flag | tinyint |
| sanctions_screening_status | varchar(32) |
| account_open_date | date |
| preferred_channel | varchar(32) |
| marketing_consent | tinyint |
| created_at | timestamp(0) with time zone |
| updated_at | timestamp(0) with time zone |

Row count: **10000**

## `js_financial_ice.banking.payment_transactions`

| column | type |
| --- | --- |
| event_id | varchar |
| event_type | varchar |
| timestamp | timestamp(6) with time zone |
| transaction_id | varchar |
| account_id | varchar |
| amount | double |
| currency | varchar |
| channel | varchar |
| merchant_category | varchar |
| status | varchar |
| city | varchar |
| country | varchar |
| latitude | double |
| longitude | double |
| is_international | boolean |
| customer_tier | varchar |
| risk_score | double |
| ingested_at | timestamp(6) with time zone |
| event_date | date |

Row count: **2646867**

## `js_financial_ice.banking.fraud_alerts`

| column | type |
| --- | --- |
| event_id | varchar |
| event_type | varchar |
| timestamp | timestamp(6) with time zone |
| account_id | varchar |
| fraud_type | varchar |
| ml_score | double |
| action | varchar |
| case_id | varchar |
| event_date | date |

Row count: **532696**

## `js_financial_ice.analytics.v_customer_payment_360`

| column | type |
| --- | --- |
| customer_id | varchar |
| account_id | varchar |
| full_name | varchar |
| age_group | varchar |
| gender | varchar |
| city | varchar |
| province | varchar |
| country | varchar |
| customer_tier | varchar |
| occupation | varchar |
| annual_income | decimal(14,2) |
| customer_risk_rating | varchar |
| kyc_status | varchar |
| pep_flag | boolean |
| sanctions_screening_status | varchar |
| account_open_date | date |
| preferred_channel | varchar |
| marketing_consent | boolean |
| account_source_file | varchar |
| first_activity_date | date |
| last_activity_date | date |
| lifetime_txn_count | bigint |
| lifetime_payment_amount | double |
| lifetime_approved_count | bigint |
| lifetime_declined_count | bigint |
| lifetime_international_count | bigint |
| weighted_avg_risk_score | double |
| txn_count_30d | bigint |
| payment_amount_30d | double |
| declined_count_30d | bigint |
| last_transaction_at | timestamp(6) with time zone |
| analytics_risk_segment | varchar(8) |
| customer_batch_id | varchar |
| account_batch_id | varchar |
| latest_data_timestamp | timestamp(6) with time zone |

## View security mode

`v_customer_payment_360` is **SECURITY DEFINER** (queries execute with the view owner's privileges).

## Join-key note

`js_financial_ice.banking.fraud_alerts` has **no `transaction_id`** column. The valid join keys to `payment_transactions` are `account_id` (with `timestamp`/`event_date` for correlation). No synthetic relationship was invented.
