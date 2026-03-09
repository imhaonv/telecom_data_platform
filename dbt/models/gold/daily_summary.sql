-- dbt/models/gold/daily_summary.sql
{{ config(materialized='table', schema='gold') }}

WITH daily_stats AS (
    SELECT 
        registration_date,
        -- Tổng số đăng ký
        SUM(total_registrations) AS total_subscriptions,
        SUM(cancelled_registrations) AS total_cancellations,
        SUM(suspicious_registrations) AS total_suspicious,
        
        -- Gói được đăng ký nhiều nhất
        FIRST_VALUE(package_name) OVER (
            PARTITION BY registration_date 
            ORDER BY total_registrations DESC
        ) AS top_package,
        
        -- Zone có nhiều đăng ký nhất
        FIRST_VALUE(zone) OVER (
            PARTITION BY registration_date 
            ORDER BY total_registrations DESC
        ) AS top_zone,
        
        -- Tỷ lệ hủy
        SUM(cancelled_registrations) * 100.0 / NULLIF(SUM(total_registrations), 0) AS cancellation_rate,
        
        -- Số lượng users mới
        SUM(CASE WHEN unique_customers = 1 THEN 1 ELSE 0 END) AS new_customers,
        
        -- Doanh thu ước tính
        SUM(total_registrations * avg_price) AS estimated_revenue
        
    FROM {{ ref('fact_daily_registrations') }}
    GROUP BY registration_date
),

anomaly_detection AS (
    SELECT 
        registration_date,
        package_name,
        total_registrations,
        AVG(total_registrations) OVER (
            ORDER BY registration_date 
            ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ) AS avg_7day,
        STDDEV(total_registrations) OVER (
            ORDER BY registration_date 
            ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ) AS std_7day
    FROM {{ ref('fact_daily_registrations') }}
    WHERE package_name IN ('Data Tốc Cao', 'Mimax')
),

anomalies AS (
    SELECT 
        registration_date,
        package_name,
        total_registrations,
        CASE 
            WHEN total_registrations > avg_7day + (2 * std_7day) THEN 'high_anomaly'
            WHEN total_registrations < avg_7day - (2 * std_7day) THEN 'low_anomaly'
            ELSE 'normal'
        END AS anomaly_status
    FROM anomaly_detection
    WHERE avg_7day IS NOT NULL
)

SELECT 
    ds.*,
    a.package_name AS anomaly_package,
    a.anomaly_status,
    a.total_registrations AS anomaly_package_registrations,
    CURRENT_TIMESTAMP AS generated_at
FROM daily_stats ds
LEFT JOIN anomalies a ON ds.registration_date = a.registration_date 
    AND a.anomaly_status != 'normal'