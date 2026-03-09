# data-generator/app/main.py
import time
import json
import random
from datetime import datetime, timedelta
import boto3
from botocore.client import Config
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
            {
                "name": "Data Tốc Cao",
                "type": "data_only",
                "price": 199000,
                "data_limit": 50,
            },
            {"name": "Mimax", "type": "combo", "price": 350000, "data_limit": 120},
            {
                "name": "ST Super",
                "type": "data_only",
                "price": 149000,
                "data_limit": 30,
            },
            {
                "name": "Data Pro",
                "type": "data_only",
                "price": 299000,
                "data_limit": 100,
            },
            {
                "name": "Cước Thả Ga",
                "type": "unlimited",
                "price": 499000,
                "data_limit": None,
            },
            {"name": "Gói Ngày", "type": "daily", "price": 10000, "data_limit": 2},
            {
                "name": "Data Student",
                "type": "data_only",
                "price": 179000,
                "data_limit": 70,
            },
            {
                "name": "Business Pro",
                "type": "combo",
                "price": 599000,
                "data_limit": 200,
            },
            {"name": "Gói Tuần", "type": "weekly", "price": 70000, "data_limit": 10},
            {
                "name": "Data Cơ Bản",
                "type": "data_only",
                "price": 99000,
                "data_limit": 20,
            },
        ]

        self.customer_ids = [f"KH{10000 + i}" for i in range(10000)]
        self.devices = ["smartphone", "tablet", "modem", "router"]
        self.payment_methods = [
            "credit_card",
            "bank_transfer",
            "momo",
            "cash",
            "scratch_card",
        ]
        self.zones = ["north", "central", "south"]
        self.statuses = ["active", "expired", "suspended", "cancelled", "pending"]

    def generate_record(self):
        """Tạo một bản ghi đăng ký data"""
        package = random.choice(self.packages)
        customer_id = random.choice(self.customer_ids)
        now = datetime.now()

        # Tạo ngẫu nhiên thời gian trong 90 ngày qua
        days_ago = random.randint(0, 90)
        activation_date = now - timedelta(days=days_ago)
        expiry_date = activation_date + timedelta(
            days=random.choice([30, 60, 90, 180, 365])
        )

        # Tỷ lệ hủy/bất thường
        is_anomaly = random.random() < 0.001  # 0.1% là bất thường
        is_cancelled = random.random() < 0.05  # 5% bị hủy

        record = {
            "subscription_id": f"VT{random.randint(100000, 999999)}",
            "customer_id": customer_id,
            "package_name": package["name"],
            "package_type": package["type"],
            "data_limit_gb": package["data_limit"],
            "daily_limit_mb": (
                random.choice([512, 1024, 2048, 3072, 4096, 5120])
                if package["data_limit"]
                else None
            ),
            "speed_mbps": random.choice([30, 50, 70, 100, 120, 150, 200]),
            "price_monthly_vnd": package["price"],
            "activation_date": activation_date.isoformat(),
            "expiry_date": expiry_date.isoformat(),
            "auto_renewal": random.choice([True, False]),
            "status": (
                "cancelled"
                if is_cancelled
                else random.choice(["active", "expired", "suspended"])
            ),
            "device_type": random.choice(self.devices),
            "payment_method": random.choice(self.payment_methods),
            "created_at": now.isoformat(),
            "last_updated": now.isoformat(),
            "zone": random.choice(self.zones),
            "is_anomaly": is_anomaly,
            "anomaly_reason": (
                random.choice(
                    ["high_frequency", "unusual_package", "suspicious_device"]
                )
                if is_anomaly
                else None
            ),
            "total_used_gb": (
                round(random.uniform(0, package["data_limit"] or 500), 2)
                if package["data_limit"]
                else round(random.uniform(0, 500), 2)
            ),
            "remaining_gb": (
                round(
                    (package["data_limit"] or 500)
                    - random.uniform(0, package["data_limit"] or 500),
                    2,
                )
                if package["data_limit"]
                else None
            ),
        }

        # Thêm bất thường
        if is_anomaly:
            record["package_name"] = random.choice(
                ["Data Tốc Cao", "Mimax"]
            )  # Gói phổ biến
            record["status"] = "active"
            record["zone"] = "north"  # Tập trung ở một zone

        return record

    def generate_batch(self, batch_size=100000):
        """Tạo một batch dữ liệu"""
        records = [self.generate_record() for _ in range(batch_size)]
        df = pd.DataFrame(records)

        # Thêm partition columns
        current_time = datetime.now()
        df["year"] = current_time.year
        df["month"] = current_time.month
        df["day"] = current_time.day
        df["hour"] = current_time.hour
        df["minute"] = current_time.minute

        return df

    def save_to_minio(self, df):
        """Lưu dữ liệu vào Minio dưới dạng Parquet"""
        current_time = datetime.now()
        partition_path = f"year={current_time.year}/month={current_time.month:02d}/day={current_time.day:02d}/hour={current_time.hour:02d}/"

        # Chuyển đổi sang Parquet
        table = pa.Table.from_pandas(df)
        buffer = BytesIO()
        pq.write_table(table, buffer)
        buffer.seek(0)

        # Tên file với timestamp
        filename = (
            f"telecom_subscriptions_{current_time.strftime('%Y%m%d_%H%M%S')}.parquet"
        )
        s3_key = f"raw/{partition_path}{filename}"

        # Upload lên Minio
        self.minio_client.put_object(
            Bucket="bronze", Key=s3_key, Body=buffer, ContentType="application/parquet"
        )

        print(f"Saved {len(df)} records to bronze/{s3_key}")
        return s3_key

    def run(self):
        """Chạy generator liên tục"""
        interval = int(os.getenv("GENERATION_INTERVAL", "30"))
        batch_size = int(os.getenv("RECORDS_PER_BATCH", "100000"))

        print(f"Starting data generator: {batch_size} records every {interval} seconds")

        while True:
            try:
                print(f"Generating batch at {datetime.now()}")
                df = self.generate_batch(batch_size)
                s3_key = self.save_to_minio(df)

                # Thống kê
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
