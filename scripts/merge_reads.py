#!/usr/bin/env python3
"""Port of the upstream merge_R1_data / merge_R2_data rules and their
get_merged_input_data_R1/R2 input functions.

Concatenates the per-SRR FASTQ files of one sample in metadata order
(upstream shell: `cat {input} > {output}`).
"""

import argparse
import time
import os
import shutil
import sys

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata", required=True)
    p.add_argument("--separator", default=",")
    p.add_argument("--sample", required=True)
    p.add_argument("--read", required=True, choices=["1", "2"])
    p.add_argument("--output", required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.metadata, sep="\t")

    rows = df.loc[df["GSM"] == args.sample]
    if rows.empty:
        print(f"error: sample {args.sample} not found in metadata", file=sys.stderr)
        sys.exit(1)

    srr_ids = rows["SRR"].tolist()[0].split(args.separator)
    inputs = [f"sra/{srr}_{args.read}.fastq" for srr in srr_ids]

    missing = [f for f in inputs if not os.path.exists(f)]
    if missing:
        # The dump rules run concurrently with this merge (engine-level
        # depends_on would serialize ALL dump instances); poll until our
        # per-sample reads appear, then merge and delete them.
        print(f"waiting for FASTQ file(s): {', '.join(missing)}", file=sys.stderr)
        waited = 0
        while waited < 5400 and any(not os.path.exists(x) for x in inputs):
            time.sleep(30)
            waited += 30
        missing = [x for x in inputs if not os.path.exists(x)]
        if missing:
            print(f"error: FASTQ file(s) never appeared: {', '.join(missing)}", file=sys.stderr)
            sys.exit(1)

    with open(args.output, "wb") as out:
        for path in inputs:
            with open(path, "rb") as fh:
                # stream in chunks — fh.read() loads a whole ~13GB FASTQ into
                # memory (MemoryError on a 3.7GB box; upstream shells cat the
                # files, which streams)
                shutil.copyfileobj(fh, out, length=64 * 1024 * 1024)
            # upstream temp(): the per-SRR dump FASTQs are deleted once the
            # merge consumes them (they are only read here; keeping them
            # doubles the pipeline's peak disk by the raw read size)
            os.remove(path)


if __name__ == "__main__":
    main()
