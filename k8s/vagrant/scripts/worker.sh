#!/bin/bash
# k8s/vagrant/scripts/worker.sh
# Script chỉ chạy trên Worker nodes
# Đọc join command từ master và join cluster

set -e

MASTER_IP=$1

echo "========================================="
echo "  Joining Kubernetes Cluster"
echo "  Master IP: ${MASTER_IP}"
echo "========================================="

# Chờ join command file từ master node
echo "Chờ join command từ master..."
while [ ! -f /vagrant/k8s/vagrant/join-command.sh ]; do
  sleep 5
done

# Join cluster
bash /vagrant/k8s/vagrant/join-command.sh

echo ""
echo "✅ Worker node đã join cluster thành công!"
