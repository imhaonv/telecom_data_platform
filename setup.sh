#!/bin/bash
# setup.sh - Telecom Data Platform initialization script

set -e

echo "🚀 Khởi tạo Telecom Data Platform..."

# Tạo các thư mục cần thiết
mkdir -p {minio,postgres,spark/{jars,scripts},airflow/{dags,logs,plugins,scripts},dbt/{models/{silver,gold},tests},superset,trino/etc/catalog,init-scripts}

# Download Iceberg Spark runtime jar (sử dụng -nc để tránh tải trùng)
echo "📦 Downloading required JARs..."
wget -nc -P spark/jars/ https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-3.2_2.12/1.3.0/iceberg-spark-runtime-3.2_2.12-1.3.0.jar || true

# Download AWS SDK
wget -nc -P spark/jars/ https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar || true

# Download Hadoop AWS
wget -nc -P spark/jars/ https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar || true

# Khởi tạo PostgreSQL trước
echo "🐘 Khởi tạo PostgreSQL..."
docker-compose up -d postgres
sleep 10

# Tạo Airflow database và user
echo "🔧 Tạo Airflow database..."
docker-compose exec -T postgres psql -U admin -d postgres -c "CREATE DATABASE airflow;" 2>/dev/null || echo "Database airflow đã tồn tại"
docker-compose exec -T postgres psql -U admin -d airflow -c "CREATE USER airflow WITH PASSWORD 'airflow';" 2>/dev/null || echo "User airflow đã tồn tại"
docker-compose exec -T postgres psql -U admin -d airflow -c "GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;" 2>/dev/null || true

# Chạy tất cả services
echo "🐳 Khởi chạy tất cả services..."
docker-compose up -d

# Chờ Airflow webserver khởi động
echo "⏳ Chờ Airflow webserver khởi động..."
sleep 20

# Khởi tạo Airflow database schema
echo "✈️ Khởi tạo Airflow..."
docker-compose exec -T airflow-webserver airflow db init 2>/dev/null || true

# Tạo Airflow admin user
docker-compose exec -T airflow-webserver airflow users create \
    --username airflow \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@telecom.com \
    --password airflow 2>/dev/null || echo "User airflow đã tồn tại"

echo ""
echo "✅ Data Platform đã được khởi tạo thành công!"
echo ""
echo "📌 Access các services:"
echo "   Minio Console: http://localhost:9001 (admin/admin123)"
echo "   Spark Master:  http://localhost:8080"
echo "   Airflow:       http://localhost:8081 (airflow/airflow)"
echo "   Superset:      http://localhost:8082 (admin/admin)"
echo "   Trino:         http://localhost:8083"