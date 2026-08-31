from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from frontier_pipeline.env import load_dotenv
from frontier_pipeline.graph.loader import load_graph
from frontier_pipeline.graph.runner import GraphRunner
from frontier_pipeline.llm.factory import get_provider
from frontier_pipeline.nodes.registry import build_default_registry
from frontier_pipeline.publish import publish_friday_artifacts
from frontier_pipeline.wiki_bootstrap import bootstrap_wiki


def _is_friday_graph(graph_name: str, graph_path: Path) -> bool:
    return graph_name == "friday_report" or "friday_report" in graph_path.as_posix()


def _friday_report_date(artifact_dir: Path) -> str:
    report_json = artifact_dir / "report.json"
    if report_json.exists():
        data = json.loads(report_json.read_text(encoding="utf-8"))
        report_date = data.get("report_date")
        if report_date:
            return str(report_date)
    return datetime.now(timezone.utc).date().isoformat()


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="frontier-pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)

    boot = sub.add_parser("bootstrap-wiki")
    boot.add_argument("--wiki", type=Path, default=Path("wiki"))

    run = sub.add_parser("run")
    run.add_argument("--graph", type=Path, required=True)
    run.add_argument("--repo-root", type=Path, default=Path.cwd())
    run.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    run.add_argument("--run-id", type=str, default="")
    run.add_argument(
        "--llm",
        type=str,
        default=None,
        help="Provider name: dashscope|anthropic|fake (default: FRONTIER_LLM_PROVIDER or dashscope)",
    )

    args = parser.parse_args(argv)
    if args.cmd == "bootstrap-wiki":
        bootstrap_wiki(args.wiki)
        return
    if args.cmd == "run":
        run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        provider = get_provider(args.llm)
        runner = GraphRunner(
            registry=build_default_registry(),
            artifacts_root=args.artifacts,
            repo_root=args.repo_root,
            llm=provider,
        )
        graph = load_graph(args.graph)
        manifest = runner.run(graph, run_id=run_id)
        failed = [n for n in manifest.nodes if n.status == "failed"]
        artifact_dir = args.artifacts / run_id
        hard_pass = True
        if _is_friday_graph(graph.name, args.graph):
            report_date = _friday_report_date(artifact_dir)
            hard_pass = publish_friday_artifacts(
                artifact_dir, args.repo_root, report_date
            )
        if failed or not hard_pass:
            raise SystemExit(1)
        return
    raise SystemExit(2)


if __name__ == "__main__":
    main()
