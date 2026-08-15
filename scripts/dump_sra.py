#!/usr/bin/env python3
"""Port of the upstream data_conversion_pair rule.

Runs `fasterq-dump sra/<SRR> -O sra` for every SRR in the metadata.
Upstream schedules one job per SRR with a global cap of 2 concurrent dumps
(run.py --resources limit_dump=2); the port replicates the cap with an
internal worker pool of 2 and the identical command per SRR.
"""

import argparse
import concurrent.futures
import subprocess

import pandas as pd

# Upstream run.py --resources limit_dump=2
MAX_DUMP_WORKERS = 2


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata", required=True)
    p.add_argument("--separator", default=",")
    return p.parse_args()


def dump(srr: str) -> None:
    # Upstream shell: fasterq-dump sra/{wildcards.sra} -O sra
    subprocess.run(["fasterq-dump", f"sra/{srr}", "-O", "sra"], check=True)


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.metadata, sep="\t")

    srrs: list[str] = []
    for value in df["SRR"].to_list():
        srrs.extend(s.strip() for s in str(value).split(args.separator) if s.strip())

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_DUMP_WORKERS) as pool:
        list(pool.map(dump, srrs))


if __name__ == "__main__":
    main()
