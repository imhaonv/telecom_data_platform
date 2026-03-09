-- dbt/models/silver/dim_subscriptions.sql
{{ config(materialized='table', schema='silver') }}

WITH subscription_data AS (
    SELECT 
        subscription_id,
        customer_id,
        package_name,
        package_type,
        data_limit_gb,
        daily_limit_mb,
        speed_mbps,
        price_monthly_vnd,
        activation_date,
        expiry_date,
        auto_renewal,
        status,
        device_type,
        payment_method,
        zone,
        customer_segment,
        subscription_duration_days,
        days_until_expiry,
        total_used_gb,
        remaining_gb,
        usage_percentage,
        is_suspicious,
        anomaly_reason,
        created_at,
        last_updated
    FROM {{ source('bronze', 'telecom_subscriptions') }}
    WHERE activation_date IS NOT NULL
),

enriched AS (
    SELECT 
        *,
        CASE 
            WHEN days_until_expiry < 0 THEN 'expired'
            WHEN days_until_expiry <= 7 THEN 'expiring_soon'
            ELSE 'active'
        END AS expiry_status,
        price_monthly_vnd / NULLIF(data_limit_gb, 0) AS price_per_gb,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY activation_date DESC) AS customer_subscription_rank
    FROM subscription_data
)

SELECT * FROM enriched