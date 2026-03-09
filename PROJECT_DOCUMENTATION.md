# Telecom Data Platform - Tài Liệu Dự Án Toàn Diện

> **Mục đích**: File này ghi lại toàn bộ kiến trúc, flow logic, cài đặt, và chi tiết triển khai của dự án Telecom Data Platform. Dùng làm input cho history prompt trong các conversation sau.

---

## 1. Tổng Quan Dự Án

### 1.1. Mô tả
Dự án xây dựng một **Data Platform** cho Telecom, xử lý dữ liệu đăng ký gói data di động theo kiến trúc **Medallion Architecture** (Bronze → Silver → Gold). Toàn bộ hệ thống chạy trên Docker containers, sử dụng các công nghệ open-source.

### 1.2. Kiến trúc Tổng Quan

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Data Generator  │───▶│   Bronze Layer   │───▶│   Silver Layer   │───▶│    Gold Layer    │
│   (Python App)   │    │   (MinIO/S3)     │    │  (Iceberg/PG)   │    │  (PostgreSQL)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │                       │
                              ┌─────────────────┐      │                       │
                              │  Apache Airflow  │──────┘                       │
                              │  (Orchestrator)  │                              │
                              └─────────────────┘                              │
                                                                    ┌──────────┴──────────┐
                                                                    │   Apache Superset    │
                                                                    │   (Visualization)   │
                                                                    └─────────────────────┘
                              ┌─────────────────┐
                              │     Trino        │───── Query Engine cho Iceberg tables
                              └─────────────────┘
