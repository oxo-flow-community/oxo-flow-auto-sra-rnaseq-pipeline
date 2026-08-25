#!/usr/bin/env python3
"""Port of the upstream data_conversion_pair / data_conversion_single rules.

Runs `fasterq-dump sra/<SRR>/<SRR>.sra -O sra` for every SRR in the metadata.
Upstream schedules one job per SRR with a global cap of 2 concurrent dumps
(run.py --resources limit_dump=2); the port replicates the cap with an
internal worker pool of 2 and the identical command per SRR.

fasterq-dump derives the output naming from the archive itself: paired-end
SRA archives produce sra/<SRR>_1.fastq + _2.fastq (upstream
data_conversion_pair outputs), single-end archives produce sra/<SRR>.fastq
(upstream data_conversion_single output). One script rule covers both —
the upstream needed two rules only because their DAG declared the output
names statically.
"""

import argparse
import os
import concurrent.futures
import subprocess

import pandas as pd

# Upstream run.py --resources limit_dump=2
MAX_DUMP_WORKERS = 2


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata", required=True)
    p.add_argument("--separator", default=",")
    p.add_argument("--sample", default=None,
                   help="dump only the SRRs of this GSM sample (per-sample rule)")
    return p.parse_args()


def dump(srr: str) -> None:
    # Upstream shell: fasterq-dump sra/{wildcards.sra} -O sra. {wildcards.sra}
    # is the .sra FILE — get_sra stores each download under
    # sra/<SRR>/<SRR>.sra. (Live: passing the sra/<SRR> directory made
    # fasterq-dump exit 0 without writing anything; the marker was then
    # written and the merge polled for 90 minutes for fastqs that never
    # appeared — v17 run end exit=1.)
    subprocess.run(
        ["fasterq-dump", f"sra/{srr}/{srr}.sra", "-O", "sra"], check=True
    )


def verify(srr: str) -> None:
    """fasterq-dump can exit 0 without producing output (see above); make
    that a hard failure instead of a silent one. Accept either the paired
    output shape (sra/{srr}_1.fastq + _2.fastq) or the single-end shape
    (sra/{srr}.fastq), matching what the archive actually contains."""
    single = os.path.exists(f"sra/{srr}.fastq")
    pair_1 = os.path.exists(f"sra/{srr}_1.fastq")
    pair_2 = os.path.exists(f"sra/{srr}_2.fastq")
    if not (single or (pair_1 and pair_2)):
        raise RuntimeError(
            f"fasterq-dump exited 0 but no FASTQ output for {srr} "
            f"(expected sra/{srr}.fastq or sra/{srr}_1.fastq + sra/{srr}_2.fastq)"
        )


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.metadata, sep="\t")
    if args.sample is not None:
        df = df[df["GSM"] == args.sample]

    srrs: list[str] = []
    for value in df["SRR"].to_list():
        srrs.extend(s.strip() for s in str(value).split(args.separator) if s.strip())

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_DUMP_WORKERS) as pool:
        list(pool.map(dump, srrs))

    for srr in srrs:
        verify(srr)

    # per-sample completion marker (declared rule output; also drives the
    # engine's per-sample fan-out of the dump rule)
    if args.sample is not None:
        with open(os.path.join("sra", args.sample + ".dumped"), "w") as fh:
            fh.write("ok\n")


if __name__ == "__main__":
    main()
