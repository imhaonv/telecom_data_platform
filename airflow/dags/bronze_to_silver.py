# airflow/dags/bronze_to_silver.py
import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

default_args = {
    "owner": "data_team",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "bronze_to_silver",
    default_args=default_args,
    description="Transform data from Bronze to Silver layer",
    schedule_interval="*/15 * * * *",  # Mỗi 15 phút
    catchup=False,
)

# Task 1: Trigger Spark job để đọc từ Bronze và viết sang Silver
spark_transform_task = SparkSubmitOperator(
    task_id="spark_bronze_to_silver",
    application="/opt/airflow/scripts/spark_transform.py",
    conn_id="spark_default",
    jars="/opt/bitnami/spark/jars/iceberg-spark-runtime-3.2_2.12-1.3.0.jar,/opt/bitnami/spark/jars/aws-java-sdk-bundle-1.12.262.jar,/opt/bitnami/spark/jars/hadoop-aws-3.3.4.jar",
    conf={
        "spark.sql.extensions": "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        "spark.sql.catalog.spark_catalog": "org.apache.iceberg.spark.SparkSessionCatalog",
        "spark.sql.catalog.spark_catalog.type": "hive",
        "spark.sql.catalog.local": "org.apache.iceberg.spark.SparkCatalog",
        "spark.sql.catalog.local.type": "hadoop",
        "spark.sql.catalog.local.warehouse": "s3a://silver/",
        "spark.hadoop.fs.s3a.endpoint": f"http://{os.environ.get('MINIO_ENDPOINT', 'minio:9000')}",
        "spark.hadoop.fs.s3a.access.key": os.environ.get("MINIO_ACCESS_KEY", "admin"),
        "spark.hadoop.fs.s3a.secret.key": os.environ.get(
            "MINIO_SECRET_KEY", "admin123"
        ),
        "spark.hadoop.fs.s3a.path.style.access": "true",
        "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
    },
    dag=dag,
)

# Task 2: Run DBT models cho Silver layer
dbt_run_task = BashOperator(
    task_id="run_dbt_models",
    bash_command="cd /opt/airflow/dbt && dbt run --models silver --profiles-dir .",
    dag=dag,
)

# Task 3: Kiểm tra chất lượng dữ liệu
data_quality_check = BashOperator(
    task_id="data_quality_check",
    bash_command="python /opt/airflow/scripts/data_quality.py",
    dag=dag,
)

spark_transform_task >> dbt_run_task >> data_quality_check
