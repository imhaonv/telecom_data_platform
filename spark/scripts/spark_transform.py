# spark/scripts/spark_transform.py
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from datetime import datetime
import os
import sys


def create_spark_session():
    """Tạo Spark session với Iceberg configuration"""
    spark_master = os.getenv("SPARK_MASTER", "spark://spark-master:7077")
    return (
        SparkSession.builder.appName("BronzeToSilver")
        .master(spark_master)
        .config("spark.ui.port", "4040")
        .config("spark.driver.memory", "1g")
        .config("spark.executor.memory", "1g")
        .config("spark.executor.cores", "1")
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.iceberg.spark.SparkSessionCatalog",
        )
        .config("spark.sql.catalog.spark_catalog.type", "hive")
        .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.local.type", "hadoop")
        .config("spark.sql.catalog.local.warehouse", "s3a://silver/")
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
        .config("spark.hadoop.fs.s3a.access.key", "admin")
        .config("spark.hadoop.fs.s3a.secret.key", "admin123")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )


def read_bronze_data(spark, date_filter=None):
    """Đọc dữ liệu từ Bronze layer"""
    base_path = "s3a://bronze/raw/"

    if date_filter:
        # Đọc dữ liệu trong khoảng thời gian cụ thể
        df = spark.read.parquet(f"{base_path}{date_filter}")
    else:
        # Đọc tất cả dữ liệu mới nhất
        df = spark.read.parquet(base_path)

    return df


def transform_to_silver(df):
    """Transform dữ liệu từ Bronze sang Silver"""

    # 1. Clean và validate dữ liệu
    silver_df = df.filter(
        col("subscription_id").isNotNull()
        & col("customer_id").isNotNull()
        & col("package_name").isNotNull()
    )

    # 2. Chuẩn hóa các trường
    silver_df = (
        silver_df.withColumn("activation_date", to_date(col("activation_date")))
        .withColumn("expiry_date", to_date(col("expiry_date")))
        .withColumn("created_at", to_timestamp(col("created_at")))
        .withColumn("last_updated", current_timestamp())
    )

    # 3. Tính toán các metrics
    silver_df = (
        silver_df.withColumn(
            "subscription_duration_days",
            datediff(col("expiry_date"), col("activation_date")),
        )
        .withColumn("days_until_expiry", datediff(col("expiry_date"), current_date()))
        .withColumn(
            "usage_percentage",
            when(
                col("data_limit_gb").isNull() | (col("data_limit_gb") == 0), 0
            ).otherwise((col("total_used_gb") / col("data_limit_gb")) * 100),
        )
    )

    # 4. Xác định customer segments
    silver_df = silver_df.withColumn(
        "customer_segment",
        when(col("price_monthly_vnd") >= 500000, "premium")
        .when(col("price_monthly_vnd") >= 200000, "standard")
        .otherwise("basic"),
    )

    # 5. Phát hiện anomalies
    window_spec = Window.partitionBy("package_name", "zone").orderBy("created_at")

    silver_df = silver_df.withColumn(
        "registration_count",
        count("*").over(
            Window.partitionBy("package_name", "zone")
            .orderBy("created_at")
            .rangeBetween(-3600, 0)
        ),
    ).withColumn(
        "is_suspicious",
        when(col("registration_count") > 100, True)
        .when(col("is_anomaly") == True, True)
        .otherwise(False),
    )

    # 6. Chọn và sắp xếp columns
    final_columns = [
        "subscription_id",
        "customer_id",
        "package_name",
        "package_type",
        "data_limit_gb",
        "daily_limit_mb",
        "speed_mbps",
        "price_monthly_vnd",
        "activation_date",
        "expiry_date",
        "auto_renewal",
        "status",
        "device_type",
        "payment_method",
        "zone",
        "customer_segment",
        "subscription_duration_days",
        "days_until_expiry",
        "total_used_gb",
        "remaining_gb",
        "usage_percentage",
        "is_suspicious",
        "anomaly_reason",
        "created_at",
        "last_updated",
    ]

    return silver_df.select(*final_columns)


def write_to_silver(spark, df):
    """Ghi dữ liệu vào Silver layer (Iceberg table)"""
    # Tạo hoặc replace table
    df.writeTo("local.silver.telecom_subscriptions").partitionedBy(
        "package_type", "zone", "year(activation_date)"
    ).createOrReplace()

    # Hoặc append nếu table đã tồn tại
    # df.writeTo("local.silver.telecom_subscriptions").append()


def write_to_postgres(df):
    """Ghi dữ liệu vào PostgreSQL để dbt có thể đọc được"""
    pg_url = "jdbc:postgresql://postgres:5432/telecom_data"
    pg_properties = {
        "user": "admin",
        "password": "admin123",
        "driver": "org.postgresql.Driver",
    }

    # Ghi vào table public.telecom_subscriptions (source cho dbt)
    df.write.jdbc(
        url=pg_url,
        table="public.telecom_subscriptions",
        mode="overwrite",
        properties=pg_properties,
    )

    print("Data synced to PostgreSQL successfully!")


def main():
    spark = create_spark_session()

    # Đọc dữ liệu từ Bronze
    print("Reading data from Bronze layer...")
    bronze_df = read_bronze_data(spark)
    print(f"Total records in Bronze: {bronze_df.count()}")

    # Transform dữ liệu
    print("Transforming data to Silver layer...")
    silver_df = transform_to_silver(bronze_df)
    print(f"Total records after transformation: {silver_df.count()}")

    # Ghi dữ liệu vào Silver (Iceberg trên MinIO)
    print("Writing to Silver layer (Iceberg)...")
    write_to_silver(spark, silver_df)

    # Sync dữ liệu sang PostgreSQL cho dbt
    print("Syncing to PostgreSQL for dbt...")
    write_to_postgres(silver_df)

    print("Transformation completed successfully!")
    spark.stop()


if __name__ == "__main__":
    main()
