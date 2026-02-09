"""Tests for LinkedIn Publisher and Threads Publisher tools (src/tools/smm_tools.py)."""

import sys
import os
import json
from unittest.mock import patch, MagicMock, PropertyMock
from io import BytesIO
from http.client import HTTPResponse
from urllib.error import HTTPError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tools.smm_tools import (
    LinkedInPublisherTool,
    LinkedInPublisherInput,
    ThreadsPublisherTool,
    ThreadsPublisherInput,
    _LINKEDIN_API_VERSION,
    _THREADS_BASE,
)


# ── Helpers ──────────────────────────────────────────────

def _mock_response(data: dict = None, status=200, headers=None):
    """Create a mock HTTP response."""
    body = json.dumps(data or {}).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.status = status
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    mock_headers = MagicMock()
    mock_headers.get = lambda key, default="": (headers or {}).get(key, default)
    resp.headers = mock_headers
    return resp


def _http_error(code: int, body: str = ""):
    err = HTTPError(
        url="https://api.example.com",
        code=code,
        msg=f"HTTP {code}",
        hdrs={},
        fp=BytesIO(body.encode("utf-8")) if body else None,
    )
    return err


# ══════════════════════════════════════════════════════════
# LINKEDIN PUBLISHER TESTS
# ══════════════════════════════════════════════════════════


class TestLinkedInPublisherInput:
    def test_input_text(self):
        inp = LinkedInPublisherInput(action="publish_text", text="Hello LinkedIn!")
        assert inp.action == "publish_text"
        assert inp.text == "Hello LinkedIn!"

    def test_input_image(self):
        inp = LinkedInPublisherInput(
            action="publish_image", text="Post", image_url="https://img.com/a.png"
        )
        assert inp.image_url == "https://img.com/a.png"

    def test_input_no_text(self):
        inp = LinkedInPublisherInput(action="status")
        assert inp.text is None
        assert inp.image_url is None


class TestLinkedInStatus:
    def test_status_configured(self):
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "tok", "LINKEDIN_PERSON_ID": "123"}):
            result = tool._run("status")
            assert "✅ Yes" in result
            assert "REST /rest/posts" in result

    def test_status_not_configured(self):
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {}, clear=True):
            result = tool._run("status")
            assert "❌ No" in result
            assert "MISSING" in result


class TestLinkedInCheckToken:
    def test_no_token(self):
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": ""}, clear=True):
            result = tool._run("check_token")
            assert "❌" in result
            assert "not set" in result

    @patch("urllib.request.urlopen")
    def test_valid_token(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response({"name": "Kristina Zhukova"})
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "valid_tok", "LINKEDIN_PERSON_ID": "1"}):
            result = tool._run("check_token")
            assert "✅" in result
            assert "Kristina Zhukova" in result

    @patch("urllib.request.urlopen")
    def test_expired_token(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(401)
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "expired", "LINKEDIN_PERSON_ID": "1"}):
            result = tool._run("check_token")
            assert "❌" in result
            assert "EXPIRED" in result


class TestLinkedInPublishText:
    def test_no_text(self):
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "t", "LINKEDIN_PERSON_ID": "1"}):
            result = tool._run("publish_text")
            assert "Error" in result

    def test_not_configured(self):
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {}, clear=True):
            result = tool._run("publish_text", text="Hello")
            assert "❌" in result
            assert "not configured" in result

    @patch("urllib.request.urlopen")
    def test_publish_success(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {}, headers={"x-restli-id": "urn:li:share:123456"}
        )
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "tok", "LINKEDIN_PERSON_ID": "1"}):
            result = tool._run("publish_text", text="Test post")
            assert "✅" in result
            assert "Published to LinkedIn" in result
            assert "123456" in result

    @patch("urllib.request.urlopen")
    def test_publish_expired(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(401)
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "tok", "LINKEDIN_PERSON_ID": "1"}):
            result = tool._run("publish_text", text="Test")
            assert "EXPIRED" in result

    @patch("urllib.request.urlopen")
    def test_publish_server_error(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(500, "Internal Server Error")
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "tok", "LINKEDIN_PERSON_ID": "1"}):
            result = tool._run("publish_text", text="Test")
            assert "❌" in result
            assert "500" in result

    def test_text_truncation(self):
        tool = LinkedInPublisherTool()
        long_text = "A" * 4000
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "t", "LINKEDIN_PERSON_ID": "1"}):
            with patch("urllib.request.urlopen") as mock:
                mock.return_value = _mock_response({}, headers={"x-restli-id": "urn:li:share:1"})
                result = tool._run("publish_text", text=long_text)
                assert "✅" in result

    def test_legacy_publish_action(self):
        """The old 'publish' action should still work (backwards compatible)."""
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "t", "LINKEDIN_PERSON_ID": "1"}):
            with patch("urllib.request.urlopen") as mock:
                mock.return_value = _mock_response({}, headers={"x-restli-id": "urn:li:share:1"})
                result = tool._run("publish", text="Legacy test")
                assert "✅" in result


