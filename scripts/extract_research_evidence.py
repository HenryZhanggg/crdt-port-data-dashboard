"""Export verified aggregate research evidence; never include raw predictions."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args()
    source = args.workbook
    output = Path(__file__).resolve().parents[1] / "data"
    summary = pd.read_excel(source, sheet_name="Summary_By_Group")
    raw = pd.read_excel(source, sheet_name="PerFold_Metrics")
    columns = ["feature_group", "fold_id", "val_cluster_id", "test_cluster_id", "n_features", "test_ap",
        "sparse_f2", "event_recall", "false_alarms_per_day"]
    folds = raw[columns]
    for _, row in summary.iterrows():
        selected = folds[folds["feature_group"].eq(row["feature_group"])]
        for metric, field in [("test_ap", "test_ap_mean"), ("sparse_f2", "sparse_f2_mean"), ("event_recall", "event_recall_mean")]:
            assert abs(selected[metric].mean() - row[field]) < 1e-10, field
    summary.to_csv(output / "research_signature_summary.csv", index=False)
    folds.to_csv(output / "research_signature_folds.csv", index=False)
    manifest = {"source_workbook": source.name, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "sheets": ["Summary_By_Group", "PerFold_Metrics"], "study": "Liverpool 12-hour warning-aligned sparse learning",
        "validation": "Four incident-cluster folds; validation-selected alert threshold", "independent_clusters": int(folds["test_cluster_id"].nunique()),
        "model": "FinalSignature-SparseLogistic", "spread": "Sample standard deviation across folds, not a confidence interval",
        "false_alarm_unit": "False-positive windows per represented day, not alert episodes per day",
        "scope": "Archived offline experiments, not predictions from the current dashboard gauges"}
    (output / "research_provenance.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"groups": len(summary), "fold_records": len(folds), "source_sha256": manifest["source_sha256"]}))


if __name__ == "__main__":
    main()
