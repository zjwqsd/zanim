import unittest

from zanim.render.video import _resolve_video_encoder, _video_encoder_args


class VideoEncoderTests(unittest.TestCase):
    def test_explicit_software_encoder_is_stable(self):
        self.assertEqual(_resolve_video_encoder("libx264"), "libx264")

    def test_invalid_encoder_is_rejected(self):
        with self.assertRaises(ValueError):
            _resolve_video_encoder("not-an-encoder")

    def test_nvenc_and_x264_use_backend_specific_quality_args(self):
        x264 = _video_encoder_args("libx264", crf=18, preset="veryfast", encoder_threads=4)
        nvenc = _video_encoder_args("h264_nvenc", crf=22, preset="veryfast", encoder_threads=4)
        self.assertIn("-crf", x264)
        self.assertIn("-threads", x264)
        self.assertIn("-cq", nvenc)
        self.assertIn("22", nvenc)
        self.assertNotIn("-threads", nvenc)


if __name__ == "__main__":
    unittest.main()