```

### 1.3. Data Domain
Dữ liệu **đăng ký gói data Telecom** bao gồm:
- Thông tin gói cước (tên, loại, giá, dung lượng, tốc độ)
- Thông tin khách hàng (ID, thiết bị, phương thức thanh toán, vùng miền)
- Thông tin đăng ký (ngày kích hoạt, ngày hết hạn, trạng thái, auto-renewal)
- Dữ liệu sử dụng (dung lượng đã dùng, còn lại)
- Phát hiện bất thường (anomaly detection)

---

## 2. Cấu Trúc Thư Mục

```
telecom_data_platform/
├── .env                          # Biến môi trường toàn cục
├── docker-compose.yml            # Định nghĩa tất cả services
├── setup.sh                      # Script khởi tạo ban đầu
├── PROJECT_DOCUMENTATION.md      # Tài liệu dự án (file này)
│
├── data-generator/               # Service sinh dữ liệu mô phỏng
│   ├── Dockerfile                # Image Python 3.9-slim (build context root)
│   ├── requirements.txt          # boto3, pandas, pyarrow
│   └── app/
│       ├── Dockerfile            # (legacy - không sử dụng)
│       └── main.py               # Logic sinh dữ liệu Telecom
│
├── spark/                        # Apache Spark + Iceberg
│   ├── Dockerfile                # Image OpenJDK 11 + Spark 3.5.1
│   ├── requirements.txt          # pyspark==3.5.1
│   ├── jars/                     # 3 JAR files
│   │   ├── iceberg-spark-runtime-3.2_2.12-1.3.0.jar
│   │   ├── aws-java-sdk-bundle-1.12.262.jar
│   │   └── hadoop-aws-3.3.4.jar
│   └── scripts/
│       └── spark_transform.py    # Job Bronze → Silver + sync PostgreSQL
│
├── airflow/                      # Apache Airflow (Orchestration)
│   ├── dags/
│   │   └── bronze_to_silver.py   # DAG chính: Spark → dbt → Data Quality
│   ├── scripts/
│   │   └── data_quality.py       # Data quality checks (5 checks)
│   ├── logs/                     # Log files
│   └── plugins/                  # Custom plugins
│
├── dbt/                          # dbt (Data Build Tool)
│   ├── dbt_project.yml           # Config dự án dbt
│   ├── profiles.yml              # Connection PostgreSQL
│   ├── models/
│   │   ├── silver/               # Silver layer models
│   │   │   ├── sources.yml                   # Khai báo source bronze.telecom_subscriptions
│   │   │   ├── dim_subscriptions.sql          # Dimension: enriched subscriptions
│   │   │   └── fact_daily_registrations.sql   # Fact: daily registration aggregates
│   │   └── gold/                 # Gold layer models
│   │       ├── customer_behavior.sql          # Customer segmentation
│   │       └── daily_summary.sql              # Daily KPI + anomaly detection
│   └── tests/                    # dbt tests
│
├── superset/                     # Apache Superset (BI/Visualization)
│   └── init_superset.py          # Script khởi tạo database + dashboard
│
├── trino/                        # Trino Query Engine
│   └── etc/
│       ├── config.properties     # Server config (coordinator mode)
│       ├── node.properties       # Node environment
│       ├── jvm.config            # JVM settings (1G heap)
│       └── catalog/
│           └── iceberg.properties # Iceberg connector → MinIO
│
├── init-scripts/                 # PostgreSQL init scripts
├── minio/                        # MinIO config
└── postgres/                     # PostgreSQL config
```

---

## 3. Chi Tiết Từng Service

### 3.1. Data Generator (`data-generator/app/main.py`)

**Mục đích**: Sinh dữ liệu mô phỏng đăng ký gói data Telecom liên tục.

**Class**: `TelecomDataGenerator`

**Cấu hình chạy**:
- `GENERATION_INTERVAL`: 30 giây (mặc định) — khoảng thời gian giữa các batch
- `RECORDS_PER_BATCH`: 100,000 bản ghi mỗi batch
- `ANOMALY_RATE`: 0.1% bản ghi bất thường
- `CANCELLATION_RATE`: 5% bản ghi bị hủy

**10 gói cước được mô phỏng**:

| Tên gói | Loại | Giá (VNĐ) | Dung lượng (GB) |
|---------|------|-----------|----------------|
| Data Tốc Cao | data_only | 199,000 | 50 |
| Mimax | combo | 350,000 | 120 |
| ST Super | data_only | 149,000 | 30 |
| Data Pro | data_only | 299,000 | 100 |
| Cước Thả Ga | unlimited | 499,000 | Unlimited |
| Gói Ngày | daily | 10,000 | 2 |
| Data Student | data_only | 179,000 | 70 |
| Business Pro | combo | 599,000 | 200 |
| Gói Tuần | weekly | 70,000 | 10 |
| Data Cơ Bản | data_only | 99,000 | 20 |

**Các trường dữ liệu sinh ra** (21 trường):
```
subscription_id, customer_id, package_name, package_type, data_limit_gb,
daily_limit_mb, speed_mbps, price_monthly_vnd, activation_date, expiry_date,
auto_renewal, status, device_type, payment_method, created_at, last_updated,
zone, is_anomaly, anomaly_reason, total_used_gb, remaining_gb
```

**Partition columns tự động thêm**: `year`, `month`, `day`, `hour`, `minute`

**Anomaly logic**:
- 0.1% bản ghi được đánh dấu `is_anomaly = True`
- Lý do bất thường: `high_frequency`, `unusual_package`, `suspicious_device`
- Bản ghi bất thường luôn có: package = "Data Tốc Cao" hoặc "Mimax", status = "active", zone = "north"

**Output**: File Parquet lưu vào MinIO bucket `bronze` tại path:
```
bronze/raw/year=YYYY/month=MM/day=DD/hour=HH/telecom_subscriptions_YYYYMMDD_HHMMSS.parquet
```

**Master data**:
- 10,000 customer IDs: `KH10000` → `KH19999`
- Devices: `smartphone`, `tablet`, `modem`, `router`
- Payment methods: `credit_card`, `bank_transfer`, `momo`, `cash`, `scratch_card`
- Zones: `north`, `central`, `south`
- Statuses: `active`, `expired`, `suspended`, `cancelled`, `pending`

---

### 3.2. MinIO (S3 Compatible Storage)

**Mục đích**: Object storage thay thế AWS S3, lưu trữ dữ liệu Bronze layer (raw Parquet files).

**Cấu hình**:
- Image: `minio/minio:latest`
- Ports: `9000` (API), `9001` (Console)
- Credentials: `admin` / `admin123`
- Volume: `minio_data` (persistent)
- Health check: HTTP GET `/minio/health/live`

**3 Buckets** được tạo tự động bởi data-generator: `bronze`, `silver`, `gold`

---

### 3.3. PostgreSQL

**Mục đích**: Database cho Silver/Gold layers (dbt models) và Airflow metadata.

**Cấu hình**:
- Image: `postgres:14`
- Port: `5432`
- Database chính: `telecom_data` (cho dbt models + Spark sync)
- Database phụ: `airflow` (cho Airflow metadata — tạo bởi `setup.sh`)
- Credentials: `admin` / `admin123`
- Volume: `postgres_data` (persistent)
- Init scripts mount: `./init-scripts` → `/docker-entrypoint-initdb.d`

**Schemas trong `telecom_data`** (tạo bởi dbt):
- `analytics` — default schema (profile)
- `silver` — Silver layer models (`dim_subscriptions`, `fact_daily_registrations`)
- `gold` — Gold layer models (`customer_behavior`, `daily_summary`)

**Tables**:
- `public.telecom_subscriptions` — Spark sync từ Iceberg (source cho dbt)

---

### 3.4. Apache Spark + Iceberg

**Mục đích**: Xử lý dữ liệu lớn, transform Bronze → Silver với Apache Iceberg table format, và sync dữ liệu sang PostgreSQL.

**Dockerfile** (`spark/Dockerfile`):
- Base: `openjdk:11-jre-slim`
- Spark version: **3.5.1** (Hadoop 3)
- Python 3 + pip
- JARs: Iceberg Spark Runtime, AWS SDK Bundle, Hadoop AWS

**JARs** (trong `spark/jars/` — 3 files):
| JAR | Version | Mục đích |
|-----|---------|----------|
| `iceberg-spark-runtime-3.2_2.12` | 1.3.0 | Iceberg table format |
| `aws-java-sdk-bundle` | 1.12.262 | AWS S3 client cho MinIO |
| `hadoop-aws` | 3.3.4 | Hadoop filesystem S3A |

**Spark Cluster**:
- `spark-master`: Master node, ports `8080` (UI), `7077` (cluster)
- `spark-worker`: 1 worker, 2 cores, 2GB RAM

**Spark Transform Job** (`spark/scripts/spark_transform.py`):

Iceberg Catalog config:
```
- Catalog name: local (Hadoop type)
- Warehouse: s3a://silver/
- S3 endpoint: http://minio:9000
- Path style access: true
```

**Transform logic** (6 bước):

1. **Filter/Validate**: Loại bỏ records có `subscription_id`, `customer_id`, hoặc `package_name` NULL
2. **Standardize dates**: Convert `activation_date` và `expiry_date` sang Date type, `created_at` sang Timestamp
3. **Calculate metrics**:
   - `subscription_duration_days` = datediff(expiry_date, activation_date)
   - `days_until_expiry` = datediff(expiry_date, current_date)
   - `usage_percentage` = (total_used_gb / data_limit_gb) * 100
4. **Customer segmentation**:
   - `premium`: price ≥ 500,000 VNĐ
   - `standard`: price ≥ 200,000 VNĐ
   - `basic`: price < 200,000 VNĐ
5. **Anomaly detection**: Window function đếm registrations theo (package_name, zone) trong 1 giờ. `is_suspicious = True` nếu count > 100 hoặc `is_anomaly = True`
6. **Column selection**: 24 columns được chọn cho Silver layer

**Output 1** — Iceberg table `local.silver.telecom_subscriptions`, partitioned by:
- `package_type`
- `zone`
- `year(activation_date)`

**Output 2** — PostgreSQL table `public.telecom_subscriptions` (JDBC write, mode `overwrite`) để dbt có thể đọc được.

---

### 3.5. Apache Airflow (Orchestration)

**Mục đích**: Điều phối (orchestrate) pipeline xử lý dữ liệu.

**Cấu hình**:
- Image: `apache/airflow:2.6.3`
- Executor: `LocalExecutor`
- Database: `postgresql+psycopg2://airflow:airflow@postgres:5432/airflow`
- Port: `8081` (mapped từ container `8080`)
- Load examples: `false`

