# airflow/scripts/spark_transform.py
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, to_date, to_timestamp, current_timestamp, current_date,
    datediff, when, lit
)
import os


def create_spark_session():
    """Tạo Spark session với S3A (MinIO) + PostgreSQL JDBC config"""
    spark_master = os.getenv("SPARK_MASTER", "spark://spark-master:7077")

    print(f"Connecting to Spark cluster: {spark_master}")
    return (
        SparkSession.builder.appName("BronzeToSilver_ETL")
        .master(spark_master)
        .config("spark.ui.port", "4040")
        .config("spark.driver.host", "airflow-scheduler")
        .config("spark.driver.bindAddress", "0.0.0.0")
        .config("spark.driver.memory", "512m")
        .config("spark.executor.memory", "512m")
        .config("spark.executor.cores", "1")
        # S3A config — để Spark hiểu s3a:// protocol (đọc MinIO)
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
        .config("spark.hadoop.fs.s3a.access.key", os.getenv("MINIO_ACCESS_KEY", "admin"))
        .config("spark.hadoop.fs.s3a.secret.key", os.getenv("MINIO_SECRET_KEY", "admin123"))
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        # JDBC driver — để Spark hiểu jdbc:postgresql:// protocol (ghi PostgreSQL)
        .config("spark.jars", "/opt/spark/jars/postgresql-42.7.1.jar")
        .getOrCreate()
    )


def read_bronze_data(spark):
    """Đọc dữ liệu parquet từ Bronze layer (MinIO s3a://bronze/raw/)"""
    base_path = "s3a://bronze/raw/"
    print(f"Reading parquet from: {base_path}")
    return spark.read.option("mergeSchema", "true").parquet(base_path)


def transform_to_silver(df):
    """Transform dữ liệu: clean, tính metrics, phân loại khách hàng"""

    # 1. Lọc records hợp lệ
    silver_df = df.filter(
        col("subscription_id").isNotNull()
        & col("customer_id").isNotNull()
        & col("package_name").isNotNull()
    )

    # 2. Chuẩn hóa date/time
    silver_df = (
        silver_df
        .withColumn("activation_date", to_date(col("activation_date")))
        .withColumn("expiry_date", to_date(col("expiry_date")))
        .withColumn("created_at", to_timestamp(col("created_at")))
        .withColumn("last_updated", current_timestamp())
    )

    # 3. Tính toán metrics
    silver_df = (
        silver_df
        .withColumn("subscription_duration_days",
                     datediff(col("expiry_date"), col("activation_date")))
        .withColumn("days_until_expiry",
                     datediff(col("expiry_date"), current_date()))
        .withColumn("usage_percentage",
                     when(col("data_limit_gb").isNull() | (col("data_limit_gb") == 0), lit(0))
                     .otherwise((col("total_used_gb") / col("data_limit_gb")) * 100))
    )

    # 4. Phân loại khách hàng theo giá gói cước
    silver_df = silver_df.withColumn(
        "customer_segment",
        when(col("price_monthly_vnd") >= 500000, "premium")
        .when(col("price_monthly_vnd") >= 200000, "standard")
        .otherwise("basic"),
    )

    # 5. Đánh dấu anomaly
    silver_df = silver_df.withColumn(
        "is_suspicious",
        when(col("is_anomaly") == True, True).otherwise(False),
    )

    # 6. Chọn columns
    return silver_df.select(
        "subscription_id", "customer_id", "package_name", "package_type",
        "data_limit_gb", "daily_limit_mb", "speed_mbps", "price_monthly_vnd",
        "activation_date", "expiry_date", "auto_renewal", "status",
        "device_type", "payment_method", "zone", "customer_segment",
        "subscription_duration_days", "days_until_expiry",
        "total_used_gb", "remaining_gb", "usage_percentage",
        "is_suspicious", "anomaly_reason", "created_at", "last_updated",
    )


def write_to_postgres(df):
    """Ghi data vào PostgreSQL table public.telecom_subscriptions (source cho dbt)"""
    pg_url = "jdbc:postgresql://{}:{}/{}".format(
        os.getenv("POSTGRES_HOST", "postgres"),
        os.getenv("POSTGRES_PORT", "5432"),
        os.getenv("POSTGRES_DB", "telecom_data"),
    )
    pg_properties = {
        "user": os.getenv("POSTGRES_USER", "admin"),
        "password": os.getenv("POSTGRES_PASSWORD", "admin123"),
        "driver": "org.postgresql.Driver",
    }

    print(f"Writing to PostgreSQL: {pg_url}")
    df.write.jdbc(
        url=pg_url,
        table="public.telecom_subscriptions",
        mode="overwrite",
        properties=pg_properties,
    )
    print("Done! Data written to public.telecom_subscriptions")


def main():
    spark = create_spark_session()
    try:
        # Step 1: Đọc từ MinIO
        print("=" * 50)
        print("Step 1: Reading from MinIO Bronze layer...")
        bronze_df = read_bronze_data(spark)
        count = bronze_df.count()
        print(f"Records found: {count}")

        if count == 0:
            print("No data in Bronze layer. Exiting.")
            return

        # Step 2: Transform
        print("=" * 50)
        print("Step 2: Transforming data...")
        silver_df = transform_to_silver(bronze_df)
        print(f"Records after transform: {silver_df.count()}")

        # Step 3: Ghi vào PostgreSQL
        print("=" * 50)
        print("Step 3: Writing to PostgreSQL...")
        write_to_postgres(silver_df)

        print("=" * 50)
        print("ETL completed successfully!")
    except Exception as e:
        print(f"ETL failed: {e}")
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
