import copy
from datetime import date
from hashlib import sha256
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class PublicMediaTests(unittest.TestCase):
    def app(self, selected='Photos'):
        app = AppTest.from_string('from public_media import render_public_media\nrender_public_media()', default_timeout=30)
        app.session_state['public_media_tab'] = selected
        with patch('requests.sessions.Session.request', side_effect=AssertionError('Media render must not request external data')):
            app.run()
        self.assertFalse(app.exception)
        return app

    def test_manifest_has_local_licensed_liverpool_photos_and_verified_film(self):
        from public_media import _load_manifest
        media = _load_manifest()
        self.assertEqual(len(media['photos']), 2)
        for photo in media['photos']:
            self.assertIn('Seaforth', photo['location'])
            self.assertIn('Liverpool', photo['location'])
            self.assertEqual(photo['license'], 'CC BY-SA 4.0')
            self.assertEqual(photo['license_url'], 'https://creativecommons.org/licenses/by-sa/4.0/')
            self.assertEqual(photo['derivative_license'], 'CC BY-SA 4.0')
            self.assertTrue(photo['author'])
            self.assertTrue(photo['attribution'])
            self.assertTrue(photo['source_page'].startswith('https://commons.wikimedia.org/wiki/File:'))
            self.assertTrue(photo['original_url'].startswith('https://upload.wikimedia.org/wikipedia/commons/'))
            self.assertTrue(photo['download_url'].startswith('https://thumb.wikimedia.org/wikipedia/commons/'))
            date.fromisoformat(photo['captured_at'])
            path = (ROOT / photo['local_path']).resolve()
            self.assertTrue(path.is_relative_to(ROOT / 'assets' / 'public_media'))
            self.assertTrue(path.is_file())
            self.assertLess(path.stat().st_size, 500_000)
            self.assertEqual(sha256(path.read_bytes()).hexdigest(), photo['sha256'])
            self.assertEqual(photo['width'], 1280)
            self.assertIn('colours unchanged', photo['modifications'])
        self.assertTrue(media['video']['embeddable_verified'])
        self.assertFalse(media['video']['is_live'])
        self.assertEqual(media['video']['publisher'], 'Peel Ports')

    def test_default_shows_dated_photos_without_requesting_the_video(self):
        app = self.app()
        self.assertEqual({tab.label for tab in app.tabs}, {'Photos', 'Video'})
        self.assertEqual(len(app.get('imgs')), 2)
        self.assertFalse(app.get('video'))
        captions = ' '.join(element.value for element in app.caption)
        self.assertIn('Historical photo', captions)
        self.assertIn('24 Nov 2022', captions)
        self.assertIn('20 Mar 2021', captions)
        self.assertIn('Niels Johannes', captions)
        self.assertIn('Phil Nash', captions)
        self.assertIn('https://creativecommons.org/licenses/by-sa/4.0/', captions)
        self.assertIn('https://commons.wikimedia.org/wiki/File:', captions)

    def test_selected_video_is_not_autoplayed_and_keeps_official_fallback(self):
        app = self.app('Video')
        self.assertEqual(len(app.get('video')), 1)
        video = app.get('video')[0].proto
        self.assertIn('UQjseoH2H2M', video.url)
        self.assertFalse(video.autoplay)
        self.assertTrue(any(element.url == 'https://www.peelports.com/port-locations/liverpool/' for element in app.get('link_button')))
        self.assertTrue(any('Peel Ports' in element.value and '2026' in element.value for element in app.caption))
        self.assertTrue(any('Copyright remains with publisher' in element.value for element in app.caption))

    def test_unverified_video_still_offers_the_official_source(self):
        from public_media import _load_manifest
        media = copy.deepcopy(_load_manifest())
        media['video'].update(embeddable_verified=False, published_at=None)
        with patch('public_media._load_manifest', return_value=media):
            app = self.app('Video')
        self.assertFalse(app.get('video'))
        self.assertTrue(any('Publication date not supplied' in element.value for element in app.caption))
        self.assertTrue(any(element.url == media['video']['source_page'] for element in app.get('link_button')))

    def test_credit_escapes_markup_and_withholds_unsafe_links(self):
        from public_media import _credit_html, _safe_url
        credit = _credit_html({'attribution':'<img src=x onerror=alert(1)>', 'source_page':'javascript:alert(1)',
            'license':'CC BY-SA 4.0', 'license_url':'https://creativecommons.org/licenses/by-sa/4.0/'})
        self.assertNotIn('<img', credit)
        self.assertIn('&lt;img', credit)
        self.assertNotIn('javascript:', credit)
        self.assertIn('https://creativecommons.org/licenses/by-sa/4.0/', credit)
        for url in ['https://[broken', 'http://commons.wikimedia.org/', 'https://user@commons.wikimedia.org/',
                    'https://commons.wikimedia.org.evil.example/', 'https://www.youtube.com:123/']:
            self.assertIsNone(_safe_url(url))


if __name__ == '__main__':
    unittest.main()
