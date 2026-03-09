-- dbt/models/gold/customer_behavior.sql
{{ config(materialized='table', schema='gold') }}

WITH customer_lifetime AS (
    SELECT 
        customer_id,
        MIN(activation_date) AS first_subscription_date,
        MAX(activation_date) AS last_subscription_date,
        COUNT(DISTINCT subscription_id) AS total_subscriptions,
        SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS total_cancellations,
        AVG(price_monthly_vnd) AS avg_spending,
        MAX(package_name) AS current_package,
        MAX(auto_renewal) AS is_auto_renewal,
        DATEDIFF(DAY, MIN(activation_date), CURRENT_DATE) AS customer_lifetime_days
    FROM {{ ref('dim_subscriptions') }}
    GROUP BY customer_id
),

customer_segments AS (
    SELECT 
        customer_id,
        CASE 
            WHEN customer_lifetime_days > 365 AND total_subscriptions > 3 THEN 'loyal'
            WHEN avg_spending > 300000 THEN 'high_value'
            WHEN total_cancellations > 0 THEN 'churn_risk'
            WHEN customer_lifetime_days < 30 THEN 'new'
            ELSE 'regular'
        END AS customer_segment,
        first_subscription_date,
        last_subscription_date,
        total_subscriptions,
        total_cancellations,
        avg_spending,
        current_package,
        is_auto_renewal,
        customer_lifetime_days
    FROM customer_lifetime
)

SELECT * FROM customer_segments