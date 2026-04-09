#!/usr/bin/env python3
"""
generate_tests.py — 通用 AI-CLI 版 Zeus 测试生成器
替代 generate-tests.sh，适用于任何不具备 claude CLI 的 AI 编程助手
（Kimi、GLM、DeepSeek、GPT/Codex、Gemini 等）
"""

import argparse
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Fix Windows console encoding for emoji/unicode output
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


PLATFORM_HINTS = {
    "android": '''Android 平台：使用 adb shell 命令操作设备。典型步骤示例：
- action: "adb -s emulator-5554 shell am start -n com.example.app/.MainActivity"
- action: "adb -s emulator-5554 shell input tap 540 960"
- action: "adb -s emulator-5554 shell input text \"hello@example.com\""
- assertion: "adb -s emulator-5554 shell dumpsys window windows | grep mCurrentFocus"
- expected: "com.example.app/.HomeActivity"''',
    "chrome": '''Chrome 平台：使用 chrome-cli 或 Google Chrome DevTools Protocol (CDP) 命令。典型步骤示例：
- action: "chrome-cli open \"https://example.com/login\""
- action: "chrome-cli execute \"document.querySelector('#email').value='test@example.com'\""
- action: "chrome-cli execute \"document.querySelector('button[type=submit]').click()\""
- assertion: "chrome-cli execute \"document.title\""
- expected: "Dashboard — Example App"''',
    "ios": '''iOS 平台：使用 xcrun simctl 命令操作模拟器，真机用 ideviceinstaller / libimobiledevice。典型步骤示例：
- action: "xcrun simctl launch booted com.example.app"
- action: "xcrun simctl io booted tap 195 420"
- action: "xcrun simctl spawn booted log stream --predicate 'subsystem == \"com.example.app\"'"
- assertion: "xcrun simctl spawn booted defaults read com.example.app userLoggedIn"
- expected: "1"''',
}


class TestGenerator:
    def __init__(self, version: str = "main"):
        self.version = version
        self.base_dir = Path(f".zeus/{version}")
        self.task_file = self.base_dir / "task.json"
        self.prd_file = self.base_dir / "prd.json"
        self.config_file = self.base_dir / "config.json"
        self.tests_dir = self.base_dir / "tests"
        self.schema_file = Path(".zeus/schemas/test-flow.schema.json")

    def _load_json(self, path: Path) -> dict:
        if not path.exists():
            print(f"❌ 文件不存在: {path}")
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_json(self, path: Path, data: dict) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def validate_environment(self) -> None:
        for f in [self.task_file, self.prd_file, self.schema_file, self.config_file]:
            if not f.exists():
                print(f"❌ 缺失前置文件: {f}")
                sys.exit(1)

    def build_prompt(self, platform: str) -> str:
        tasks = self._load_json(self.task_file)
        prd = self._load_json(self.prd_file)
        schema = self._load_json(self.schema_file)
        config = self._load_json(self.config_file)
        north_star = config.get("metrics", {}).get("north_star", "未设置")
        platform_guide = PLATFORM_HINTS.get(platform, "")
        generated_at = now_iso()

        prompt = f"""你是 Zeus 测试用例生成代理（zeus-tester）。
根据下方 task.json、prd.json 和 test-flow schema，为 {platform} 平台生成完整的测试流程 JSON。

## 规则

1. 只输出合法 JSON，不要输出任何 markdown 代码块包裹（不要 ```json），不要注释，不要解释文字。
2. 严格遵循 test-flow.schema.json 的字段定义。
3. 每个 task 至少生成 1 个 scenario，高优先级 story 对应的 task 生成 2~3 个 scenario（覆盖成功路径 + 1~2 个边界/失败路径）。
4. scenario.id 从 TC-001 开始递增。
5. steps 中 action 必须是可在真实 {platform} 环境中直接执行的原生命令字符串。
6. passes 全部初始化为 false，run_at 初始化为 null。
7. generated_from 填写所有 task 的 id 数组。
8. generated_at 填写当前 ISO 时间：{generated_at}

## 平台命令规范

{platform_guide}

## 北极星指标

{north_star}

## task.json

{json.dumps(tasks, indent=2, ensure_ascii=False)}

## prd.json

{json.dumps(prd, indent=2, ensure_ascii=False)}

## test-flow.schema.json

{json.dumps(schema, indent=2, ensure_ascii=False)}

## 输出

直接输出 {platform}.test.json 的完整 JSON 内容，platform 字段值为 "{platform}"，version 字段值为 "{self.version}"。
"""
        return prompt

    def run(self, platforms: list[str], force: bool = False) -> None:
        self.validate_environment()
        self.tests_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n═══════════════════════════════════════════════════")
        print(f"  Zeus Test Generator  version={self.version}")
        print(f"═══════════════════════════════════════════════════\n")

        total = len(platforms)
        success = 0
        fail = 0

        for platform in platforms:
            if platform not in PLATFORM_HINTS:
                print(f"⚠️  未知平台: {platform}（跳过）")
                continue

            out_file = self.tests_dir / f"{platform}.test.json"
            if out_file.exists() and not force:
                print(f"⏭️  {platform}.test.json 已存在，跳过（使用 --force 覆盖）")
                success += 1
                continue

            print(f"\n→  生成 {platform} 测试用例...")
            prompt = self.build_prompt(platform)

            print("\n" + "=" * 60)
            print(f"请复制以下 prompt 到你的 AI 会话中，生成 {platform}.test.json 的 JSON 内容：")
            print("=" * 60 + "\n")
            print(prompt)
            print("\n" + "=" * 60)

            user_input = input("\n请将生成的 JSON 内容粘贴到这里（输入 end 结束多行输入）:\n")
            lines = []
            while True:
                line = input()
                if line.strip() == "end":
                    break
                lines.append(line)
            raw_json = "\n".join(lines)

            # Clean markdown fences if any
            raw_json = raw_json.strip()
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:]
            if raw_json.startswith("```"):
                raw_json = raw_json[3:]
            if raw_json.endswith("```"):
                raw_json = raw_json[:-3]
            raw_json = raw_json.strip()

            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError as e:
                print(f"❌  {platform}: 输入内容不是合法 JSON: {e}")
                raw_path = out_file.with_suffix(out_file.suffix + ".raw")
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write(raw_json)
                print(f"   原始内容已保存到: {raw_path}")
                fail += 1
                continue

            self._save_json(out_file, data)
            scenario_count = len(data.get("scenarios", []))
            print(f"✅  {platform}.test.json 生成完成（{scenario_count} 个 scenario）")
            success += 1

        print(f"\n───────────────────────────────────────────────────")
        print(f"  完成：{success}/{total} 平台成功" + (f"，{fail} 个失败" if fail > 0 else ""))
        print(f"  输出目录：{self.tests_dir}/")
        print(f"───────────────────────────────────────────────────\n")

        if fail > 0:
            sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Zeus Test Generator (Python)")
    parser.add_argument("--version", default="main", help="目标版本 (默认: main)")
    parser.add_argument("--platforms", default="android,chrome,ios", help="平台列表，逗号分隔 (默认: android,chrome,ios)")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的测试文件")

    args = parser.parse_args()
    platforms = [p.strip() for p in args.platforms.split(",")]

    generator = TestGenerator(version=args.version)
    generator.run(platforms=platforms, force=args.force)


if __name__ == "__main__":
    main()
