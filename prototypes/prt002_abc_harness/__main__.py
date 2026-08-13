"""Create a PRT-002 pre-registered batch; this command never creates a RUN artifact."""

from __future__ import annotations

import argparse
from pathlib import Path

from .harness import PreregisteredBatch


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Create a non-canonical PRT-002 A/B/C batch")
    parser.add_argument("--outdir", required=True, help="External directory for non-versioned prototype artifacts")
    parser.add_argument("--agent-model", required=True, help="Exact model/provider identity recorded before trial setup")
    parser.add_argument("--operator", required=True, help="Person/system operating the batch")
    parser.add_argument("--source-revision", required=True, help="Exact harness/repository revision used for the batch")
    parser.add_argument("--repeats-per-variant", type=int, default=3)
    args = parser.parse_args(argv)
    batch = PreregisteredBatch.create(
        Path(args.outdir),
        agent_model=args.agent_model,
        operator=args.operator,
        source_revision=args.source_revision,
        repeats_per_variant=args.repeats_per_variant,
    )
    print(f"Non-canonical PRT-002 batch created: {batch.batch_dir}")


if __name__ == "__main__":
    main()
