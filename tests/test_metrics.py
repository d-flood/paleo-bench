import unittest

from paleo_bench.metrics import compute_metrics, normalize_for_comparison


class TestScoringRegularization(unittest.TestCase):
    def test_final_and_medial_sigma_score_the_same(self) -> None:
        self.assertEqual(compute_metrics("λογος", "λογοσ").cer, 0)
        self.assertEqual(compute_metrics("σωσον", "ςωςον").cer, 0)

    def test_lunate_sigma_scores_as_sigma(self) -> None:
        self.assertEqual(compute_metrics("εις λογος", "ειϲ λογοϲ").cer, 0)
        self.assertEqual(compute_metrics("σαρκα", "Ϲαρκα").cer, 0)

    def test_capitalization_is_ignored(self) -> None:
        self.assertEqual(compute_metrics("παυλος", "Παυλος").cer, 0)
        self.assertEqual(compute_metrics("παυλος", "ΠΑΥΛΟΣ").cer, 0)
        self.assertEqual(compute_metrics("παυλος", "ΠΑΥΛΟΣ").wer, 0)

    def test_greek_letter_variants_score_as_base_letters(self) -> None:
        self.assertEqual(compute_metrics("θεος βιβλος", "ϑεος ϐιϐλος").cer, 0)
        self.assertEqual(compute_metrics("κρφπε", "ϰϱϕϖϵ").cer, 0)

    def test_ligature_letters_expand(self) -> None:
        self.assertEqual(compute_metrics("εστιν", "εϛιν").cer, 0)
        self.assertEqual(compute_metrics("τουτο", "τȣτο").cer, 0)
        self.assertEqual(compute_metrics("και λογος", "ϗ λογος").cer, 0)

    def test_latin_and_cyrillic_lookalikes_inside_greek_words(self) -> None:
        self.assertEqual(compute_metrics("δικαιοσυνην", "δικαιосυνην").cer, 0)
        self.assertEqual(compute_metrics("ελληνι", "ελληvι").cer, 0)
        self.assertEqual(compute_metrics("Column 1", "Column 1").cer, 0)
        self.assertGreater(compute_metrics("Column 1", "Coluмn 1").cer, 0)

    def test_modifier_marks_are_ignored(self) -> None:
        self.assertEqual(compute_metrics("αλλ εν", "αλλ᾽ εν").cer, 0)
        self.assertEqual(compute_metrics("αβ", "αʹβ").cer, 0)

    def test_other_letters_still_count(self) -> None:
        scores = compute_metrics("λογος", "λογον")
        self.assertGreater(scores.cer, 0)
        self.assertEqual(scores.levenshtein_distance, 1)

    def test_normalized_text_keeps_case_and_final_sigma(self) -> None:
        self.assertEqual(normalize_for_comparison("Λόγος."), "Λογος")


if __name__ == "__main__":
    unittest.main()
