from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from novel_scanner.scanner import NovelScanner

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Novel Scanner CLI")
    parser.add_argument("--input", required=True, help="Path to the novel text file")
    parser.add_argument("--ai-config", required=True, help="Path to AI config YAML")
    parser.add_argument(
        "--pipeline-config", required=True, help="Path to pipeline config YAML"
    )
    parser.add_argument(
        "--prompts-dir", required=True, help="Directory containing prompt templates"
    )
    parser.add_argument(
        "--world-info", help="Path to world information file", default=None
    )
    parser.add_argument(
        "--output-dir", help="Directory to save the output", default=None
    )
    parser.add_argument(
        "--context-override",
        type=int,
        default=None,
        help="Override the maximum context tokens",
    )
    return parser.parse_args()


def load_world_info(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    world_path = Path(path)
    if not world_path.exists():
        console.print(f"[yellow]World info file not found: {path}")
        return None
    return world_path.read_text(encoding="utf-8")


def main() -> None:
    args = parse_args()

    console.print("[bold cyan]📚 Novel Scanner Starting...")

    world_info = load_world_info(args.world_info)

    scanner = NovelScanner(
        ai_config_path=args.ai_config,
        pipeline_config_path=args.pipeline_config,
        prompts_dir=args.prompts_dir,
    )

    async def run_scan() -> None:
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task(description="Processing novel...", total=None)
            result = await scanner.scan_novel(
                novel_path=args.input,
                world_info=world_info,
                context_override=args.context_override,
            )

        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / (Path(args.input).stem + "_summary.txt")
            output_content = result.get("merge") or result
            output_path.write_text(str(output_content), encoding="utf-8")
            console.print(f"[green]Output saved to {output_path}")

        console.print("[bold green]✅ Novel scanning completed!")

    asyncio.run(run_scan())


if __name__ == "__main__":
    main()
