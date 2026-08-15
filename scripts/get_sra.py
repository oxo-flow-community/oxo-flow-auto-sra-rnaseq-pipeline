#!/usr/bin/env python3
"""Port of the upstream Snakefile get_sra run: block (logic identical).

Verifies locally downloaded .sra files exist and symlinks them into
sra/<SRR>/<SRR>.sra.

Fidelity note: the upstream block iterates metadata SRR values without
splitting; the port splits on the srr_separator like the upstream merge
input functions and run.py check_sra_files do (upstream get_sra itself has
a latent bug for multi-SRR rows).
"""

import argparse
import os
import sys

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--metadata", required=True)
    p.add_argument("--sra-data-path", default="sra")
    p.add_argument("--separator", default=",")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.metadata, sep="\t")

    for value in df["SRR"].to_list():
        for sra_id in str(value).split(args.separator):
            sra_id = sra_id.strip()
            if not sra_id:
                continue

            sra_file = os.path.join(args.sra_data_path, sra_id, f"{sra_id}.sra")

            # 检查文件是否存在
            if not os.path.exists(sra_file):
                raise FileNotFoundError(f"SRA file not found: {sra_file}")

            # 创建输出目录
            output = os.path.join("sra", sra_id, f"{sra_id}.sra")
            os.makedirs(os.path.dirname(output), exist_ok=True)

            # 如果源文件和目标文件不是同一个路径，创建符号链接
            if os.path.abspath(sra_file) != os.path.abspath(output):
                if os.path.exists(output):
                    os.remove(output)
                os.symlink(os.path.abspath(sra_file), output)
                print(f"Created symlink: {output} -> {sra_file}")
            else:
                print(f"Using existing SRA file: {output}")


if __name__ == "__main__":
    main()
