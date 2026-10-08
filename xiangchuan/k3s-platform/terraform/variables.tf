variable "kubeconfig_path" {
  description = "kubeconfig 路徑（k3s 預設 /etc/rancher/k3s/k3s.yaml，本機遠端請用 ~/.kube/config）"
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "kubeconfig context，留空用當前 context"
  type        = string
  default     = ""
}

variable "namespace" {
  description = "平台 namespace"
  type        = string
  default     = "platform"
}

variable "git_repo_url" {
  description = "GitOps 用的 Git repo URL（Argo CD 依此自動同步 manifests）"
  type        = string
  default     = "https://github.com/lewislunora/lewislunora.git"
}

variable "git_revision" {
  description = "同步的分支或 tag"
  type        = string
  default     = "main"
}

variable "manifests_path" {
  description = "repo 內 k8s manifests 相對路徑"
  type        = string
  default     = "xiangchuan/k3s-platform/k8s-manifests"
}

variable "argocd_namespace" {
  description = "Argo CD 安裝 namespace"
  type        = string
  default     = "argocd"
}

variable "argocd_chart_version" {
  description = "argo-helm chart 版本"
  type        = string
  default     = "7.7.12"
}

variable "app_image" {
  description = "平台容器 image（CI 會推到 GHCR，Argo CD 自動套用）"
  type        = string
  default     = "ghcr.io/lewislunora/xiangchuan/platform-app:latest"
}

variable "app_replicas" {
  description = "平台副本數"
  type        = number
  default     = 1
}
