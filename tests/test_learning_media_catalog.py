import unittest
from pathlib import Path
from app.ai_course_content import AI_LESSONS
from app.podcast_content import PODCASTS, PODCAST_CATEGORIES

ROOT = Path(__file__).resolve().parents[1]


class LearningMediaCatalogTests(unittest.TestCase):
    def test_all_requested_recordings_have_audio_and_long_sources_are_split(self):
        counts = {}
        unique = set()
        for podcast in PODCASTS:
            key = (podcast['category'], podcast['slug'])
            self.assertNotIn(key, unique)
            unique.add(key)
            self.assertIn(podcast['category'], PODCAST_CATEGORIES)
            self.assertTrue(podcast['description'])
            self.assertGreater(podcast['duration_seconds'], 0)
            self.assertGreater(podcast['source_end'], podcast['source_start'])
            counts[podcast['source_id']] = counts.get(podcast['source_id'], 0) + 1
            root = (ROOT / 'app/podcast_media').resolve()
            audio = (root / podcast['filename']).resolve()
            self.assertTrue(audio.is_relative_to(root))
            self.assertTrue(audio.is_file(), audio)
            self.assertGreater(audio.stat().st_size, 10000)
            with audio.open('rb') as source:
                signature = source.read(3)
            self.assertTrue(signature == b'ID3' or signature[0] == 255, audio)
        required = {'1RuWJjzT9Fo', 'eBjsDWm4C3g', 'sMgo4sIJpik', 'X9BvjDnDKpU',
                    '_dVF0SXgs0w', 'fvbl1y2C4bg', 'ro74ZX-bs1I', 'IJcm2QwQHzM', 'AqDXJ3YZF3M'}
        self.assertTrue(required <= set(counts))
        for source_id in ('_dVF0SXgs0w', 'AqDXJ3YZF3M'):
            self.assertGreaterEqual(counts[source_id], 2)
            parts = sorted((p for p in PODCASTS if p['source_id'] == source_id), key=lambda p: p['part'])
            self.assertEqual(parts[0]['source_start'], 0)
            for previous, current in zip(parts, parts[1:]):
                self.assertEqual(previous['source_end'], current['source_start'])
                self.assertEqual(previous['part'] + 1, current['part'])

    def test_every_ai_lesson_has_a_compatible_local_video(self):
        for lesson in AI_LESSONS:
            video = ROOT / 'app/static' / lesson['video_file']
            self.assertTrue(video.is_file(), video)
            self.assertGreater(video.stat().st_size, 10000)
            poster = ROOT / 'app/static' / lesson['poster_file']
            self.assertTrue(poster.is_file(), poster)
            with poster.open('rb') as image:
                self.assertEqual(image.read(3), b'\xff\xd8\xff')
            with video.open('rb') as source:
                header = source.read(1024 * 1024)
            self.assertIn(b'ftyp', header, video)
            self.assertIn(b'avc1', header, video)
            self.assertIn(b'mp4a', header, video)
