import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / ".zeus" / "v2" / "scripts"))
from zeus_orchestrator import ZeusOrchestrator

async def main():
    orch = ZeusOrchestrator(version="v2", max_parallel=3)
    summary = await orch.run_global()
    log_path = Path(".zeus/v2/agent-logs/global-run-experiment.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("Global run finished:", summary)

if __name__ == "__main__":
    asyncio.run(main())
