#!/bin/bash
# k8s/vagrant/scripts/master.sh
# Script chỉ chạy trên Master node
# kubeadm init + cài Flannel CNI + tạo join command

set -e

MASTER_IP=$1
POD_CIDR=$2

echo "========================================="
echo "  Khởi tạo Kubernetes Master"
echo "  IP: ${MASTER_IP}"
echo "========================================="

# 1. Khởi tạo cluster
kubeadm init \
  --apiserver-advertise-address="${MASTER_IP}" \
  --pod-network-cidr="${POD_CIDR}" \
  --node-name="k8s-master"

# 2. Cấu hình kubectl cho root user
mkdir -p /root/.kube
cp -i /etc/kubernetes/admin.conf /root/.kube/config
chown root:root /root/.kube/config

# 3. Cấu hình kubectl cho vagrant user
mkdir -p /home/vagrant/.kube
cp -i /etc/kubernetes/admin.conf /home/vagrant/.kube/config
chown vagrant:vagrant /home/vagrant/.kube/config

# 4. Cài đặt Flannel CNI (pod networking)
kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml

# 5. Tạo join command cho worker nodes
echo "========================================="
echo "  Tạo join command cho workers"
echo "========================================="
kubeadm token create --print-join-command > /vagrant/k8s/vagrant/join-command.sh
chmod +x /vagrant/k8s/vagrant/join-command.sh

# 6. Copy kubeconfig ra thư mục shared
cp /etc/kubernetes/admin.conf /vagrant/k8s/vagrant/kubeconfig

echo ""
echo "✅ Master node đã sẵn sàng!"
echo "📋 Join command đã được lưu vào k8s/vagrant/join-command.sh"
echo "📋 Kubeconfig đã được lưu vào k8s/vagrant/kubeconfig"