**Services**:
- `airflow-webserver`: UI quản lý DAGs
- `airflow-scheduler`: Lên lịch và trigger DAGs

**DAG: `bronze_to_silver`** (`airflow/dags/bronze_to_silver.py`):
- Schedule: `*/15 * * * *` (mỗi 15 phút)
- Catchup: `false`
- Owner: `data_team`
- Retries: 1, retry delay: 5 phút

**Pipeline flow** (3 tasks tuần tự):
```
spark_bronze_to_silver  ──▶  run_dbt_models  ──▶  data_quality_check
```

| Task | Operator | Mô tả |
|------|----------|--------|
| `spark_bronze_to_silver` | `SparkSubmitOperator` | Submit Spark job transform Bronze→Silver + sync PG |
| `run_dbt_models` | `BashOperator` | Chạy `dbt run --models silver` |
| `data_quality_check` | `BashOperator` | Chạy `data_quality.py` (5 checks) |

**SparkSubmitOperator config**:
- Application: `/opt/airflow/scripts/spark_transform.py`
- Connection: `spark_default`
- JARs: Iceberg, AWS SDK, Hadoop AWS
- Spark config: Iceberg catalog + S3A filesystem

---

### 3.6. Data Quality (`airflow/scripts/data_quality.py`)

**Mục đích**: Kiểm tra chất lượng dữ liệu sau khi transform.

