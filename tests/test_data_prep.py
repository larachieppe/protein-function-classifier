"""Fast, dependency-light unit tests for the data-preparation helpers.

These cover pure-Python logic (sequence truncation, label maps, row cleaning,
and multi-source label parsing) so they run in a second or two without any
model download or GPU. They double as the smoke test that the SessionStart
hook installed the environment correctly.
"""
import numpy as np
import pandas as pd

from data import _dual_end_truncate, build_label_maps
from prepare_data import SOURCES, _clean


class TestDualEndTruncate:
    def test_short_sequence_is_unchanged(self):
        seq = "MKV"
        assert _dual_end_truncate(seq, max_residues=10) == seq

    def test_sequence_at_limit_is_unchanged(self):
        seq = "A" * 10
        assert _dual_end_truncate(seq, max_residues=10) == seq

    def test_long_sequence_keeps_both_termini_and_exact_length(self):
        # Distinct N- and C-terminal blocks so we can assert both survive.
        seq = "N" * 40 + "X" * 20 + "C" * 40  # length 100
        out = _dual_end_truncate(seq, max_residues=10)
        assert len(out) == 10
        assert out.startswith("N")  # N-terminal signal peptide retained
        assert out.endswith("C")    # C-terminal sorting signal retained
        assert "X" not in out       # the discarded middle is what got dropped

    def test_odd_max_residues_split(self):
        seq = "N" * 50 + "C" * 50
        out = _dual_end_truncate(seq, max_residues=11)
        # half = 11 // 2 = 5 from the head, 6 from the tail
        assert out == seq[:5] + seq[-6:]
        assert len(out) == 11


class TestBuildLabelMaps:
    def test_maps_are_sorted_and_inverse(self):
        df = pd.DataFrame({"label": ["Nucleus", "Cytoplasm", "Nucleus", "Membrane"]})
        label2id, id2label = build_label_maps(df)

        assert label2id == {"Cytoplasm": 0, "Membrane": 1, "Nucleus": 2}
        # id2label is the exact inverse of label2id
        assert id2label == {i: label for label, i in label2id.items()}
        # ids are contiguous 0..N-1
        assert sorted(id2label) == list(range(len(label2id)))


class TestClean:
    def test_drops_nan_empty_and_duplicate_rows(self):
        df = pd.DataFrame(
            {
                "sequence": ["MKV", "MKV", "MAAA", "", "MPLL", np.nan],
                "label": ["Nucleus", "Nucleus", "Membrane", "Cytoplasm", np.nan, "Nucleus"],
            }
        )
        cleaned, dropped = _clean(df)

        # Kept: the first "MKV" and "MAAA". Dropped: the duplicate "MKV",
        # the empty sequence, the NaN-label row, and the NaN-sequence row.
        assert sorted(cleaned["sequence"].tolist()) == ["MAAA", "MKV"]
        assert dropped == 4
        assert len(cleaned) + dropped == len(df)


class TestMultiSourceLabelParsing:
    def test_deeploc_multi_takes_compartment_before_comma(self):
        label_fn = SOURCES["deeploc-multi"]["label_fn"]
        assert label_fn("Cell.membrane,M") == "Cell.membrane"
        assert label_fn("Nucleus,S") == "Nucleus"

    def test_deeploc_default_source_columns_present(self):
        cfg = SOURCES["deeploc"]
        assert cfg["seq"] and cfg["label"]
        assert "train" in cfg["splits"] and "test" in cfg["splits"]
