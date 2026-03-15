FROM apache/airflow:2.6.3-python3.8

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends default-jdk procps wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Download Spark 3.5.8 để đồng bộ version với cluster
ENV SPARK_VERSION=3.5.8
ENV HADOOP_VERSION=3
ENV SPARK_HOME=/opt/spark

RUN wget -q https://dlcdn.apache.org/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz \
    && tar -xzf spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz \
    && mv spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION} ${SPARK_HOME} \
    && rm spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz

# Download PostgreSQL JDBC driver và Hadoop AWS JARs
# - postgresql: để Spark ghi data vào PostgreSQL (jdbc:postgresql://)
# - hadoop-aws + aws-sdk: để Spark đọc data từ MinIO (s3a://)
RUN mkdir -p ${SPARK_HOME}/jars && \
    wget -q -P ${SPARK_HOME}/jars https://jdbc.postgresql.org/download/postgresql-42.7.1.jar && \
    wget -q -P ${SPARK_HOME}/jars https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    wget -q -P ${SPARK_HOME}/jars https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar

ENV PATH="${SPARK_HOME}/bin:${PATH}"
ENV PYTHONPATH="${SPARK_HOME}/python:${SPARK_HOME}/python/lib/py4j-0.10.9.7-src.zip:${PYTHONPATH}"

USER airflow

RUN pip install --no-cache-dir \
    apache-airflow-providers-apache-spark==4.1.0 \
    dbt-postgres==1.6.0
