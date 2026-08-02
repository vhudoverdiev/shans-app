import hashlib
import json
import struct
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "base.html"
MANIFEST = PROJECT_ROOT / "app" / "static" / "site.webmanifest"
LOGO = PROJECT_ROOT / "app" / "static" / "logo.png"
FAVICON = PROJECT_ROOT / "app" / "static" / "favicon.png"
APPLE_TOUCH_ICON = PROJECT_ROOT / "app" / "static" / "apple-touch-icon.png"
PWA_ICON = PROJECT_ROOT / "app" / "static" / "pwa-icon-512.png"
IPHONE_16_PRO_MAX_STARTUP = PROJECT_ROOT / "app" / "static" / "ios-startup-iphone-16-pro-max.png"


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
            '<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">',
            template,
        )
        self.assertIn(
            'rel="apple-touch-icon" sizes="180x180"',
            template,
        )
        self.assertIn("filename='apple-touch-icon.png', v=static_asset_version", template)
        self.assertNotIn('rel="apple-touch-icon" href="{{ url_for(\'static\', filename=\'logo.png\'', template)
        self.assertIn('rel="apple-touch-startup-image"', template)
        self.assertIn("device-width: 440px", template)
        self.assertIn("device-height: 956px", template)
        self.assertIn("-webkit-device-pixel-ratio: 3", template)
        self.assertIn("filename='ios-startup-iphone-16-pro-max.png', v=static_asset_version", template)
        self.assertIn("filename='site.webmanifest'", template)

    def test_manifest_describes_standalone_shans_app(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "Шанс")
        self.assertEqual(manifest["short_name"], "Шанс")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
        self.assertIn(
            {
                "src": "/static/pwa-icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            manifest["icons"],
        )

    def test_home_screen_install_metadata_never_uses_old_logo_icon(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        install_icon_sources = [
            icon["src"]
            for icon in manifest["icons"]
            if icon.get("purpose") in {None, "any", "any maskable", "maskable any"}
        ]

        self.assertNotIn("/static/logo.png", install_icon_sources)
        self.assertIn("/static/pwa-icon-512.png", install_icon_sources)
        self.assertIn("filename='apple-touch-icon.png', v=static_asset_version", template)
        self.assertIn("filename='ios-startup-iphone-16-pro-max.png', v=static_asset_version", template)
        self.assertNotIn("filename='logo.png', v=static_asset_version", template.split('rel="manifest"', 1)[0])

    def test_browser_favicon_is_a_rounded_square(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        favicon = FAVICON.read_bytes()

        self.assertIn('rel="icon" type="image/png"', template)
        self.assertIn(
            "filename='favicon.png', v=static_asset_version",
            template,
        )
        self.assertEqual(favicon[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", favicon[16:24]), (512, 512))
        self.assertEqual(favicon[25], 6)
        self.assertEqual(
            hashlib.sha256(favicon).hexdigest(),
            "b9e52a3974c9797f87040414b7a286b9b60dda9e5d28d7b56f8e1139463edca1",
        )

    def test_logo_asset_matches_the_supplied_source_image(self):
        logo = LOGO.read_bytes()

        self.assertEqual(logo[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", logo[16:24]), (1254, 1254))
        self.assertEqual(
            hashlib.sha256(logo).hexdigest(),
            "4ae379a1088102a02eafd5b28ad21392eab9d8a19d3f50dce22649777c1c3de8",
        )

    def test_ios_home_screen_assets_have_expected_dimensions(self):
        apple_touch_icon = APPLE_TOUCH_ICON.read_bytes()
        pwa_icon = PWA_ICON.read_bytes()
        startup_image = IPHONE_16_PRO_MAX_STARTUP.read_bytes()

        self.assertEqual(apple_touch_icon[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", apple_touch_icon[16:24]), (180, 180))
        self.assertEqual(pwa_icon[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", pwa_icon[16:24]), (512, 512))
        self.assertEqual(startup_image[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", startup_image[16:24]), (1320, 2868))


if __name__ == "__main__":
    unittest.main()
