import inspect
import unittest

from zanim.render.video import _x264_encoder_args, render_video


class VideoEncoderTests(unittest.TestCase):
    def test_x264_encoder_args(self):
        args = _x264_encoder_args(crf=18, preset="veryfast", encoder_threads=4)
        self.assertEqual(
            args,
            [
                "-c:v", "libx264",
                "-crf", "18",
                "-preset", "veryfast",
                "-threads", "4",
            ],
        )

    def test_fast_portable_defaults(self):
        params = inspect.signature(render_video).parameters
        self.assertEqual(params["preset"].default, "veryfast")
        self.assertEqual(params["encoder_threads"].default, 4)
        self.assertNotIn("video_encoder", params)


if __name__ == "__main__":
    unittest.main()
