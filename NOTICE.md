oxo-flow-auto-sra-rnaseq-pipeline
Copyright (c) 2026 oxo-flow-community

This pipeline is a port of xuzhougeng/auto_sra_rnaseq_pipeline
(https://github.com/xuzhougeng/auto_sra_rnaseq_pipeline), main HEAD commit
923b9e98669a02d7b63ac8743e7ed960f3d0a86e (2025-09-19), authored by
Zhougeng Xu (xuzhougeng).

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

---------------------------------------------------------------------
Copied or derived upstream scripts

The following files contain code copied verbatim or closely derived from
the upstream repository (authored by Zhougeng Xu, xuzhougeng):

- scripts/update_json.py — copied byte-identical from upstream
  scripts/update_json.py (external-orchestration file_dict.json tracker).
- scripts/DESeq2_diff_encode.R — copied byte-identical from upstream
  scripts/DESeq2_diff_encode.R (ENCODE differential analysis).
- scripts/notify.py — derived from upstream scripts/utilize.py:
  feishu_notification is verbatim; bark_notification is a corrected
  implementation of the upstream function (upstream assigns base_url and
  never sends — a silent no-op).
- scripts/run_batch.py — derived from upstream run.py: validate_metadata_file
  and check_sra_files are verbatim; the runner drives `oxo-flow run`
  instead of `snakemake`.
- scripts/clean_encode.py — derived from the upstream Snakefile_ENCODE
  data_clean_pair rule and its get_raw_data input function (runs the
  byte-identical fastp command per sample).
- scripts/merge_reads.py, scripts/dump_sra.py, scripts/get_sra.py,
  scripts/combine_count.py — ports of the corresponding upstream rules'
  input functions / run: blocks (identical command and merge logic).
- scripts/send_mail.py, scripts/DESeq2_diff.R — pre-existing ports of the
  upstream send_mail() and DGE_analysis.

---------------------------------------------------------------------
Upstream license

The upstream repository declares no license: it ships no LICENSE file and
GitHub reports no license at the ported commit
(923b9e98669a02d7b63ac8743e7ed960f3d0a86e). There is therefore no
LICENSE.upstream file in this repository. All upstream-derived content
(workflow structure, command logic, and the ported scripts/rules) is
attributed above; if you reuse this port, be aware that the upstream code
has no stated redistribution terms and treat it accordingly. The port
itself is licensed Apache-2.0.
---------------------------------------------------------------------
