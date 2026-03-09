# -*- mode: ruby -*-
# Vagrantfile - Telecom Data Platform K8s Cluster
# 1 Master + 2 Workers trên VirtualBox

# Cấu hình mạng
MASTER_IP = "192.168.56.10"
WORKER_IP_BASE = "192.168.56"  # .11, .12
POD_CIDR = "10.244.0.0/16"

# Cấu hình tài nguyên
MASTER_CPUS = 2
MASTER_MEMORY = 4096
WORKER_CPUS = 2
WORKER_MEMORY = 4096
NUM_WORKERS = 2

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/focal64"
  config.vm.box_check_update = false

  # ============================================
  # Master Node
  # ============================================
  config.vm.define "k8s-master" do |master|
    master.vm.hostname = "k8s-master"
    master.vm.network "private_network", ip: MASTER_IP

    master.vm.provider "virtualbox" do |vb|
      vb.name = "telecom-k8s-master"
      vb.memory = MASTER_MEMORY
      vb.cpus = MASTER_CPUS
    end

    # Provisioning chung (Docker + kubeadm)
    master.vm.provision "shell", path: "k8s/vagrant/scripts/common.sh"

    # Provisioning master (kubeadm init + Flannel)
    master.vm.provision "shell", path: "k8s/vagrant/scripts/master.sh",
      args: [MASTER_IP, POD_CIDR]
  end

  # ============================================
  # Worker Nodes
  # ============================================
  (1..NUM_WORKERS).each do |i|
    config.vm.define "k8s-worker-#{i}" do |worker|
      worker.vm.hostname = "k8s-worker-#{i}"
      worker.vm.network "private_network", ip: "#{WORKER_IP_BASE}.#{10 + i}"

      worker.vm.provider "virtualbox" do |vb|
        vb.name = "telecom-k8s-worker-#{i}"
        vb.memory = WORKER_MEMORY
        vb.cpus = WORKER_CPUS
      end

      # Provisioning chung (Docker + kubeadm)
      worker.vm.provision "shell", path: "k8s/vagrant/scripts/common.sh"

      # Provisioning worker (kubeadm join)
      worker.vm.provision "shell", path: "k8s/vagrant/scripts/worker.sh",
        args: [MASTER_IP]
    end
  end
end
