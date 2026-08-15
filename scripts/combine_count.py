#!/usr/bin/env python3
"""Port of the upstream combine_count run: block (logic identical)."""

import argparse
import os
import sys

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--counts", required=True, nargs="+")
    p.add_argument("--metadata", required=True)
    p.add_argument("--output", required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # Fail fast when [config] db_id drifts from the metadata file name
    # (upstream derives DB_ID from the metadata at load time).
    expected_db_id = os.path.basename(args.metadata).replace(".txt", "")
    out_db_id = os.path.basename(args.output).replace(".tsv", "")
    if expected_db_id != out_db_id:
        print(
            f"error: db_id mismatch — metadata '{args.metadata}' implies db_id "
            f"'{expected_db_id}' but the declared output is '{args.output}'",
            file=sys.stderr,
        )
        sys.exit(1)

    df = pd.read_csv(args.counts[0], header=None, sep="\t", index_col=0)
    df = df.iloc[:, [0]]
    rename_dict = {1: os.path.basename(args.counts[0]).replace("_ReadsPerGene.out.tab", "")}
    df = df.rename(columns=rename_dict)
    for file in args.counts[1:]:
        df2 = pd.read_csv(file, header=None, sep="\t", index_col=0)
        df2 = df2.iloc[:, [0]]
        rename_dict = {1: os.path.basename(file).replace("_ReadsPerGene.out.tab", "")}
        df2 = df2.rename(columns=rename_dict)
        df = df2.merge(df, left_index=True, right_index=True)

    df.to_csv(args.output, sep="\t", encoding="utf-8")


if __name__ == "__main__":
    main()
