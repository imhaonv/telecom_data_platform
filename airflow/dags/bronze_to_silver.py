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
    schedule_interval="*/55 * * * *",  # Mỗi 15 phút
    catchup=False,
)

# Task 1: Trigger Spark job để chạy một ứng dụng đơn giản (demo)
spark_transform_task = SparkSubmitOperator(
    task_id="spark_bronze_to_silver",
    application="/opt/airflow/scripts/spark_transform.py",
    conn_id="spark_default",
    conf={
        "spark.ui.port": "4040",
        "spark.driver.host": "airflow-scheduler",
        "spark.driver.bindAddress": "0.0.0.0",
        "spark.driver.memory": "512m",
        "spark.executor.memory": "512m",
        "spark.executor.cores": "1",
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