**5 checks**:

| # | Check | Mô tả |
|---|-------|--------|
| 1 | Null Count | Kiểm tra NULL trong `subscription_id`, `customer_id`, `package_name`, `activation_date` |
| 2 | Row Count | Đảm bảo `dim_subscriptions` và `fact_daily_registrations` có dữ liệu |
| 3 | Duplicates | Kiểm tra trùng `subscription_id` |
| 4 | Value Ranges | Validate `price_monthly_vnd`, `usage_percentage`, `zone`, `status` |
| 5 | Freshness | Kiểm tra `last_updated` < 2 giờ |

---

### 3.7. dbt (Data Build Tool)

**Mục đích**: Transform và model data trong PostgreSQL theo layer.

**Cấu hình** (`dbt_project.yml`):
- Project name: `telecom_data_platform`
- Profile: `telecom_data_platform`
- Default materialization: `table`
- Silver models: schema `silver`, materialized `table`
- Gold models: schema `gold`, materialized `table`

**Profile** (`profiles.yml`):
- Target: `dev`
- Type: `postgres`
- Host / User / Password / Port / DB: đọc từ env vars
- Default schema: `analytics`
- Threads: 4

**Source** (`models/silver/sources.yml`):
- Source name: `bronze`
- Schema: `public`
- Table: `telecom_subscriptions` (Spark sync từ Iceberg)
- Column tests: `not_null`, `unique`, `accepted_values`

**Models** (4 models, dependency graph):

```
                         ┌───────────────────────────┐
                         │  source: bronze.           │
                         │  telecom_subscriptions     │
                         │  (public.telecom_subs - PG)│
                         └──────────┬────────────────┘
                                    │
                         ┌──────────▼───────────┐
                         │  dim_subscriptions    │ ◄── Silver Layer
                         │  (schema: silver)     │
                         └──────────┬───────────┘
                            ┌───────┴────────┐
                   ┌────────▼──────┐  ┌──────▼────────────┐
                   │ fact_daily_   │  │ customer_behavior  │ ◄── Gold Layer
                   │ registrations │  │ (schema: gold)     │
                   │ (schema:silver)│  └──────────────────┘
                   └───────┬───────┘
                    ┌──────▼──────┐
                    │daily_summary│ ◄── Gold Layer
                    │(schema: gold)│
                    └─────────────┘
```

#### Model 1: `dim_subscriptions` (Silver)
- Source: `{{ source('bronze', 'telecom_subscriptions') }}`
- Filter: `activation_date IS NOT NULL`
- Enrichments:
  - `expiry_status`: 'expired' (< 0 days), 'expiring_soon' (≤ 7 days), 'active'
  - `price_per_gb`: price / data_limit_gb
  - `customer_subscription_rank`: ROW_NUMBER partitioned by customer_id, ordered by activation_date DESC

#### Model 2: `fact_daily_registrations` (Silver)
- Source: `{{ ref('dim_subscriptions') }}`
- Aggregation: GROUP BY date, package_name, package_type, zone, device_type, payment_method
- Metrics: total_registrations, cancelled_registrations, suspicious_registrations, auto_renewal_registrations, avg_price, unique_customers

#### Model 3: `customer_behavior` (Gold)
- Source: `{{ ref('dim_subscriptions') }}`
- Logic: Customer lifetime analysis + segmentation
- Segments:
  - `loyal`: lifetime > 365 days AND subscriptions > 3
  - `high_value`: avg_spending > 300,000 VNĐ
  - `churn_risk`: has cancellations
  - `new`: lifetime < 30 days
  - `regular`: default

