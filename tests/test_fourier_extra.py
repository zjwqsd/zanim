import math
import unittest

from zanim.extras.fourier import dft, dominant_terms, epicycle_chain


class FourierExtraTests(unittest.TestCase):
    def test_circle_has_one_dominant_positive_frequency(self):
        n = 64
        samples = tuple(
            complex(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i in range(n)
        )
        terms = dft(samples)
        dominant = dominant_terms(terms, 2)
        one = next(term for term in dominant if term.frequency == 1)
        self.assertAlmostEqual(one.radius, 1.0, places=10)

    def test_epicycle_chain_is_periodic(self):
        n = 32
        samples = tuple(
            complex(math.cos(2 * math.pi * i / n), 0.4 * math.sin(4 * math.pi * i / n))
            for i in range(n)
        )
        terms = dominant_terms(dft(samples), 8)
        self.assertEqual(epicycle_chain(terms, 0.0), epicycle_chain(terms, 1.0))


class FourierSvgInputTests(unittest.TestCase):
    def test_closed_svg_outline_reconstructs_with_full_dft(self):
        from pathlib import Path

        from zanim import load_svg
        from zanim.extras.fourier import contour_samples, select_closed_contour

        root = Path(__file__).resolve().parents[1]
        contour = select_closed_contour(load_svg(root / "tests/assets/fourier_heart.svg"))
        samples = contour_samples(contour, 64)
        terms = dft(samples)
        for i in (0, 7, 23, 63):
            reconstructed = epicycle_chain(terms, i / 64)[-1]
            self.assertAlmostEqual(reconstructed.real, samples[i].real, places=9)
            self.assertAlmostEqual(reconstructed.imag, samples[i].imag, places=9)
