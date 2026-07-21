import hashlib
import json
import struct
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "base.html"
MANIFEST = PROJECT_ROOT / "app" / "static" / "site.webmanifest"
APPLE_TOUCH_ICON = PROJECT_ROOT / "app" / "static" / "apple-touch-icon.png"


class PwaInstallationTests(unittest.TestCase):
    def test_ios_home_screen_metadata_uses_shans_name_and_icon(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            '<meta name="apple-mobile-web-app-title" content="Шанс">',
            template,
        )
        self.assertIn(
            '<meta name="apple-mobile-web-app-capable" content="yes">',
            template,
        )
        self.assertIn(
            'rel="apple-touch-icon" sizes="180x180"',
            template,
        )
        self.assertIn("filename='apple-touch-icon.png'", template)
        self.assertIn("filename='site.webmanifest'", template)

    def test_manifest_describes_standalone_shans_app(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "Шанс")
        self.assertEqual(manifest["short_name"], "Шанс")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
        self.assertIn(
            {
                "src": "/static/apple-touch-icon.png",
                "sizes": "180x180",
                "type": "image/png",
                "purpose": "any",
            },
            manifest["icons"],
        )

    def test_apple_touch_icon_is_180_pixel_png(self):
        icon = APPLE_TOUCH_ICON.read_bytes()

        self.assertEqual(icon[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", icon[16:24]), (180, 180))
        self.assertEqual(
            hashlib.sha256(icon).hexdigest(),
            "b0e82a4374e9446255b03d3d93caaf17b092b1b886f26a170a346ce3215ab973",
        )


if __name__ == "__main__":
    unittest.main()
