# Telecom Data Platform

## 📖 Giới thiệu
Dự án **Telecom Data Platform** là một nền tảng dữ liệu toàn diện được cấu trúc theo mô hình kiến trúc dữ liệu hiện đại (Modern Data Stack). Nền tảng này hỗ trợ toàn bộ vòng đời của dữ liệu từ việc giả lập/thu thập dữ liệu, lưu trữ trên Data Lake, xử lý dữ liệu lớn (Big Data), chuyển đổi dữ liệu và cuối cùng là trực quan hóa để phục vụ phân tích kinh doanh (Business Intelligence).

Dự án được triển khai hoàn toàn bằng Docker, giúp việc thiết lập và vận hành trở nên dễ dàng và cô lập trên mọi môi trường.

## 🏗 Kiến trúc hệ thống
Dự án kết hợp các công cụ mạnh mẽ trong giới Data/Data Engineering:

- **Storage / Data Lake (Bronze Layer)**: **Minio** (S3-compatible storage) dùng để lưu trữ dữ liệu thô.
- **Processing (Data Processing Component)**: **Apache Spark** kết hợp với **Apache Iceberg** giúp xử lý và quản lý dữ liệu lớn mở rộng dạng bảng.
- **Relational Database (Silver & Gold Layers)**: **PostgreSQL** được sử dụng làm kho lưu trữ dữ liệu sau xử lý.
- **Orchestration**: **Apache Airflow** điều phối toàn bộ các pipeline (DAGs) từ lấy dữ liệu đến xử lý và chuyển đổi.
- **Transformation (ELT)**: **dbt (Data Build Tool)** quản lý các model biến đổi dữ liệu một cách trực quan và có kiểm soát phiên bản.
- **Data Query Engine**: **Trino** cung cấp khả năng truy vấn SQL phân tán siêu tốc trực tiếp lên Data Lake (Iceberg/Minio).
- **Data Visualization / BI**: **Apache Superset** giúp tạo các dashboard trực quan hóa dữ liệu từ kho dữ liệu hoặc qua Trino.
- **Data Generator**: Dịch vụ giả lập luồng dữ liệu liên tục để phục vụ cho việc phát triển và kiểm thử hệ thống.

## 📁 Cấu trúc thư mục
- `airflow/`: Chứa cấu hình, Dockerfile, scripts và đặc biệt là các DAGs (`airflow/dags/`) dùng để điều phối luồng dữ liệu.
- `spark/`: Môi trường và các job xử lý dữ liệu song song của Apache Spark.
- `dbt/`: Chứa các model, cấu hình dbt phục vụ quá trình data transformation.
- `data-generator/`: Script mô phỏng việc sinh dữ liệu viễn thông (telecom data) đưa vào hệ thống.
- `trino/`: Cấu hình catalog và thuộc tính kết nối cho distributed query engine Trino.
- `superset/`: Cấu hình và kho lưu trữ liên quan đến BI Superset.
- `init-scripts/`: (Tùy chọn) Chứa các script khởi tạo database cho auto-setup PostgreSQL.

## 🚀 Hướng dẫn cài đặt và sử dụng

### Yêu cầu hệ thống (Prerequisites)
- [Docker](https://docs.docker.com/get-docker/) và Docker Compose (version 3.8+).
- Hệ máy tính cấu hình tối thiểu khuyến nghị: RAM 8GB (Khuyến nghị 16GB+) do hệ thống chạy nhiều container song song.

### Cài đặt
1. **Clone repository (nếu có)** hoặc cd vào thư mục dự án:
   ```bash
   cd /path/to/telecom_data_platform
   ```

2. **Cấu hình biến môi trường**:
   Bảo đảm file `.env` đã được cấu hình với các thông số password và port phù hợp dựa trên template mẫu.

3. **Khởi động các dịch vụ**:
   Dùng Docker Compose để build và chạy ngầm toàn bộ các dịch vụ:
   ```bash
   docker-compose up -d --build
   ```

4. **Theo dõi trạng thái hệ thống**:
   Bạn có thể kiểm tra trạng thái khởi chạy bằng lệnh:
   ```bash
   docker-compose ps
   ```

### 🌐 Truy cập các dịch vụ (Cổng mặc định/mẫu)
Dưới đây là một số service nổi bật bạn có thể truy cập qua trình duyệt (Lưu ý: Port có thể bị ảnh hưởng bởi file `.env`):
- **Apache Airflow (Web UI)**: `http://localhost:8080` (Tài khoản được cấu hình trong `AIRFLOW_ADMIN_USER`/`AIRFLOW_ADMIN_PASSWORD` của file `.env`).
- **Minio Console**: `http://localhost:9001`
- **Apache Spark Master UI**: `http://localhost:8081` (Tùy port cấu hình `SPARK_MASTER_WEBUI_PORT`)
- **Apache Superset**: `http://localhost:8088`
- **PostgreSQL**: Truy xuất qua port `5432` hoặc theo biến `POSTGRES_HOST_PORT`.
- **Trino**: Truy xuất thông qua ứng dụng DBeaver/DataGrip ở port cấu hình `TRINO_HOST_PORT` (Mặc định thường là 8080/8443).

## 🛑 Dừng hệ thống
Để dừng hoàn toàn hệ thống và giữ lại dữ liệu:
```bash
docker-compose stop
```
Để dừng và xoá containers (Các volume dữ liệu Minio/Postgres vẫn được giữ lại vì persist ở `docker-compose.yml`):
```bash
docker-compose down
```
Để xoá sạch cả hệ thống bao gồm mọi volume (Mất toàn bộ dữ liệu):
```bash
docker-compose down -v
```

## 📝 Nhật ký cập nhật (Changelog)
- Đã cấu hình và đổi thương hiệu dự án thành **Telecom Data Platform**. Các lỗi liên đới tới thư mục build, cấu hình Airflow và dbt đã được khắc phục để hệ thống có thể chạy toàn diện.