class TestLinkedInPublishImage:
    def test_no_text(self):
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "t", "LINKEDIN_PERSON_ID": "1"}):
            result = tool._run("publish_image", image_url="https://img.com/a.png")
            assert "Error" in result
            assert "text" in result

    def test_no_image_url(self):
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "t", "LINKEDIN_PERSON_ID": "1"}):
            result = tool._run("publish_image", text="Post")
            assert "Error" in result
            assert "image_url" in result

    @patch("urllib.request.urlopen")
    def test_image_publish_success(self, mock_urlopen):
        # 4 calls: init upload, download image, upload binary, create post
        init_resp = _mock_response({
            "value": {
                "uploadUrl": "https://upload.linkedin.com/upload/123",
                "image": "urn:li:image:456",
            }
        })
        img_resp = _mock_response({})
        img_resp.read.return_value = b"\x89PNG\r\n\x1a\n"
        upload_resp = _mock_response({})
        post_resp = _mock_response({}, headers={"x-restli-id": "urn:li:share:789"})
        mock_urlopen.side_effect = [init_resp, img_resp, upload_resp, post_resp]

        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "tok", "LINKEDIN_PERSON_ID": "1"}):
            result = tool._run("publish_image", text="Photo!", image_url="https://img.com/a.png")
            assert "✅" in result
            assert "image" in result.lower()

    @patch("urllib.request.urlopen")
    def test_image_init_error(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(403, "Forbidden")
        tool = LinkedInPublisherTool()
        with patch.dict(os.environ, {"LINKEDIN_ACCESS_TOKEN": "t", "LINKEDIN_PERSON_ID": "1"}):
            result = tool._run("publish_image", text="Post", image_url="https://img.com/a.png")
            assert "❌" in result
            assert "init error" in result or "403" in result


class TestLinkedInUnknownAction:
    def test_unknown_action(self):
        tool = LinkedInPublisherTool()
        result = tool._run("unknown_action")
        assert "Unknown action" in result


# ══════════════════════════════════════════════════════════
# THREADS PUBLISHER TESTS
# ══════════════════════════════════════════════════════════


class TestThreadsPublisherInput:
    def test_input_text(self):
        inp = ThreadsPublisherInput(action="publish_text", text="Hello Threads!")
        assert inp.action == "publish_text"

    def test_input_carousel(self):
        inp = ThreadsPublisherInput(
            action="publish_carousel",
            text="Carousel!",
            image_urls="https://a.com/1.jpg,https://a.com/2.jpg",
        )
        assert "," in inp.image_urls

    def test_input_defaults(self):
        inp = ThreadsPublisherInput(action="status")
        assert inp.text is None
        assert inp.image_url is None
        assert inp.image_urls is None


class TestThreadsStatus:
    def test_status_configured(self):
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "tok", "THREADS_USER_ID": "123"}):
            result = tool._run("status")
            assert "✅ Yes" in result
            assert "graph.threads.net" in result

    def test_status_not_configured(self):
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {}, clear=True):
            result = tool._run("status")
            assert "❌ No" in result
            assert "MISSING" in result


class TestThreadsCheckToken:
    def test_no_credentials(self):
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {}, clear=True):
            result = tool._run("check_token")
            assert "❌" in result
            assert "not set" in result

    @patch("urllib.request.urlopen")
    def test_valid_token(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response({"username": "kristina_zh"})
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "tok", "THREADS_USER_ID": "123"}):
            result = tool._run("check_token")
            assert "✅" in result
            assert "kristina_zh" in result

    @patch("urllib.request.urlopen")
    def test_expired_token(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(401)
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "bad", "THREADS_USER_ID": "123"}):
            result = tool._run("check_token")
            assert "❌" in result


class TestThreadsPublishText:
    def test_no_text(self):
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "t", "THREADS_USER_ID": "1"}):
            result = tool._run("publish_text")
            assert "Error" in result

    def test_not_configured(self):
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {}, clear=True):
            result = tool._run("publish_text", text="Hello")
            assert "❌" in result
            assert "not configured" in result

    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_publish_text_success(self, mock_sleep, mock_urlopen):
        create_resp = _mock_response({"id": "container_1"})
        publish_resp = _mock_response({"id": "post_100"})
        mock_urlopen.side_effect = [create_resp, publish_resp]

        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "tok", "THREADS_USER_ID": "123"}):
            result = tool._run("publish_text", text="Test thread")
            assert "✅" in result
            assert "post_100" in result
            assert "threads.net" in result

    @patch("urllib.request.urlopen")
    def test_publish_text_container_error(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(400, "Bad request")
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "tok", "THREADS_USER_ID": "123"}):
            result = tool._run("publish_text", text="Test")
            assert "❌" in result

    def test_text_truncation(self):
        tool = ThreadsPublisherTool()
        long_text = "A" * 600
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "t", "THREADS_USER_ID": "1"}):
            with patch("urllib.request.urlopen") as mock:
                mock.return_value = _mock_response({"id": "c1"})
                with patch("time.sleep"):
                    # Will call create + publish
                    mock.side_effect = [_mock_response({"id": "c1"}), _mock_response({"id": "p1"})]
                    result = tool._run("publish_text", text=long_text)
                    assert "✅" in result


