resource "kubernetes_namespace" "platform" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }
}

resource "kubernetes_namespace" "argocd" {
  metadata {
    name = var.argocd_namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }
}

resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argocd_chart_version
  namespace        = kubernetes_namespace.argocd.metadata[0].name
  create_namespace = false
  timeout          = 600
  atomic           = true

  set {
    name  = "server.insecure"
    value = "true"
  }

  set {
    name  = "configs.params.server\\.insecure"
    value = "true"
  }

  set {
    name  = "redis-ha.enabled"
    value = "false"
  }

  set {
    name  = "controller.replicas"
    value = "1"
  }

  set {
    name  = "server.replicas"
    value = "1"
  }

  set {
    name  = "repoServer.replicas"
    value = "1"
  }

  depends_on = [kubernetes_namespace.argocd]
}

resource "kubernetes_config_map" "argocd_repo_access" {
  metadata {
    name      = "argocd-git-repo-access"
    namespace = kubernetes_namespace.argocd.metadata[0].name
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }

  data = {
    repo_url  = var.git_repo_url
    revision  = var.git_revision
    manifests = var.manifests_path
    app_image = var.app_image
  }

  depends_on = [helm_release.argocd]
}

# Application CRD 由 helm 裝上後，用 local-exec 套用 argocd/ 內的 manifest
# （kubernetes_manifest 在 CRD 尚未存在時會 plan 失敗，故走 apply 階段）
resource "terraform_data" "apply_argocd_app" {
  input = {
    repo_url  = var.git_repo_url
    revision  = var.git_revision
    path      = var.manifests_path
    namespace = var.argocd_namespace
    image     = var.app_image
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      kubectl apply -f "${path.module}/../argocd/project.yaml"
      kubectl -n ${var.argocd_namespace} apply -f "${path.module}/../argocd/application.yaml"
      kubectl -n ${var.argocd_namespace} annotate application xiangchuan-platform \
        argocd.argoproj.io/refresh=normal --overwrite || true
    EOT
  }

  depends_on = [helm_release.argocd]
}

output "argocd_namespace" {
  value       = kubernetes_namespace.argocd.metadata[0].name
  description = "Argo CD namespace"
}

output "platform_namespace" {
  value       = kubernetes_namespace.platform.metadata[0].name
  description = "平台 namespace"
}
