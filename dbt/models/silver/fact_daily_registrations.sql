-- dbt/models/silver/fact_daily_registrations.sql
{{ config(materialized='table', schema='silver') }}

SELECT 
    DATE(created_at) AS registration_date,
    package_name,
    package_type,
    zone,
    device_type,
    payment_method,
    COUNT(*) AS total_registrations,
    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_registrations,
    SUM(CASE WHEN is_suspicious THEN 1 ELSE 0 END) AS suspicious_registrations,
    SUM(CASE WHEN auto_renewal THEN 1 ELSE 0 END) AS auto_renewal_registrations,
    AVG(price_monthly_vnd) AS avg_price,
    COUNT(DISTINCT customer_id) AS unique_customers
FROM {{ ref('dim_subscriptions') }}
GROUP BY 1, 2, 3, 4, 5, 6