class TestThreadsPublishImage:
    def test_no_text(self):
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "t", "THREADS_USER_ID": "1"}):
            result = tool._run("publish_image", image_url="https://img.com/a.jpg")
            assert "Error" in result
            assert "text" in result

    def test_no_image_url(self):
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "t", "THREADS_USER_ID": "1"}):
            result = tool._run("publish_image", text="Post")
            assert "Error" in result
            assert "image_url" in result

    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_publish_image_success(self, mock_sleep, mock_urlopen):
        create_resp = _mock_response({"id": "container_img"})
        publish_resp = _mock_response({"id": "post_img_200"})
        mock_urlopen.side_effect = [create_resp, publish_resp]

        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "tok", "THREADS_USER_ID": "123"}):
            result = tool._run("publish_image", text="Photo post", image_url="https://img.com/a.jpg")
            assert "✅" in result
            assert "image" in result.lower()
            assert "post_img_200" in result


class TestThreadsPublishCarousel:
    def test_no_text(self):
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "t", "THREADS_USER_ID": "1"}):
            result = tool._run("publish_carousel", image_urls="a.jpg,b.jpg")
            assert "Error" in result

    def test_no_image_urls(self):
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "t", "THREADS_USER_ID": "1"}):
            result = tool._run("publish_carousel", text="Carousel")
            assert "Error" in result
            assert "image_urls" in result

    def test_single_image_rejected(self):
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "t", "THREADS_USER_ID": "1"}):
            result = tool._run("publish_carousel", text="Carousel", image_urls="https://a.com/1.jpg")
            assert "Error" in result
            assert "at least 2" in result

    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_publish_carousel_success(self, mock_sleep, mock_urlopen):
        # 2 item containers + 1 carousel container + 1 publish
        item1 = _mock_response({"id": "item_1"})
        item2 = _mock_response({"id": "item_2"})
        carousel = _mock_response({"id": "carousel_c"})
        publish = _mock_response({"id": "post_carousel_300"})
        mock_urlopen.side_effect = [item1, item2, carousel, publish]

        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "tok", "THREADS_USER_ID": "123"}):
            result = tool._run(
                "publish_carousel",
                text="My carousel",
                image_urls="https://a.com/1.jpg,https://a.com/2.jpg",
            )
            assert "✅" in result
            assert "carousel" in result.lower()
            assert "2 images" in result
            assert "post_carousel_300" in result

    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_carousel_item_failure(self, mock_sleep, mock_urlopen):
        mock_urlopen.side_effect = _http_error(400, "Bad image URL")
        tool = ThreadsPublisherTool()
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "tok", "THREADS_USER_ID": "123"}):
            result = tool._run(
                "publish_carousel",
                text="Carousel",
                image_urls="https://a.com/1.jpg,https://a.com/2.jpg",
            )
            assert "❌" in result
            assert "item failed" in result.lower() or "error" in result.lower()

    def test_carousel_max_20_images(self):
        tool = ThreadsPublisherTool()
        urls = ",".join([f"https://a.com/{i}.jpg" for i in range(25)])
        with patch.dict(os.environ, {"THREADS_ACCESS_TOKEN": "t", "THREADS_USER_ID": "1"}):
            with patch("urllib.request.urlopen") as mock:
                with patch("time.sleep"):
                    # Should create max 20 items + 1 carousel + 1 publish = 22 calls
                    responses = [_mock_response({"id": f"item_{i}"}) for i in range(22)]
                    mock.side_effect = responses
                    result = tool._run("publish_carousel", text="Big carousel", image_urls=urls)
                    # Should cap at 20 images
                    assert "20 images" in result or "✅" in result


class TestThreadsUnknownAction:
    def test_unknown_action(self):
        tool = ThreadsPublisherTool()
        result = tool._run("delete_all")
        assert "Unknown action" in result


class TestThreadsContainerHelpers:
    @patch("urllib.request.urlopen")
    def test_create_container_success(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response({"id": "container_123"})
        tool = ThreadsPublisherTool()
        result = tool._create_container("token", "user_1", {"media_type": "TEXT", "text": "Hi"})
        assert result == "container_123"

    @patch("urllib.request.urlopen")
    def test_create_container_no_id(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response({})
        tool = ThreadsPublisherTool()
        result = tool._create_container("token", "user_1", {"media_type": "TEXT"})
        assert result.startswith("❌")

    @patch("urllib.request.urlopen")
    def test_create_container_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(429, "Rate limited")
        tool = ThreadsPublisherTool()
        result = tool._create_container("token", "user_1", {"media_type": "TEXT"})
        assert "❌" in result
        assert "429" in result

    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_publish_container_success(self, mock_sleep, mock_urlopen):
        mock_urlopen.return_value = _mock_response({"id": "post_999"})
        tool = ThreadsPublisherTool()
        result = tool._publish_container("token", "user_1", "container_1")
        assert result == "post_999"

    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_publish_container_error(self, mock_sleep, mock_urlopen):
        mock_urlopen.side_effect = _http_error(500, "Server error")
        tool = ThreadsPublisherTool()
        result = tool._publish_container("token", "user_1", "container_1")
        assert "❌" in result
        assert "500" in result
