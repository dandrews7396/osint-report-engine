import unittest
from unittest.mock import patch

from utils.helpers import process_base64_images, sanitize_rich_html


class RichHtmlSanitizationTests(unittest.TestCase):
    def test_removes_executable_markup(self):
        payload = '''
            <img src="data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
                 onload="window.stolen=document.cookie">
            <svg onload="alert(1)"><circle></circle></svg>
            <script>alert(2)</script>
            <a href="javascript:alert(3)" onclick="alert(4)">click</a>
        '''

        cleaned = sanitize_rich_html(payload)

        self.assertNotIn('onload', cleaned)
        self.assertNotIn('onclick', cleaned)
        self.assertNotIn('<svg', cleaned)
        self.assertNotIn('<script', cleaned)
        self.assertNotIn('javascript:', cleaned)
        self.assertIn('data:image/gif;base64,', cleaned)
        self.assertIn('>click</a>', cleaned)

    def test_preserves_supported_rich_text(self):
        value = '''
            <p><strong>Step 1</strong></p>
            <ol start="2"><li>Open <a href="https://example.test">the page</a></li></ol>
            <table><tbody><tr><td colspan="2">Evidence</td></tr></tbody></table>
        '''

        cleaned = sanitize_rich_html(value)

        self.assertIn('<strong>Step 1</strong>', cleaned)
        self.assertIn('<ol start="2">', cleaned)
        self.assertIn('href="https://example.test"', cleaned)
        self.assertIn('rel="noopener noreferrer"', cleaned)
        self.assertIn('colspan="2"', cleaned)

    def test_persists_guidance_images_as_case_assets(self):
        guidance = '<p><img src="data:image/png;base64,cGl4ZWw="></p>'

        with patch("utils.helpers.os.makedirs"), patch(
            "utils.helpers.open", unittest.mock.mock_open()
        ), patch("utils.helpers.os.path.abspath", return_value="/case/assets/pixel.png"):
            stored = process_base64_images(
                sanitize_rich_html(guidance),
                client_id=1,
                project_id=2,
            )

        self.assertEqual(stored, '<p><img src="file:///case/assets/pixel.png"></p>')


if __name__ == '__main__':
    unittest.main()
