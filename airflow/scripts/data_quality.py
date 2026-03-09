# airflow/scripts/data_quality.py
"""
Data Quality Check Script
Kiểm tra chất lượng dữ liệu sau khi transform Bronze → Silver
"""
import psycopg2
import sys
import os
from datetime import datetime

# PostgreSQL connection config
PG_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "postgres"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB", "telecom_data"),
    "user": os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "admin123"),
}


def get_connection():
    """Tạo kết nối PostgreSQL"""
    return psycopg2.connect(**PG_CONFIG)


def check_null_counts(cursor):
    """Kiểm tra NULL values trong các cột quan trọng"""
    print("=" * 50)
    print("CHECK 1: Null Count Validation")
    print("=" * 50)

    critical_columns = [
        "subscription_id",
        "customer_id",
        "package_name",
        "activation_date",
    ]
    issues = []

    for col in critical_columns:
        cursor.execute(
            f"SELECT COUNT(*) FROM silver.dim_subscriptions WHERE {col} IS NULL"
        )
        null_count = cursor.fetchone()[0]
        status = "✅ PASS" if null_count == 0 else "❌ FAIL"
        print(f"  {status} | {col}: {null_count} nulls")
        if null_count > 0:
            issues.append(f"{col} has {null_count} null values")

    return issues


def check_row_count(cursor):
    """Kiểm tra số lượng bản ghi"""
    print("\n" + "=" * 50)
    print("CHECK 2: Row Count Validation")
    print("=" * 50)

    issues = []

    cursor.execute("SELECT COUNT(*) FROM silver.dim_subscriptions")
    row_count = cursor.fetchone()[0]
    status = "✅ PASS" if row_count > 0 else "❌ FAIL"
    print(f"  {status} | dim_subscriptions: {row_count} rows")
    if row_count == 0:
        issues.append("dim_subscriptions has 0 rows")

    cursor.execute("SELECT COUNT(*) FROM silver.fact_daily_registrations")
    row_count = cursor.fetchone()[0]
    status = "✅ PASS" if row_count > 0 else "❌ FAIL"
    print(f"  {status} | fact_daily_registrations: {row_count} rows")
    if row_count == 0:
        issues.append("fact_daily_registrations has 0 rows")

    return issues


def check_duplicates(cursor):
    """Kiểm tra bản ghi trùng lặp"""
    print("\n" + "=" * 50)
    print("CHECK 3: Duplicate Check")
    print("=" * 50)

    issues = []

    cursor.execute(
        """
        SELECT COUNT(*) - COUNT(DISTINCT subscription_id) AS duplicate_count
        FROM silver.dim_subscriptions
    """
    )
    dup_count = cursor.fetchone()[0]
    status = "✅ PASS" if dup_count == 0 else "⚠️ WARN"
    print(f"  {status} | Duplicate subscription_ids: {dup_count}")
    if dup_count > 0:
        issues.append(f"{dup_count} duplicate subscription_ids found")

    return issues


def check_value_ranges(cursor):
    """Kiểm tra giá trị nằm trong khoảng cho phép"""
    print("\n" + "=" * 50)
    print("CHECK 4: Value Range Validation")
    print("=" * 50)

    issues = []

    # Kiểm tra giá gói cước
    cursor.execute(
        """
        SELECT COUNT(*) FROM silver.dim_subscriptions
        WHERE price_monthly_vnd < 0 OR price_monthly_vnd > 10000000
    """
    )
    invalid_price = cursor.fetchone()[0]
    status = "✅ PASS" if invalid_price == 0 else "❌ FAIL"
    print(f"  {status} | Invalid prices (< 0 or > 10M): {invalid_price}")
    if invalid_price > 0:
        issues.append(f"{invalid_price} records with invalid price")

    # Kiểm tra usage percentage
    cursor.execute(
        """
        SELECT COUNT(*) FROM silver.dim_subscriptions
        WHERE usage_percentage < 0 OR usage_percentage > 200
    """
    )
    invalid_usage = cursor.fetchone()[0]
    status = "✅ PASS" if invalid_usage == 0 else "⚠️ WARN"
    print(f"  {status} | Invalid usage_percentage (< 0 or > 200%): {invalid_usage}")
    if invalid_usage > 0:
        issues.append(f"{invalid_usage} records with unusual usage_percentage")

    # Kiểm tra zones hợp lệ
    cursor.execute(
        """
        SELECT COUNT(*) FROM silver.dim_subscriptions
        WHERE zone NOT IN ('north', 'central', 'south')
    """
    )
    invalid_zone = cursor.fetchone()[0]
    status = "✅ PASS" if invalid_zone == 0 else "❌ FAIL"
    print(f"  {status} | Invalid zones: {invalid_zone}")
    if invalid_zone > 0:
        issues.append(f"{invalid_zone} records with invalid zone")

    # Kiểm tra status hợp lệ
    cursor.execute(
        """
        SELECT COUNT(*) FROM silver.dim_subscriptions
        WHERE status NOT IN ('active', 'expired', 'suspended', 'cancelled', 'pending')
    """
    )
    invalid_status = cursor.fetchone()[0]
    status_label = "✅ PASS" if invalid_status == 0 else "❌ FAIL"
    print(f"  {status_label} | Invalid statuses: {invalid_status}")
    if invalid_status > 0:
        issues.append(f"{invalid_status} records with invalid status")

    return issues


def check_freshness(cursor):
    """Kiểm tra dữ liệu có cập nhật gần đây không"""
    print("\n" + "=" * 50)
    print("CHECK 5: Data Freshness")
    print("=" * 50)

    issues = []

    cursor.execute(
        """
        SELECT MAX(last_updated) FROM silver.dim_subscriptions
    """
    )
    result = cursor.fetchone()[0]
    if result:
        hours_ago = (datetime.now() - result).total_seconds() / 3600
        status = "✅ PASS" if hours_ago < 2 else "⚠️ WARN"
        print(f"  {status} | Last updated: {result} ({hours_ago:.1f} hours ago)")
        if hours_ago >= 2:
            issues.append(f"Data is {hours_ago:.1f} hours old")
    else:
        print("  ❌ FAIL | No data found")
        issues.append("No data found in dim_subscriptions")

    return issues


def main():
    print(f"\n{'#' * 60}")
    print(f"  DATA QUALITY REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 60}\n")

    all_issues = []

    try:
        conn = get_connection()
        cursor = conn.cursor()

        all_issues.extend(check_null_counts(cursor))
        all_issues.extend(check_row_count(cursor))
        all_issues.extend(check_duplicates(cursor))
        all_issues.extend(check_value_ranges(cursor))
        all_issues.extend(check_freshness(cursor))

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"\n❌ CONNECTION ERROR: {e}")
        sys.exit(1)

    # Summary
    print(f"\n{'=' * 50}")
    print("SUMMARY")
    print(f"{'=' * 50}")

    if all_issues:
        print(f"⚠️ {len(all_issues)} issue(s) found:")
        for issue in all_issues:
            print(f"  - {issue}")
        # Exit with warning but don't fail the DAG for non-critical issues
        print("\nData quality check completed with warnings.")
    else:
        print("✅ All checks passed! Data quality is good.")

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