#### Model 4: `daily_summary` (Gold)
- Source: `{{ ref('fact_daily_registrations') }}`
- Logic: Daily KPI aggregation + anomaly detection (2-sigma rule trên 7-day rolling window)
- Anomaly detection trên packages "Data Tốc Cao" và "Mimax"
- Metrics: total_subscriptions, cancellation_rate, estimated_revenue, anomaly_status

---

### 3.8. Apache Superset (Visualization)

**Mục đích**: BI dashboard để trực quan hóa dữ liệu Gold layer.

**Cấu hình**:
- Image: `apache/superset:latest`
- Port: `8082` (mapped từ `8088`)
- Secret key: `mysecretkey123`
- Startup: `superset db upgrade && superset init && superset run`

**Init script** (`superset/init_superset.py`):
- Tạo database connection: `postgresql://admin:admin123@postgres:5432/telecom_data`
- Tạo dashboard mẫu: "Telecom Daily Subscriptions" (slug: `telecom-daily`)
- Auto-refresh: 900 giây (15 phút)
- Color scheme: `supersetColors`

---

### 3.9. Trino (Query Engine)

**Mục đích**: Query engine cho Iceberg tables trên MinIO.

**Cấu hình**:
- Image: `trinodb/trino:latest`
- Port: `8083` (mapped từ `8080`)
- Config mount: `./trino/etc` → `/etc/trino`

**Config files**:
| File | Nội dung |
|------|----------|
| `config.properties` | Coordinator mode, HTTP port 8080 |
| `node.properties` | Environment=docker, data-dir=/data/trino |
| `jvm.config` | 1G heap, G1GC, ExitOnOutOfMemoryError |
| `catalog/iceberg.properties` | Iceberg connector → MinIO Silver bucket |

**Iceberg catalog config**:
```properties
connector.name=iceberg
iceberg.catalog.type=hadoop
iceberg.hadoop.warehouse=s3a://silver/
s3.endpoint=http://minio:9000
s3.aws-access-key=admin
s3.aws-secret-key=admin123
```

---

## 4. Data Flow Chi Tiết

### 4.1. Luồng Dữ Liệu End-to-End

```
Bước 1: DATA GENERATION (Continuous)
─────────────────────────────────────
data-generator container chạy liên tục:
  └── Mỗi 30s → sinh 100,000 records
      └── Lưu Parquet → MinIO bucket "bronze"
          └── Path: bronze/raw/year=.../month=.../day=.../hour=.../file.parquet

Bước 2: BRONZE → SILVER (Spark + Iceberg) — Mỗi 15 phút
───────────────────────────────────────────────────────────
Airflow trigger SparkSubmitOperator:
  └── Đọc Parquet từ MinIO (s3a://bronze/raw/)
      └── Transform 6 bước (validate → standardize → metrics → segment → anomaly → select)
          ├── Ghi Iceberg table: local.silver.telecom_subscriptions (MinIO)
          └── Sync PostgreSQL: public.telecom_subscriptions (JDBC overwrite)

Bước 3: SILVER → GOLD (dbt) — Sau Spark job
─────────────────────────────────────────────
Airflow trigger BashOperator (dbt run):
  └── dim_subscriptions (Silver/PG) ← đọc từ public.telecom_subscriptions
      ├── fact_daily_registrations (Silver/PG)
      │   └── daily_summary (Gold/PG)
      └── customer_behavior (Gold/PG)

Bước 4: DATA QUALITY CHECK — Sau dbt
─────────────────────────────────────
Airflow trigger BashOperator:
  └── data_quality.py (5 checks: nulls, rows, duplicates, ranges, freshness)

Bước 5: VISUALIZATION (Continuous)
───────────────────────────────────
Superset kết nối PostgreSQL → truy vấn Gold tables:
  └── Dashboard "Telecom Daily Subscriptions"
      └── Auto-refresh mỗi 15 phút
```

### 4.2. Schedule Tổng Hợp

| Component | Schedule | Mô tả |
|-----------|----------|--------|
| Data Generator | Mỗi 30 giây | Sinh 100K records → MinIO |
| Airflow DAG | Mỗi 15 phút | Trigger toàn bộ pipeline |
| Spark Job | Triggered by Airflow | Bronze → Silver (Iceberg + PG sync) |
| dbt Run | Triggered by Airflow | Silver → Gold (PostgreSQL) |
| Data Quality | Triggered by Airflow | 5 checks chất lượng dữ liệu |
| Superset | Auto-refresh 15 phút | Dashboard cập nhật |

