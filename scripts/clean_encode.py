#!/usr/bin/env python3
"""Port of the upstream Snakefile_ENCODE data_clean_pair rule and its
get_raw_data input function.

The ENCODE metadata names the input FASTQ files per sample via the
R1_file_accession / R2_file_accession columns (file name != sample name),
which oxo-flow static inputs cannot express — the port moves the fastp
invocation into a per-sample script rule, like the other metadata-driven
rules of this port (get_sra, sra_dump, merge_reads).

Runs the byte-identical upstream fastp command:
  fastp -w 8 -i 00_raw_data/{R1}.fastq.gz [-I 00_raw_data/{R2}.fastq.gz]
        -o 01_clean_data/{sample}_R1.fq [-O 01_clean_data/{sample}_R2.fq]
        -j log/{sample}.json -h log/{sample}.html &> log/{sample}_fastp.log
(--mode single omits the -I/-O pair, mirroring the fixed upstream single-end
path of the main Snakefile's data_clean_single rule; the upstream ENCODE
file has no single-end clean rule and its fixed -I {input[1]} would IndexError.)

Fidelity note: the workflow routes samples by [[sample_groups]] metadata
(runtype = "paired-ended" / "single-ended"); the metadata `runtype` column
is authoritative, so a sample declared in the wrong group fails fast here
instead of producing a wrong-shaped file.
"""

import argparse
import os
import subprocess
import sys

import pandas as pd

FASTP_THREADS = 8  # upstream fastp_threads = 8 (baked, like data_clean_pair)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata", required=True)
    p.add_argument("--sample", required=True)
    p.add_argument("--mode", required=True, choices=["paired", "single"])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.metadata, sep="\t")

    rows = df.loc[df["sample"] == args.sample]
    if rows.empty:
        print(f"error: sample {args.sample} not found in metadata", file=sys.stderr)
        sys.exit(1)
    row = rows.iloc[0]

    runtype = str(row["runtype"]).strip().lower()
    expected = "paired-ended" if args.mode == "paired" else "single-ended"
    if runtype != expected:
        print(
            f"error: sample {args.sample} has runtype='{runtype}' in the metadata but "
            f"this is the {args.mode}-end clean rule (expected '{expected}'); "
            f"move it to the matching [[sample_groups]] entry",
            file=sys.stderr,
        )
        sys.exit(1)

    r1 = f"00_raw_data/{row['R1_file_accession']}.fastq.gz"
    if not os.path.exists(r1):
        print(f"error: input FASTQ not found: {r1}", file=sys.stderr)
        sys.exit(1)

    if args.mode == "paired":
        r2 = f"00_raw_data/{row['R2_file_accession']}.fastq.gz"
        if not os.path.exists(r2):
            print(f"error: input FASTQ not found: {r2}", file=sys.stderr)
            sys.exit(1)
        cmd = (
            f"fastp -w {FASTP_THREADS} -i {r1} -I {r2} "
            f"-o 01_clean_data/{args.sample}_R1.fq -O 01_clean_data/{args.sample}_R2.fq "
            f"-j log/{args.sample}.json -h log/{args.sample}.html "
            f"&> log/{args.sample}_fastp.log"
        )
    else:
        cmd = (
            f"fastp -w {FASTP_THREADS} -i {r1} "
            f"-o 01_clean_data/{args.sample}.fq "
            f"-j log/{args.sample}.json -h log/{args.sample}.html "
            f"&> log/{args.sample}_fastp.log"
        )

    os.makedirs("log", exist_ok=True)
    subprocess.run(cmd, shell=True, check=True)


if __name__ == "__main__":
    main()
