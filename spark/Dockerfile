# spark/Dockerfile
FROM eclipse-temurin:11-jre-focal

# Install Python và các dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Download và cài đặt Spark
ENV SPARK_VERSION=3.5.8
ENV HADOOP_VERSION=3

RUN wget -q https://dlcdn.apache.org/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz \
    && tar -xzf spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz \
    && mv spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION} /opt/spark \
    && rm spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz

# Cài đặt Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt

# Cài đặt Iceberg và các JARs
# (Optional) Iceberg và AWS JARs sẽ được thêm sau nếu cần
# RUN mkdir -p /opt/spark/jars
# COPY jars/iceberg-spark-runtime-3.5_2.12-1.5.0.jar /opt/spark/jars/
# COPY jars/aws-java-sdk-bundle-1.12.262.jar /opt/spark/jars/
# COPY jars/hadoop-aws-3.3.4.jar /opt/spark/jars/

# Set environment variables
ENV SPARK_HOME=/opt/spark
ENV PATH=$PATH:$SPARK_HOME/bin
ENV PYTHONPATH=$SPARK_HOME/python:$PYTHONPATH

WORKDIR /opt/spark