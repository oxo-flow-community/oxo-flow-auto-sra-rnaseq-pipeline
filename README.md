# oxo-flow-auto-sra-rnaseq-pipeline — SRA-powered RNA-seq: .sra archives to differential expression

[![CI](https://github.com/oxo-flow-community/oxo-flow-auto-sra-rnaseq-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/oxo-flow-community/oxo-flow-auto-sra-rnaseq-pipeline/actions/workflows/ci.yml)

> ★ Verified · ⇄ Official port of [`xuzhougeng/auto_sra_rnaseq_pipeline`](https://github.com/xuzhougeng/auto_sra_rnaseq_pipeline) @ `923b9e9`
> — same tools, same versions, same commands. Part of the
> [oxo-flow-community catalog](https://oxo-flow-community.github.io/).

Automated RNA-seq processing from locally downloaded SRA archives to
differential expression results. The workflow verifies and symlinks your
`.sra` files, converts them to FASTQ with fasterq-dump, merges multiple SRR
runs per sample, trims with fastp, aligns with STAR (producing gene counts
and coordinate-sorted BAMs), indexes BAMs, generates BPM-normalized bigWig
signal tracks, merges the per-sample count tables into one matrix, and runs
DESeq2 differential analysis with ashr shrinkage using the sample groups
from your metadata table.

## Installation

### 1. Install oxo-flow

Requires **oxo-flow ≥ 0.11.0**. Release binary (recommended):

```bash
curl -fL -o oxo-flow.tar.gz \
  https://github.com/Traitome/oxo-flow/releases/download/v0.11.0/oxo-flow-v0.11.0-x86_64-unknown-linux-gnu.tar.gz
tar xzf oxo-flow.tar.gz
sudo mv oxo-flow /usr/local/bin/
```

Alternative: `conda install -c bioconda oxo-flow-cli` (the bioconda package
may lag behind releases; other platform binaries are on the releases page).

### 2. Get this workflow

```bash
git clone https://github.com/oxo-flow-community/oxo-flow-auto-sra-rnaseq-pipeline.git
```

### 3. Requirements

- **Reference data**: a STAR index directory (`config.index`, e.g.
  `/data/reference/genome/GRCh38/STAR`) and a GTF matching the STAR index
  (`config.GTF`).
- **Input data**: pre-downloaded SRA archives at
  `<sra_data_path>/<SRR>/<SRR>.sra` (default `sra/…`), and a metadata TSV
  (one row per sample) with the columns:
  `Dataset GSE GSM gene method celline group group_name type platform SRR paired`.
  Multiple SRR runs per sample are comma-joined in the `SRR` column
  (separator configurable via `srr_separator`). The `group` column holds
  the DESeq2 design groups (`treat` / `control`).
- **Compute**: up to 20 threads / 10 GB per rule (`align_and_count`), 8
  threads (`data_clean_pair`), 10 (`bamtobw`), 4 (`build_bam_index`).
- **Tools**: conda environments with pinned versions — see `envs/`
  (`align`, `preprocess`, `download`, `count`, `deseq2`). oxo-flow sets up
  each environment automatically on first run.

## Usage

```bash
# 1. Place your metadata at <metadata> (default test/fixtures/metadata/D21122.txt)
#    and your .sra files at <sra_data_path>/<SRR>/<SRR>.sra (default sra/<SRR>/<SRR>.sra)
# 2. Edit main.oxoflow:
#    - [[sample_groups]] samples  — keep in sync with the GSM column of your metadata
#    - [config] db_id             — your metadata file name without the .txt suffix
#    - [config] index / GTF       — your STAR index directory and GTF
# 3. Preview the plan
oxo-flow dry-run main.oxoflow
# 4. Run
oxo-flow run main.oxoflow -j 8
```

Results: merged count matrix `03_merged_counts/<DB_ID>.tsv`, bigWig tracks
`04_bigwig/<sample>.bw`, DESeq2 results `05_DGE_analysis/<DB_ID>.Rds`
(exprSet + metadata + ashr-shrunk diffResults). Intermediates
(`00_raw_data`, `01_clean_data`, `02_read_align`) are cleaned up when the
run finishes, as in the upstream workflow.

## Fidelity

| Upstream rule | oxo-flow rule | Tool (version) | Notes |
|---|---|---|---|
| get_sra | `get_sra` | python 3.11 + pandas 3.0.5 | run: block ported to `scripts/get_sra.py` (identical symlink logic). Single-instance script rule (oxo-flow fans out over `{sample}`/`{pair_id}` only); iterates the same metadata SRR values. Splits multi-SRR values on `srr_separator` like the upstream merge input functions and run.py `check_sra_files` (upstream get_sra itself does not split — latent bug for multi-SRR rows). No declared outputs (per-SRR paths are dynamic). |
| data_conversion_pair | `data_conversion_pair` | sra-tools 3.1.1 | `fasterq-dump sra/<SRR> -O sra` identical per SRR. Upstream runs one job per SRR capped at 2 concurrent dumps (run.py `--resources limit_dump=2`); the port runs a script with an internal worker pool of 2. Script deps (python/pandas) join the download env — oxo-flow runs one environment per rule, upstream split input function (base env) and command (download env). |
| data_conversion_single | **not ported** | — | Single-end branch. Upstream routes per sample by the metadata `paired` column; oxo-flow cannot branch per sample. The port ships the paired-end path (upstream example dataset D21122 is all-PAIRED). |
| merge_R1_data | `merge_R1_data` | coreutils `cat` (via python script) | Input function `get_merged_input_data_R1` ported to `scripts/merge_reads.py --read 1`; identical `cat … > 00_raw_data/{sample}_R1.fq`. `limit_merge` cap preserved: 1 unit per rule + `[resource_groups] limit_merge = { max = 2 }` (upstream run.py `--resources limit_merge=2`). |
| merge_R2_data | `merge_R2_data` | coreutils `cat` (via python script) | Same as above, `--read 2`. |
| merge_data | **not ported** | — | Single-end branch (see data_conversion_single). |
| data_clean_pair | `data_clean_pair` | fastp 1.3.6 | Command byte-identical (`-w`, `-i/-I`, `-o/-O`, `-j log/{sample}.json`, `-h log/{sample}.html`, `&> log/{sample}_fastp.log`). Upstream does not pin fastp; resolved from bioconda on 2026-08-15. Threads 8 (upstream `fastp_threads` baked into `[rules.resources]`). |
| data_clean_single | **not ported** | — | Single-end branch. |
| align_and_count | `align_and_count` | star 2.7.1a | Command byte-identical (flags, `--outFileNamePrefix`, `--limitBAMsortRAM $((10000 * 1000000))`, `--quantMode GeneCounts`, `--outTmpKeep None`, `mv …_Log.final.out` to log). Threads 20 (upstream `star_threads` baked in). The attempt-based memory escalation lambda (`10000` first attempt, `60000*(attempt-1)` after) is not expressible — the port pins the first-attempt value (`resources.memory = "10G"`). |
| build_bam_index | `build_bam_index` | samtools 1.24 | `samtools index -@ 4 {input}` identical. Upstream does not pin samtools; resolved from bioconda on 2026-08-15. |
| bamtobw | `bamtobw` | deeptools 3.5.6 | Command byte-identical (`-p 10 --binSize 50 --effectiveGenomeSize 2913022398 --normalizeUsing BPM -b … -o 04_bigwig/{sample}.bw`). Upstream does not pin deeptools; resolved from bioconda on 2026-08-15. |
| combine_count | `combine_count` | python 3.11 + pandas 3.0.5 | run: block ported verbatim to `scripts/combine_count.py` (same merge order and column renaming); per-sample counts gathered via `expand_inputs` over the sample list. Adds a fail-fast check that `[config] db_id` matches the metadata file name (upstream derives DB_ID at load time). Upstream runs in the snakemake base env (`snakemake==8.16 pandas`); snakemake itself is not needed — oxo-flow is the orchestrator. |
| DGE_analysis | `DGE_analysis` | R 4.3.2, DESeq2 1.42.0, ashr 2.2.63, data.table 1.18.4 | `scripts/DESeq2_diff.R` ported verbatim (design `~group`, contrast `treat`/`control`, `lfcShrink(type="ashr")`, saves exprSet + metadata + diffResults to the .Rds path). Env pins from the upstream Dockerfile (r432 env); r-data.table resolved from conda-forge on 2026-08-15; python added for the on_success mail hook. |
| onsuccess | `on_success` (DGE_analysis) | shell + smtplib | Upstream workflow-level `onsuccess` becomes the final rule's hook: `rm -rf 02_read_align` + conditional email via `scripts/send_mail.py` (port of `send_mail()`; the upstream `client.quit()` NameError on SMTP connection failure is fixed and notification failures exit 0 so they never fail a finished workflow). `mail` defaults to false, as upstream. |
| onerror | **not ported** | — | oxo-flow has per-rule `on_failure` hooks, no workflow-level error hook. |
| Snakefile_ENCODE | **not ported** | — | Alternate entry point (ENCODE metadata columns, `DESeq2_diff_encode.R`). |
| run.py | **not ported** | — | Batch runner over multiple metadata files (metadata validation, bark/feishu notifications, `--restart-times 3`). Its `limit_dump`/`limit_merge` caps are ported as described above; for re-runs use `oxo-flow run --resume-failed`. |
| slurm/config.yaml | **not ported** | — | Cluster profile; oxo-flow's `[cluster]` section covers this. |
| scripts/update_json.py | **not ported** | — | `file_dict.json` tracker used by external orchestration. |
| pigz_threads config key | dropped | — | Merge rules use plain `cat`; the pigz pipe is commented out upstream. |

## Source

Ported from **[xuzhougeng/auto_sra_rnaseq_pipeline](https://github.com/xuzhougeng/auto_sra_rnaseq_pipeline)**, main HEAD commit `923b9e98669a02d7b63ac8743e7ed960f3d0a86e` (2025-09-19). The upstream repository declares no license (no LICENSE file). Created 2026-08-15; this workflow **may lag upstream releases**. Attribution in `NOTICE.md`.

If this workflow helps your research, please cite the upstream project's
reference: Guo S, Xu Z, Dong X, et al. GPSAdb: a comprehensive web resource
for interactive exploration of genetic perturbation RNA-seq datasets.
*Nucleic Acids Research*, 51(D1):D964–D968, 2023. https://doi.org/10.1093/nar/gkac1066

## Test

```bash
bash test/run.sh   # validate + lint + dry-run, exits 0
```

## License

Apache-2.0. Copyright (c) 2026 oxo-flow-community.

## Community

https://oxo-flow-community.github.io/
