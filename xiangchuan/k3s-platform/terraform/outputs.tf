output "argocd_ready_hint" {
  value       = "argocd app list  # 或 kubectl -n argocd get applications"
  description = "Argo CD 檢查指令"
}

output "git_repo_url" {
  value       = var.git_repo_url
  description = "GitOps repo"
}

output "manifests_path" {
  value       = var.manifests_path
  description = "Argo CD 同步路徑"
}
