# dbt/Dockerfile
FROM python:3.9-slim

# Install dbt-postgres
RUN pip install --no-cache-dir dbt-postgres==1.6.0

WORKDIR /usr/app

# Copy dbt project files
COPY . /usr/app

# Default command: keep container running for dbt commands
CMD ["tail", "-f", "/dev/null"]
