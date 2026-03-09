# Triển khai Telecom Data Platform lên Kubernetes (Vagrant + kubeadm)

Hướng dẫn triển khai Telecom Data Platform lên **multi-node Kubernetes cluster** sử dụng **Vagrant + VirtualBox + kubeadm**. Mô phỏng môi trường production với 3 VMs (1 Master + 2 Workers) chạy trên cùng 1 máy.

---

## 1. Yêu cầu

- **VirtualBox** ≥ 6.1 — [Tải về](https://www.virtualbox.org/wiki/Downloads)
- **Vagrant** ≥ 2.3 — [Tải về](https://www.vagrantup.com/downloads)
- **RAM máy host** ≥ 16 GB (3 VMs × 4GB = 12GB + host OS)
- **Disk** ≥ 40 GB trống

Kiểm tra cài đặt:

```bash
vagrant --version   # Vagrant 2.3.x
VBoxManage --version  # 6.1.x hoặc 7.x
```

---

## 2. Kiến trúc Multi-Node

```
┌─────────────────── Máy Host (macOS/Linux/Windows) ──────────────────┐
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                     Private Network 192.168.56.0/24           │  │
│  │                                                                │  │
│  │  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐    │  │
│  │  │   k8s-master     │  │ k8s-worker-1 │  │ k8s-worker-2 │    │  │
│  │  │  192.168.56.10   │  │ 192.168.56.11│  │ 192.168.56.12│    │  │
│  │  │                  │  │              │  │              │    │  │
│  │  │ • Control Plane  │  │ • MinIO Pod  │  │ • Spark      │    │  │
│  │  │ • API Server     │  │ • PostgreSQL │  │   Executor   │    │  │
│  │  │ • Scheduler      │  │   Pod        │  │   Pods       │    │  │
│  │  │ • Flannel CNI    │  │ • Data Gen   │  │              │    │  │
│  │  │                  │  │   Pod        │  │              │    │  │
│  │  │ 2 CPU / 4GB RAM  │  │ 2 CPU / 4GB │  │ 2 CPU / 4GB │    │  │
│  │  └──────────────────┘  └──────────────┘  └──────────────┘    │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Shared folder: /vagrant ←→ telecom_data_platform/                  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Cấu trúc files

```
telecom_data_platform/
├── Vagrantfile                       # 1 Master + 2 Workers
├── k8s/
│   ├── vagrant/
│   │   ├── scripts/
│   │   │   ├── common.sh            # Docker + kubeadm (tất cả nodes)
│   │   │   ├── master.sh            # kubeadm init + Flannel
│   │   │   └── worker.sh            # kubeadm join
│   │   ├── join-command.sh          # (auto-generated khi master init)
│   │   └── kubeconfig               # (auto-generated, copy về host)
│   ├── namespace.yaml
│   ├── rbac.yaml
│   ├── minio.yaml
│   ├── postgres.yaml
│   ├── spark-app.yaml
│   ├── data-generator.yaml
│   └── spark/
│       └── Dockerfile               # Spark image cho K8s
└── spark/
    ├── jars/                         # JARs (copy vào K8s image)
    ├── scripts/spark_transform.py
    └── requirements.txt
```

---

## 4. Bước 1 — Tạo Cluster (vagrant up)

```bash
cd /path/to/telecom_data_platform

# Tạo cả 3 VMs cùng lúc (mất ~10-15 phút)
vagrant up
```

Vagrant sẽ tự động:
1. Tạo 3 VMs Ubuntu 20.04 trên VirtualBox
2. Cài Docker + containerd trên mỗi VM
3. Cài kubeadm, kubelet, kubectl v1.28
4. Chạy `kubeadm init` trên master (Flannel CNI)
5. Chạy `kubeadm join` trên 2 workers

### 4.1. Kiểm tra trạng thái VMs

```bash
vagrant status
# k8s-master    running (virtualbox)
# k8s-worker-1  running (virtualbox)
# k8s-worker-2  running (virtualbox)
```

### 4.2. Kiểm tra cluster

```bash
# SSH vào master
vagrant ssh k8s-master

# Kiểm tra nodes
kubectl get nodes
# NAME           STATUS   ROLES           AGE     VERSION
# k8s-master     Ready    control-plane   5m      v1.28.x
# k8s-worker-1   Ready    <none>          3m      v1.28.x
# k8s-worker-2   Ready    <none>          2m      v1.28.x
```

### 4.3. Sử dụng kubectl từ máy host (không cần SSH)

```bash
# Copy kubeconfig về máy host
export KUBECONFIG=$(pwd)/k8s/vagrant/kubeconfig
kubectl get nodes
```

---

## 5. Bước 2 — Build Docker Images trên các Nodes

Vì không dùng registry, cần build image trực tiếp trên mỗi node:

```bash
# Build trên master (nếu cần chạy Spark driver trên master)
vagrant ssh k8s-master -c "cd /vagrant && docker build -f k8s/spark/Dockerfile -t telecom-spark:latest ./spark"

# Build trên worker-1
vagrant ssh k8s-worker-1 -c "cd /vagrant && docker build -f k8s/spark/Dockerfile -t telecom-spark:latest ./spark"

# Build trên worker-2
vagrant ssh k8s-worker-2 -c "cd /vagrant && docker build -f k8s/spark/Dockerfile -t telecom-spark:latest ./spark"

# Build data-generator image trên tất cả nodes
vagrant ssh k8s-master -c "cd /vagrant && docker build -t telecom-data-generator:latest ./data-generator"
vagrant ssh k8s-worker-1 -c "cd /vagrant && docker build -t telecom-data-generator:latest ./data-generator"
vagrant ssh k8s-worker-2 -c "cd /vagrant && docker build -t telecom-data-generator:latest ./data-generator"
```

> **Tip**: Hoặc dùng local Docker registry để chỉ build 1 lần (xem phần Nâng cao).

---

## 6. Bước 3 — Deploy Infrastructure

```bash
vagrant ssh k8s-master
cd /vagrant

# Tạo namespace
kubectl apply -f k8s/namespace.yaml

# RBAC cho Spark
kubectl apply -f k8s/rbac.yaml

# Deploy MinIO + PostgreSQL
kubectl apply -f k8s/minio.yaml
kubectl apply -f k8s/postgres.yaml

# Chờ pods ready
kubectl get pods -n telecom-platform -w
# NAME                     READY   STATUS    AGE
# minio-xxx                1/1     Running   30s
# postgres-xxx             1/1     Running   30s
```

---

## 7. Bước 4 — Deploy Data Generator

```bash
kubectl apply -f k8s/data-generator.yaml

# Kiểm tra logs
kubectl logs -f -n telecom-platform deploy/data-generator
# Generating batch... 100000 records → MinIO
```

---

## 8. Bước 5 — Cài Spark Operator

```bash
# Cài Helm (nếu chưa có trên master)
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Thêm repo và cài đặt
helm repo add spark-operator https://googlecloudplatform.github.io/spark-on-k8s-operator
helm repo update

helm install spark-operator spark-operator/spark-operator \
    --namespace spark-operator \
    --create-namespace \
    --set webhook.enable=false

# Chờ operator ready
kubectl get pods -n spark-operator
```

---

## 9. Bước 6 — Chạy Spark Job

```bash
kubectl apply -f k8s/spark-app.yaml

# Theo dõi pods
kubectl get pods -n telecom-platform -w
# NAME                                    READY   STATUS
# telecom-bronze-to-silver-driver         1/1     Running
# telecom-bronze-to-silver-xxx-exec-1     1/1     Running   (worker-1)
# telecom-bronze-to-silver-xxx-exec-2     1/1     Running   (worker-2)

# Xem Spark job logs
kubectl logs -n telecom-platform telecom-bronze-to-silver-driver
```

### 9.1. Kiểm tra pods phân bổ trên nodes

```bash
kubectl get pods -n telecom-platform -o wide
# NAME                           NODE           IP
# minio-xxx                      k8s-worker-1   10.244.1.x
# postgres-xxx                   k8s-worker-1   10.244.1.x
# telecom-...-driver             k8s-master     10.244.0.x
# telecom-...-exec-1             k8s-worker-1   10.244.1.x
# telecom-...-exec-2             k8s-worker-2   10.244.2.x
```

---

## 10. Truy cập Services từ máy host

### 10.1. MinIO Console

```bash
# Port-forward qua SSH tunnel
vagrant ssh k8s-master -- -L 9001:localhost:9001 \
  kubectl port-forward -n telecom-platform svc/minio 9001:9001
# Mở http://localhost:9001 (admin/admin123)
```

### 10.2. PostgreSQL

```bash
vagrant ssh k8s-master -- -L 5432:localhost:5432 \
  kubectl port-forward -n telecom-platform svc/postgres 5432:5432
# psql -h localhost -U admin -d telecom_data
```

### 10.3. Spark UI (trong lúc job chạy)

```bash
vagrant ssh k8s-master -- -L 4040:localhost:4040 \
  kubectl port-forward -n telecom-platform svc/telecom-bronze-to-silver-driver-svc 4040:4040
# Mở http://localhost:4040
```

---

## 11. Nâng cao: Local Docker Registry

Thay vì build image trên mỗi node, dùng local registry:

```bash
# Trên master, chạy registry
vagrant ssh k8s-master -c "docker run -d -p 5000:5000 --restart=always --name registry registry:2"

# Build và push
vagrant ssh k8s-master -c "
  cd /vagrant
  docker build -f k8s/spark/Dockerfile -t localhost:5000/telecom-spark:latest ./spark
  docker push localhost:5000/telecom-spark:latest
  docker build -t localhost:5000/telecom-data-generator:latest ./data-generator
  docker push localhost:5000/telecom-data-generator:latest
"
```

Sau đó thay `image` trong YAML files:
```yaml
image: "192.168.56.10:5000/telecom-spark:latest"
```

---

## 12. Quản lý Cluster

### SSH vào nodes

```bash
vagrant ssh k8s-master
vagrant ssh k8s-worker-1
vagrant ssh k8s-worker-2
```

### Tạm dừng / Khởi động lại

```bash
vagrant halt          # Tắt tất cả VMs
vagrant up            # Bật lại (giữ nguyên data)
vagrant reload        # Restart VMs
```

### Xóa hoàn toàn

```bash
# Xóa K8s resources trước
vagrant ssh k8s-master -c "kubectl delete namespace telecom-platform"

# Xóa VMs
vagrant destroy -f
```

---

## 13. So sánh Docker Compose vs Vagrant K8s

| Khía cạnh | Docker Compose | Vagrant + kubeadm |
|-----------|---------------|-------------------|
| Môi trường | Single host | Multi-node VMs |
| Isolation | Container-level | VM-level (full OS) |
| Networking | Docker bridge | Flannel CNI + Private network |
| Spark mode | Standalone cluster | Spark Operator (K8s native) |
| Scheduling | Airflow | ScheduledSparkApplication |
| Tài nguyên | ~4GB RAM | ~12GB RAM |
| Production giống | ⭐ | ⭐⭐⭐ |
| Setup time | 2 phút | 15 phút |

---

## 14. Troubleshooting

| Vấn đề | Giải pháp |
|--------|----------|
| `vagrant up` timeout | Kiểm tra VirtualBox + tăng timeout trong Vagrantfile |
| Nodes NotReady | Chờ thêm 1-2 phút cho Flannel, hoặc kiểm tra: `kubectl describe node` |
| Image pull error | Đảm bảo đã build image trên đúng node, hoặc dùng local registry |
| Pod Pending | Kiểm tra resources: `kubectl describe pod <name> -n telecom-platform` |
| Worker không join | SSH vào worker và chạy lại: `bash /vagrant/k8s/vagrant/join-command.sh` |
| Flannel lỗi | Kiểm tra `kube-flannel` pod: `kubectl get pods -n kube-flannel` |

---

> **Tổng tài nguyên cần**: 12 GB RAM + 6 CPU cores + 40 GB disk trên máy host