---

## 5. Cài Đặt & Cấu Hình

### 5.1. Environment Variables (`.env`)

```bash
# Database
POSTGRES_USER=admin
POSTGRES_PASSWORD=admin123
POSTGRES_DB=telecom_data
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Minio
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=admin123
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123

# Airflow
AIRFLOW_UID=1000
AIRFLOW_GID=0
AIRFLOW__CORE__FERNET_KEY=46BKJoQYlPPOexq0OhDZnIlNepKFf87WFwLbfzqDDho=

# Spark
SPARK_MASTER=spark://spark-master:7077
SPARK_WORKER_MEMORY=2G
SPARK_WORKER_CORES=2

# Data Generator
GENERATION_INTERVAL=30
RECORDS_PER_BATCH=100000
ANOMALY_RATE=0.001
CANCELLATION_RATE=0.05

# Superset
SUPERSET_SECRET_KEY=mysecretkey123
SUPERSET_DATABASE_URI=postgresql://admin:admin123@postgres:5432/telecom_data
```

### 5.2. Ports Mapping

| Service | Container Port | Host Port | URL |
|---------|---------------|-----------|-----|
| MinIO API | 9000 | 9000 | http://localhost:9000 |
| MinIO Console | 9001 | 9001 | http://localhost:9001 |
| PostgreSQL | 5432 | 5432 | localhost:5432 |
| Spark Master UI | 8080 | 8080 | http://localhost:8080 |
| Spark Master | 7077 | 7077 | spark://localhost:7077 |
| Airflow Web | 8080 | 8081 | http://localhost:8081 |
| Superset | 8088 | 8082 | http://localhost:8082 |
| Trino | 8080 | 8083 | http://localhost:8083 |

### 5.3. Docker Volumes

| Volume | Mount | Mục đích |
|--------|-------|----------|
| `minio_data` | `/data` | Persistent MinIO storage |
| `postgres_data` | `/var/lib/postgresql/data` | Persistent PostgreSQL data |

### 5.4. Khởi Chạy

```bash
# 1. Chạy setup script (tải JARs, tạo Airflow DB + user, khởi tạo services)
chmod +x setup.sh
./setup.sh

# 2. Hoặc khởi chạy thủ công
docker-compose up -d postgres
sleep 10
docker-compose exec -T postgres psql -U admin -d postgres -c "CREATE DATABASE airflow;"
docker-compose exec -T postgres psql -U admin -d airflow -c "CREATE USER airflow WITH PASSWORD 'airflow';"
docker-compose exec -T postgres psql -U admin -d airflow -c "GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;"
docker-compose up -d
sleep 20
docker-compose exec -T airflow-webserver airflow db init
docker-compose exec -T airflow-webserver airflow users create \
    --username airflow --firstname Admin --lastname User \
    --role Admin --email admin@telecom.com --password airflow
```

---

## 6. Credentials Tổng Hợp

| Service | Username | Password | Ghi chú |
|---------|----------|----------|---------|
| MinIO | admin | admin123 | Console tại :9001 |
| PostgreSQL | admin | admin123 | DB: telecom_data |
| Airflow PG | airflow | airflow | DB: airflow |
| Airflow Web | airflow | airflow | Tạo bởi setup.sh |
| Superset | admin | admin | Tạo bởi superset init |

---

## 7. Technology Stack Summary

| Layer | Technology | Version | Mục đích |
|-------|-----------|---------|----------|
| Storage (Bronze) | MinIO | latest | S3-compatible object storage |
| Processing | Apache Spark | 3.5.1 | Big data processing |
| Table Format | Apache Iceberg | 1.3.0 | ACID transactions, time travel |
| Database (Silver/Gold) | PostgreSQL | 14 | Relational data warehouse |
| Orchestration | Apache Airflow | 2.6.3 | Pipeline scheduling |
| Transformation | dbt | (container) | SQL-based transforms |
| Visualization | Apache Superset | latest | BI Dashboards |
| Query Engine | Trino | latest | Federated queries on Iceberg |
| Language | Python | 3.9 | Data generator, Spark jobs |
| Container | Docker Compose | 3.8 | Infrastructure as Code |

---

> **Last updated**: 2026-03-09
> **Project path**: `/Users/nguyenhao/Documents/Learn_DE/telecom_data_platform/`
