"""琥珀发版工具：构建签名 APK → 生成 update.json → 输出发布指引。

用法（在 amber 仓库根目录）：
    python core/tools/release.py --repo <owner/repo>          # 建仓后正式发版
    python core/tools/release.py --dry-run                    # 只构建不生成发布物

前置（一次性）：
  1. 签名：华灯仓库 local.properties 已配 storeFile/KeyAlias（amber-release.jks）
  2. 构建：在华灯仓库跑 gradle assembleRelease，产物 app-release.apk
  3. 发布：gh release create v<版本> APK --title ... --notes ...（需 gh 登录）
     然后把 update.json 提交到仓库根目录（jsDelivr 兜底源要求入库）

App 端：UpdateChecker 的 REPO 填 <owner/repo> 后自动启用检查；
主源 GitHub Releases API，兜底 update.json（jsDelivr 国内直连 + ghproxy 镜像）。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HUADENG = Path(r"D:/codex/AI_Workspace/projects/rikkahub-huadeng")
GRADLE = Path(r"D:/android-dev/gradle/gradle-9.6.0/bin/gradle.bat")


def read_gradle_version() -> tuple[str, int]:
    text = (HUADENG / "app/build.gradle.kts").read_text(encoding="utf-8")
    version_name = re.search(r'versionName\s*=\s*"([^"]+)"', text).group(1)
    version_code = int(re.search(r"versionCode\s*=\s*(\d+)", text).group(1))
    return version_name, version_code


def run_gradle(task: str) -> None:
    env_note = "JAVA_HOME=D:/android-dev/jdk"
    print(f"[release] gradle {task}（{env_note}，首次 R8 较慢）")
    subprocess.run([str(GRADLE), task, "--no-daemon"], cwd=HUADENG, check=True)


def make_update_json(repo: str, version: str, apk_size: int) -> dict:
    tag = f"v{version}"
    apk_name = "amber-release.apk"
    url = f"https://github.com/{repo}/releases/download/{tag}/{apk_name}"
    return {
        "version": version,
        "publishedAt": datetime.now(timezone.utc).isoformat(),
        "changelog": f"琥珀 {version}",
        "downloads": [
            {"name": apk_name, "url": url, "size": f"{apk_size / 1048576:.1f} MB", "fallbackUrl": url},
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="", help="GitHub 仓库 owner/repo（建仓后必填）")
    ap.add_argument("--dry-run", action="store_true", help="只构建 APK，不生成发布物")
    a = ap.parse_args()

    if not a.repo and not a.dry_run:
        print("[release] 尚未建立琥珀发布仓库：请先在 GitHub 建（建议名 amber）并 gh auth login，")
        print("          然后 python core/tools/release.py --repo <你的用户名>/amber")
        print("          仓库为空期间 App 内更新检查保持静默禁用（UpdateChecker REPO 留空）。")
        sys.exit(2)

    run_gradle("assembleRelease")
    apk = HUADENG / "app/build/outputs/apk/release/app-release.apk"
    if not apk.exists():
        print(f"[release] 未找到 {apk}")
        sys.exit(1)
    version, code = read_gradle_version()
    print(f"[release] APK 就绪：{apk}（v{version} / {code}，{apk.stat().st_size / 1048576:.1f} MB）")

    if a.dry_run:
        return

    out_dir = Path("dist/release")
    out_dir.mkdir(parents=True, exist_ok=True)
    update = make_update_json(a.repo, version, apk.stat().st_size)
    update_path = out_dir / "update.json"
    update_path.write_text(json.dumps(update, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "amber-release.apk").write_bytes(apk.read_bytes())
    print(f"[release] 发布物已输出：{update_path} + amber-release.apk")
    print(f"""
[release] 下一步（gh 已登录时逐条执行）：
  cd dist/release
  gh release create v{version} amber-release.apk --title "琥珀 v{version}" --notes "{update['changelog']}"
  gh api -X PUT repos/{a.repo}/contents/update.json \\
    -f message="release v{version}" \\
    -f content=$(python -c "import base64;print(base64.b64encode(open('update.json','rb').read()).decode())")
最后：把 UpdateChecker.kt 的 REPO 常量填为 "{a.repo}" 并重新构建一版 App（此后用户端自动检查更新）。
""")


if __name__ == "__main__":
    main()
