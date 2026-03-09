# k8s/spark/Dockerfile - Spark image cho Kubernetes deployment
FROM eclipse-temurin:11-jre-focal

# Install Python và các dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Tạo symlink python -> python3
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Download và cài đặt Spark
ENV SPARK_VERSION=3.5.8
ENV HADOOP_VERSION=3

RUN wget -q https://dlcdn.apache.org/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz \
    && tar -xzf spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz \
    && mv spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION} /opt/spark \
    && rm spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz

# Set environment variables
ENV SPARK_HOME=/opt/spark
ENV PATH=$PATH:$SPARK_HOME/bin:$SPARK_HOME/sbin
ENV PYTHONPATH=$SPARK_HOME/python:$SPARK_HOME/python/lib/py4j-0.10.9.7-src.zip:$PYTHONPATH
ENV PYSPARK_PYTHON=python3

# Cài đặt Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Copy Iceberg và các JARs
# (Optional) Iceberg và AWS JARs sẽ được thêm sau nếu cần
# RUN mkdir -p /opt/spark/jars
# COPY jars/iceberg-spark-runtime-3.5_2.12-1.5.0.jar /opt/spark/jars/
# COPY jars/aws-java-sdk-bundle-1.12.262.jar /opt/spark/jars/
# COPY jars/hadoop-aws-3.3.4.jar /opt/spark/jars/

# Tạo thư mục làm việc và copy scripts
WORKDIR /opt/spark/work-dir
COPY scripts/spark_transform.py .

# Tạo user spark không root
RUN groupadd -r spark && useradd -r -g spark spark && \
    chown -R spark:spark /opt/spark

USER spark

CMD ["spark-submit", "--version"]
