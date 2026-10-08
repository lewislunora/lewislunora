#!/usr/bin/env python3
"""本地一鍵 GitOps 部署編排：terraform apply → argocd sync → health check。

用法：
    python deploy.py plan              # 只看 terraform plan（唯讀）
    python deploy.py apply             # terraform apply（會改叢集）
    python deploy.py sync              # 觸發 Argo CD 同步並等待
    python deploy.py status            # 查看 Argo CD / workload 狀態
    python deploy.py up --yes          # 全流程（apply + sync + status）
    python deploy.py health            # 打 /api/status 檢查

環境變數：
    KUBECONFIG   kubeconfig 路徑（預設 ~/.kube/config）
    SITE_URL     health check 網址（預設 http://localhost）
    ARGOCD_*     可選，若 argocd CLI 已 login 則直接使用
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
TF_DIR = os.path.join(BASE, "terraform")
ARGO_DIR = os.path.join(BASE, "argocd")
APP_NAME = "xiangchuan-platform"
NAMESPACE = "platform"


def run(cmd: list[str], cwd: str | None = None, check: bool = True) -> int:
    print(f"$ {' '.join(cmd)}")
    if args.dry_run and cmd and cmd[0] in {"terraform", "kubectl"} and not cmd[1:2] == ["plan"]:
        print("  (dry-run 跳過)")
        return 0
    proc = subprocess.run(cmd, cwd=cwd)
    if check and proc.returncode != 0:
        sys.exit(proc.returncode)
    return proc.returncode


def need(tool: str) -> None:
    if shutil.which(tool) is None:
        print(f"錯誤：找不到 {tool}，請先安裝")
        sys.exit(1)


def cmd_plan() -> None:
    need("terraform")
    run(["terraform", "init", "-input=false"], cwd=TF_DIR)
    run(["terraform", "plan", "-input=false"], cwd=TF_DIR)


def cmd_apply() -> None:
    need("terraform")
    need("kubectl")
    if not args.yes:
        print("這會實際變更叢集。確認請加 --yes")
        sys.exit(1)
    run(["terraform", "init", "-input=false"], cwd=TF_DIR)
    run(["terraform", "apply", "-auto-approve", "-input=false"], cwd=TF_DIR)


def cmd_sync() -> None:
    need("kubectl")
    if not args.yes:
        print("這會觸發 Argo CD 同步。確認請加 --yes")
        sys.exit(1)
    kubectl = ["kubectl", "-n", "argocd"]
    run(kubectl + ["apply", "-f", os.path.join(ARGO_DIR, "project.yaml")])
    run(kubectl + ["apply", "-f", os.path.join(ARGO_DIR, "application.yaml")])
    run(
        kubectl
        + [
            "annotate",
            "application",
            APP_NAME,
            "argocd.argoproj.io/refresh=normal",
            "--overwrite",
        ],
        check=False,
    )
    if shutil.which("argocd"):
        run(["argocd", "app", "wait", APP_NAME, "--timeout", "300", "--sync", "--health"], check=False)
    else:
        print("argocd CLI 未安裝，改用 kubectl 輪詢同步狀態（Argo CD 自同步最長約 3 分鐘）")
        deadline = time.time() + 300
        while time.time() < deadline:
            out = subprocess.run(
                ["kubectl", "-n", "argocd", "get", "application", APP_NAME, "-o", "jsonpath={.status.sync.status}"],
                capture_output=True,
                text=True,
            )
            if out.stdout.strip() == "Synced":
                print("Synced")
                return
            print(f"  status.sync = {out.stdout.strip() or 'Unknown'}，等待中...")
            time.sleep(10)
        print("逾時未 Synced，可用 `python deploy.py status` 查看")


def cmd_status() -> None:
    need("kubectl")
    run(["kubectl", "-n", "argocd", "get", "applications"], check=False)
    run(["kubectl", "-n", NAMESPACE, "get", "pods,svc,ingress", "-o", "wide"], check=False)
    run(["kubectl", "-n", NAMESPACE, "rollout", "status", "deploy/platform-app", "--timeout=60s"], check=False)


def cmd_health() -> None:
    url = os.environ.get("SITE_URL", "http://localhost").rstrip("/") + "/api/status"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            body = resp.read(500).decode("utf-8", "replace")
            print(f"HTTP {resp.status} {url}\n{body}")
    except Exception as exc:  # noqa: BLE001
        print(f"health check 失敗：{exc}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="翔川 GitOps 本地編排")
    parser.add_argument("command", choices=["plan", "apply", "sync", "status", "up", "health"])
    parser.add_argument("--yes", action="store_true", help="確認執行變更性操作")
    parser.add_argument("--dry-run", action="store_true", help="只印指令不執行")
    global args
    args = parser.parse_args()

    if args.command == "plan":
        cmd_plan()
    elif args.command == "apply":
        cmd_apply()
    elif args.command == "sync":
        cmd_sync()
    elif args.command == "status":
        cmd_status()
    elif args.command == "health":
        cmd_health()
    elif args.command == "up":
        cmd_apply()
        cmd_sync()
        cmd_status()
        cmd_health()


if __name__ == "__main__":
    main()
