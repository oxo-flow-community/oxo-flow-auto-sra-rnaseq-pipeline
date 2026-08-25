#!/usr/bin/env bash
# Acceptance test for the oxo-flow-auto-sra-rnaseq-pipeline port.
# Usage: bash test/run.sh            (uses ./main.oxoflow and ./main_encode.oxoflow)
# Local: OXO=/Users/wsx/Documents/GitHub/oxo-community/bin/oxo-flow bash test/run.sh
set -euo pipefail
cd "$(dirname "$0")/.."
OXO=${OXO:-oxo-flow}

check_wf() {
    local wf=$1
    echo "==> validate $wf"
    "$OXO" validate "$wf"

    echo "==> lint $wf (warnings are acceptable, errors are not)"
    "$OXO" lint "$wf"

    echo "==> dry-run $wf with default config"
    "$OXO" dry-run "$wf" > /tmp/oxo-dryrun-$$.txt 2>&1
    grep -q "would execute" /tmp/oxo-dryrun-$$.txt

    echo "==> debug $wf: expanded commands contain no literal {wildcards}"
    "$OXO" debug "$wf" | grep -q '{sample}' && { echo "unexpanded wildcards in debug output"; exit 1; } || true
    "$OXO" debug "$wf" | grep -q '{config\.' && { echo "unexpanded config placeholders in debug output"; exit 1; } || true
}

check_wf main.oxoflow
check_wf main_encode.oxoflow

echo "==> slurm profile resolves"
"$OXO" dry-run main.oxoflow --profile slurm > /tmp/oxo-dryrun-$$.txt 2>&1
grep -q "Applied config values from profile 'slurm'" /tmp/oxo-dryrun-$$.txt

echo "PASS"
