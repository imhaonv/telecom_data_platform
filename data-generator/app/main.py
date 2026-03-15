# data-generator/app/main.py
import time
import random
from datetime import datetime, timedelta
import boto3
from botocore.client import Config
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO
import os


class TelecomDataGenerator:
    def __init__(self):
        self.minio_client = boto3.client(
            "s3",
            endpoint_url=f"http://{os.getenv('MINIO_ENDPOINT', 'localhost:9000')}",
            aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "admin"),
            aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "admin123"),
            config=Config(signature_version="s3v4"),
        )

        # Tạo buckets nếu chưa tồn tại
        self.buckets = ["bronze", "silver", "gold"]
        for bucket in self.buckets:
            try:
                self.minio_client.create_bucket(Bucket=bucket)
            except:
                pass

        # Danh sách các gói data Telecom
        self.packages = [
            {"name": "Data Tốc Cao", "type": "data_only", "price": 199000, "data_limit": 50},
            {"name": "Mimax", "type": "combo", "price": 350000, "data_limit": 120},
            {"name": "ST Super", "type": "data_only", "price": 149000, "data_limit": 30},
            {"name": "Data Pro", "type": "data_only", "price": 299000, "data_limit": 100},
            {"name": "Cước Thả Ga", "type": "unlimited", "price": 499000, "data_limit": 0},
            {"name": "Gói Ngày", "type": "daily", "price": 10000, "data_limit": 2},
            {"name": "Data Student", "type": "data_only", "price": 179000, "data_limit": 70},
            {"name": "Business Pro", "type": "combo", "price": 599000, "data_limit": 200},
            {"name": "Gói Tuần", "type": "weekly", "price": 70000, "data_limit": 10},
            {"name": "Data Cơ Bản", "type": "data_only", "price": 99000, "data_limit": 20},
        ]

        self.pkg_names = [p["name"] for p in self.packages]
        self.pkg_types = [p["type"] for p in self.packages]
        self.pkg_prices = [p["price"] for p in self.packages]
        self.pkg_limits = [p["data_limit"] for p in self.packages]

        self.customer_ids = [f"KH{10000 + i}" for i in range(10000)]
        self.devices = ["smartphone", "tablet", "modem", "router"]
        self.payment_methods = ["credit_card", "bank_transfer", "momo", "cash", "scratch_card"]
        self.zones = ["north", "central", "south"]
        self.speed_choices = [30, 50, 70, 100, 120, 150, 200]
        self.daily_limit_choices = [512, 1024, 2048, 3072, 4096, 5120]
        self.duration_choices = [30, 60, 90, 180, 365]
        self.anomaly_reasons = ["high_frequency", "unusual_package", "suspicious_device"]

    def generate_batch(self, batch_size=10000):
        """Tạo một batch dữ liệu sử dụng numpy vectorized operations"""
        now = datetime.now()
        rng = np.random.default_rng()

        # Vectorized random indices
        pkg_idx = rng.integers(0, len(self.packages), size=batch_size)
        cust_idx = rng.integers(0, len(self.customer_ids), size=batch_size)

        # Package fields via index
        pkg_names = np.array(self.pkg_names)[pkg_idx]
        pkg_types = np.array(self.pkg_types)[pkg_idx]
        pkg_prices = np.array(self.pkg_prices)[pkg_idx]
        pkg_limits = np.array(self.pkg_limits, dtype=float)[pkg_idx]

        # Customer IDs
        customer_ids = np.array(self.customer_ids)[cust_idx]

        # Dates
        days_ago = rng.integers(0, 91, size=batch_size)
        durations = np.array(self.duration_choices)[rng.integers(0, len(self.duration_choices), size=batch_size)]
        activation_dates = [now - timedelta(days=int(d)) for d in days_ago]
        expiry_dates = [activation_dates[i] + timedelta(days=int(durations[i])) for i in range(batch_size)]

        # Anomaly / Cancellation flags
        is_anomaly = rng.random(batch_size) < 0.001
        is_cancelled = rng.random(batch_size) < 0.05

        # Status
        status_choices = ["active", "expired", "suspended"]
        statuses = np.where(
            is_cancelled,
            "cancelled",
            np.array(status_choices)[rng.integers(0, 3, size=batch_size)],
        )

        # Other vectorized fields
        subscription_ids = [f"VT{x}" for x in rng.integers(100000, 999999, size=batch_size)]
        device_types = np.array(self.devices)[rng.integers(0, len(self.devices), size=batch_size)]
        payment_methods = np.array(self.payment_methods)[rng.integers(0, len(self.payment_methods), size=batch_size)]
        zones_arr = np.array(self.zones)[rng.integers(0, len(self.zones), size=batch_size)]
        speeds = np.array(self.speed_choices)[rng.integers(0, len(self.speed_choices), size=batch_size)]
        daily_limits = np.array(self.daily_limit_choices)[rng.integers(0, len(self.daily_limit_choices), size=batch_size)]
        auto_renewal = rng.choice([True, False], size=batch_size)

        # Data usage (vectorized)
        max_data = np.where(pkg_limits > 0, pkg_limits, 500.0)
        total_used = np.round(rng.random(batch_size) * max_data, 2)
        remaining = np.where(pkg_limits > 0, np.round(max_data - rng.random(batch_size) * max_data, 2), None)

        # Daily limits: None for unlimited packages
        daily_limits_final = np.where(pkg_limits > 0, daily_limits, None)

        # Anomaly overrides
        anomaly_reasons = np.where(
            is_anomaly,
            np.array(self.anomaly_reasons)[rng.integers(0, len(self.anomaly_reasons), size=batch_size)],
            None,
        )
        pkg_names = np.where(is_anomaly, rng.choice(["Data Tốc Cao", "Mimax"], size=batch_size), pkg_names)
        statuses = np.where(is_anomaly, "active", statuses)
        zones_arr = np.where(is_anomaly, "north", zones_arr)

        now_iso = now.isoformat()

        df = pd.DataFrame({
            "subscription_id": subscription_ids,
            "customer_id": customer_ids,
            "package_name": pkg_names,
            "package_type": pkg_types,
            "data_limit_gb": pkg_limits,
            "daily_limit_mb": daily_limits_final,
            "speed_mbps": speeds,
            "price_monthly_vnd": pkg_prices,
            "activation_date": [d.isoformat() for d in activation_dates],
            "expiry_date": [d.isoformat() for d in expiry_dates],
            "auto_renewal": auto_renewal,
            "status": statuses,
            "device_type": device_types,
            "payment_method": payment_methods,
            "created_at": now_iso,
            "last_updated": now_iso,
            "zone": zones_arr,
            "is_anomaly": is_anomaly,
            "anomaly_reason": anomaly_reasons,
            "total_used_gb": total_used,
            "remaining_gb": remaining,
        })

        # Partition columns
        df["year"] = now.year
        df["month"] = now.month
        df["day"] = now.day
        df["hour"] = now.hour
        df["minute"] = now.minute

        return df

    def save_to_minio(self, df):
        """Lưu dữ liệu vào Minio dưới dạng Parquet"""
        current_time = datetime.now()
        partition_path = f"year={current_time.year}/month={current_time.month:02d}/day={current_time.day:02d}/hour={current_time.hour:02d}/"

        table = pa.Table.from_pandas(df)
        buffer = BytesIO()
        pq.write_table(table, buffer)
        buffer.seek(0)

        filename = f"telecom_subscriptions_{current_time.strftime('%Y%m%d_%H%M%S')}.parquet"
        s3_key = f"raw/{partition_path}{filename}"

        self.minio_client.put_object(
            Bucket="bronze", Key=s3_key, Body=buffer, ContentType="application/parquet"
        )

        print(f"Saved {len(df)} records to bronze/{s3_key}")
        return s3_key

    def run(self):
        """Chạy generator liên tục"""
        interval = int(os.getenv("GENERATION_INTERVAL", "120"))
        batch_size = int(os.getenv("RECORDS_PER_BATCH", "10000"))

        print(f"Starting data generator: {batch_size} records every {interval} seconds")

        while True:
            try:
                print(f"Generating batch at {datetime.now()}")
                df = self.generate_batch(batch_size)
                s3_key = self.save_to_minio(df)

                print(f"Package distribution:")
                print(df["package_name"].value_counts().head())

                print(f"Anomalies detected: {df['is_anomaly'].sum()}")
                print(f"Cancelled subscriptions: {(df['status'] == 'cancelled').sum()}")
                print("-" * 50)

            except Exception as e:
                print(f"Error: {e}")

            time.sleep(interval)


if __name__ == "__main__":
    generator = TelecomDataGenerator()
    generator.run()
