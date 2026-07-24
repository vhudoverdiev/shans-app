import hashlib
import json
import struct
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "base.html"
MANIFEST = PROJECT_ROOT / "app" / "static" / "site.webmanifest"
LOGO = PROJECT_ROOT / "app" / "static" / "logo.png"


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
            'rel="apple-touch-icon"',
            template,
        )
        self.assertIn("filename='logo.png'", template)
        self.assertIn("filename='site.webmanifest'", template)

    def test_manifest_describes_standalone_shans_app(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "Шанс")
        self.assertEqual(manifest["short_name"], "Шанс")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
        self.assertIn(
            {
                "src": "/static/logo.png",
                "sizes": "1254x1254",
                "type": "image/png",
                "purpose": "any",
            },
            manifest["icons"],
        )

    def test_logo_asset_matches_the_supplied_source_image(self):
        logo = LOGO.read_bytes()

        self.assertEqual(logo[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", logo[16:24]), (1254, 1254))
        self.assertEqual(
            hashlib.sha256(logo).hexdigest(),
            "4ae379a1088102a02eafd5b28ad21392eab9d8a19d3f50dce22649777c1c3de8",
        )


if __name__ == "__main__":
    unittest.main()
