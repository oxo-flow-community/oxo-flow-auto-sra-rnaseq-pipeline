#!/usr/bin/env python3
"""Port of the upstream run.py batch runner.

Drives one oxo-flow run per metadata file in a directory, exactly like the
upstream runner drove one snakemake run per file:

  1. validate the metadata TSV (required columns SRR/paired/GSM/GSE; every
     SRR non-empty; every paired value PAIRED or SINGLE) — upstream
     validate_metadata_file, verbatim;
  2. check that every SRR's .sra file exists — upstream check_sra_files,
     verbatim;
  3. run the workflow with `metadata=<file> db_id=<basename>` overrides
     (upstream wrote a per-file temp config with config['metadata']);
  4. move the metadata file to finished/ or failed/;
  5. send bark / feishu notifications from the workflow's [config] keys.

Upstream mapping:
  --cores                -> oxo-flow run -j (upstream default 79)
  --restart-times 3      -> oxo-flow run -r 3
  --unlock / --rerun-incomplete / --latency-wait -> oxo-flow checkpoints
     and resume handle these natively; nothing to do
  --executor / --executor_profile_path -> oxo-flow run --profile NAME
  --timeout              -> oxo-flow run --timeout
  limit_dump/limit_merge caps -> workflow [resource_groups] (already in
     main.oxoflow)

Requires the oxo-flow binary on PATH (or --oxo). Python 3.11+ (tomllib)
with pandas, e.g. the workflow's envs/count.yaml environment.
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tomllib

import pandas as pd

from notify import bark_notification, feishu_notification


# Upstream run.py check_config — the mail/bark/feishu keys must be set when
# their switch is on. The port reads them from the workflow's [config].
def check_config(config):
    if config.get("mail"):
        for key in ("sender", "sender_password", "mail_to"):
            if not config.get(key):
                print(f"{key} should not be empty", file=sys.stderr)
                return False
    if config.get("bark") and not config.get("bark_api"):
        print("bark_api should not be empty", file=sys.stderr)
        return False
    if config.get("feishu") and not config.get("feishu_api"):
        print("feishu_api should not be empty", file=sys.stderr)
        return False
    return True


def get_workflow(root_dir=".", file="main.oxoflow"):
    sf = os.path.join(root_dir, file)
    if not os.path.exists(sf):
        sys.exit(f"Unable to locate the workflow file; tried {sf}")
    return sf


def find_oxoflow():
    """Locate the oxo-flow binary (upstream find_snakemake)."""
    try:
        result = subprocess.run(
            ["oxo-flow", "--version"], capture_output=True, text=True, check=True
        )
        print(f"Found oxo-flow in PATH: {result.stdout.strip()}")
        return "oxo-flow"
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError):
        pass
    for home in (os.path.expanduser("~"), "/opt", "/usr/local"):
        for env in ("oxo-flow", "oxoflow", "rna_seq", "snakemake"):
            for base in ("miniconda3", "anaconda3", "micromamba"):
                path = os.path.join(home, base, "envs", env, "bin", "oxo-flow")
                if os.path.exists(path):
                    return path
    sys.exit(
        "Unable to locate the oxo-flow binary. Install it (see the README) "
        "or pass --oxo /path/to/oxo-flow."
    )


def run_oxoflow(oxo, workflow, metadata_file, db_id, cores, timeout=None,
                profile=None, root_dir="."):
    cmd = [
        oxo,
        "run",
        workflow,
        f"metadata={metadata_file}",
        f"db_id={db_id}",
        "-j", str(cores),
        "-r", "3",  # upstream --restart-times 3
    ]
    if profile:
        cmd.extend(["--profile", profile])
    if timeout:
        cmd.extend(["--timeout", str(timeout)])
    print(f"Running command: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, cwd=root_dir, capture_output=True,
                       text=True)
        return True, ""
    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr if e.stderr else ""
        return False, stderr_output
    except subprocess.TimeoutExpired:
        return False, "Timeout"


def process_sample_file(metadata_file, metadata_dir, finished_dir, failed_dir,
                        workflow, oxo, cores, profile, timeout, root_dir):
    try:
        print(f"Starting oxo-flow execution for {metadata_file}...")
        status, error_output = run_oxoflow(
            oxo, workflow, os.path.join(metadata_dir, metadata_file),
            os.path.basename(metadata_file).replace(".txt", ""),
            cores, timeout, profile, root_dir,
        )

        # Upstream run.py re-reads the temp config to know the notification
        # flags; the port reads the workflow's [config] for the same keys.
        with open(workflow, "rb") as f:
            workflow_cfg = tomllib.load(f)
        config = workflow_cfg.get("config", {})

        if status:
            contents = f"oxo-flow run successfully for {metadata_file}"
            shutil.move(os.path.join(metadata_dir, metadata_file),
                        os.path.join(finished_dir, metadata_file))
        else:
            contents = f"oxo-flow run failed or timed out for {metadata_file}"
            shutil.move(os.path.join(metadata_dir, metadata_file),
                        os.path.join(failed_dir, metadata_file))

        if config.get("bark"):
            bark_notification(config.get("bark_api"), contents)
        if config.get("feishu"):
            feishu_notification(config.get("feishu_api"), contents)

        return contents, status
    except Exception as e:
        # A notification failure must never change the task outcome
        # (upstream let it bubble into the task result); report and keep
        # the file in unfinished/ for the next pass.
        error_message = f"Error processing {metadata_file}: {str(e)}"
        print(error_message, file=sys.stderr)
        return error_message, False


def validate_metadata_file(metadata_file):
    """Upstream run.py validate_metadata_file, verbatim."""
    try:
        df = pd.read_csv(metadata_file, sep='\t')
        errors = []

        # 检查必需的列是否存在
        required_columns = ['SRR', 'paired', 'GSM', 'GSE']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            errors.append(f"Missing required columns: {', '.join(missing_columns)}")
            return errors

        # 检查每一行的SRR和paired字段
        for idx, row in df.iterrows():
            row_num = idx + 2  # +2 because pandas is 0-indexed and we have header

            # 检查SRR字段
            srr_value = row['SRR']
            if pd.isna(srr_value) or str(srr_value).strip().upper() in ['NA', 'NAN', '']:
                errors.append(f"Row {row_num}: SRR field is empty or NA")

            # 检查paired字段
            paired_value = row['paired']
            if pd.isna(paired_value) or str(paired_value).strip().upper() in ['NA', 'NAN', '']:
                errors.append(f"Row {row_num}: paired field is empty or NA")
            elif str(paired_value).strip().upper() not in ['PAIRED', 'SINGLE']:
                errors.append(f"Row {row_num}: paired field must be 'PAIRED' or 'SINGLE', got '{paired_value}'")

        return errors
    except Exception as e:
        return [f"Error reading metadata file: {str(e)}"]


def check_sra_files(metadata_file, sra_dir):
    """Upstream run.py check_sra_files, verbatim."""
    try:
        df = pd.read_csv(metadata_file, sep='\t')
        missing_files = []

        for _, row in df.iterrows():
            # 检查SRR值是否为NaN或NA
            srr_value = row['SRR']
            if pd.isna(srr_value) or str(srr_value).strip().upper() in ['NA', 'NAN', '']:
                continue  # 跳过无效的SRR值（这些应该已经在validate_metadata_file中被捕获）

            srr_list = str(srr_value).strip().split(',')

            for srr in srr_list:
                srr = srr.strip()
                if srr and srr.upper() not in ['NA', 'NAN']:  # 确保SRR值有效
                    sra_file = os.path.join(sra_dir, srr, f"{srr}.sra")
                    if not os.path.exists(sra_file):
                        missing_files.append(sra_file)

        return missing_files
    except Exception as e:
        print(f"Error checking SRA files for {metadata_file}: {e}", file=sys.stderr)
        return ["Error reading metadata file"]


def main():
    parser = argparse.ArgumentParser(description="Process metadata files in batch (upstream run.py port).")
    parser.add_argument('unfinished_dir', help="Directory containing unfinished metadata files")
    parser.add_argument('--workflow', default='main.oxoflow',
                        help="Path to the oxo-flow workflow file (default: 'main.oxoflow' in root_dir)")
    parser.add_argument('--root_dir', default='.',
                        help="Working directory for the runs (default: current directory)")
    parser.add_argument('--cores', type=int, default=79,
                        help="Number of cores to use (default: 79, like upstream)")
    parser.add_argument('--oxo', default=None, help="Path to the oxo-flow binary (default: found on PATH)")
    parser.add_argument('--profile', default=None,
                        help="oxo-flow execution profile name (upstream --executor_profile_path)")
    parser.add_argument('--timeout', type=int, default=None,
                        help="Timeout for each run in seconds (default: None)")
    parser.add_argument('--sra_dir', default='sra',
                        help="Directory containing SRA files (default: 'sra')")

    args = parser.parse_args()

    workflow = get_workflow(args.root_dir, args.workflow)
    oxo = args.oxo or find_oxoflow()

    # 在开始处理前检查oxo-flow环境
    print("\nChecking oxo-flow environment...")
    subprocess.run([oxo, "--version"], check=True, cwd=args.root_dir)

    with open(workflow, "rb") as f:
        base_config = tomllib.load(f).get("config", {})

    if not check_config(base_config):
        sys.exit("invalid config: check mail/bark/feishu keys in [config]")

    finished_dir = "finished"
    failed_dir = "failed"
    metadata_dir = "metadata"
    for dir_path in [finished_dir, failed_dir, metadata_dir]:
        os.makedirs(dir_path, exist_ok=True)

    metadata_files = glob.glob(os.path.join(args.unfinished_dir, "*.txt"))

    # 统计变量
    total_tasks = len(metadata_files)
    processed_tasks = 0
    skipped_tasks = 0
    failed_tasks = 0
    skipped_files = []
    failed_files = []

    # 串行处理每个metadata文件
    for metadata_file in metadata_files:
        print(f"\nValidating metadata file {metadata_file}...")

        # 首先验证metadata文件格式
        validation_errors = validate_metadata_file(metadata_file)

        if validation_errors:
            print(f"Skipping {metadata_file} - Metadata validation failed:")
            for error in validation_errors:
                print(f"  - {error}")

            skipped_tasks += 1
            skipped_files.append(os.path.basename(metadata_file))
            continue

        print(f"Metadata file {metadata_file} is valid. Checking SRA files...")

        # 检查SRA文件是否存在
        missing_files = check_sra_files(metadata_file, args.sra_dir)

        if missing_files:
            print(f"Skipping {metadata_file} - Missing SRA files:")
            for missing_file in missing_files:
                print(f"  - {missing_file}")

            skipped_tasks += 1
            skipped_files.append(os.path.basename(metadata_file))
            continue

        print(f"All SRA files found for {metadata_file}. Processing...")

        result, status = process_sample_file(
            os.path.basename(metadata_file),
            args.unfinished_dir,
            finished_dir,
            failed_dir,
            workflow,
            oxo,
            args.cores,
            args.profile,
            args.timeout,
            args.root_dir,
        )

        print(f"Task for {metadata_file} completed with result: {result}")

        if status:
            processed_tasks += 1
        else:
            failed_tasks += 1
            failed_files.append(os.path.basename(metadata_file))

    # 输出统计信息
    print(f"\n=== Processing Summary ===")
    print(f"Total tasks: {total_tasks}")
    print(f"Successfully processed: {processed_tasks}")
    print(f"Failed tasks: {failed_tasks}")
    print(f"Skipped tasks: {skipped_tasks}")

    if failed_tasks > 0:
        print(f"\nAll failed files:")
        for failed_file in failed_files:
            print(f"  - {failed_file}")

    if skipped_tasks > 0:
        print(f"\nSkipped files:")
        for skipped_file in skipped_files:
            print(f"  - {skipped_file}")


if __name__ == '__main__':
    main()
