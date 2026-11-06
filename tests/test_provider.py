"""Mocked HTTP tests only: these never contact Gemini."""
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from app.provider import GeminiProvider, PredictionError, parse_response


def response_payload(text="Test-only provider output"):
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]}


class GeminiTests(unittest.TestCase):
    def setUp(self):
        self.provider = GeminiProvider("test-only-key", model="test-model", timeout=7)
        self.clinical = dict(glucose=155.5, haemoglobin=12.5, cholesterol=265,
                             full_name="Must not be sent", date_of_birth="1990-01-01",
                             email="private@example.com")

    def mock_response(self, opener, payload):
        response = Mock()
        response.read.return_value = payload
        opener.return_value.__enter__.return_value = response

    @patch("app.provider.urlopen")
    def test_request_and_response(self, opener):
        self.mock_response(opener, json.dumps(response_payload()).encode())
        self.assertEqual(self.provider(self.clinical), "Test-only provider output")
        request = opener.call_args.args[0]
        self.assertEqual(opener.call_args.kwargs, {"timeout": 7.0})
        self.assertTrue(request.full_url.endswith("/test-model:generateContent"))
        self.assertNotIn("test-only-key", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "test-only-key")
        self.assertEqual(request.method, "POST")
        body = json.loads(request.data)
        labs = json.loads(body["contents"][0]["parts"][0]["text"])
        self.assertEqual(set(labs), {"glucose", "haemoglobin", "cholesterol", "units"})
        self.assertEqual(labs["glucose"], 155.5)
        self.assertEqual(labs["units"]["glucose"], "mg/dL")
        self.assertNotIn("private@example.com", request.data.decode())
        self.assertIn("treatment advice", body["systemInstruction"]["parts"][0]["text"])

    @patch("app.provider.urlopen")
    def test_timeout_and_provider_errors(self, opener):
        failures = [TimeoutError("secret"), URLError("secret")]
        failures += [HTTPError("https://example.invalid", code, "secret", {}, None)
                     for code in [400, 401, 403, 404, 429, 500, 503]]
        for error in failures:
            with self.subTest(error=type(error), code=getattr(error, "code", None)):
                opener.side_effect = error
                with self.assertRaises(PredictionError) as caught:
                    self.provider(self.clinical)
                self.assertNotIn("secret", str(caught.exception))
                self.assertIn("retry", str(caught.exception).lower())

    @patch("app.provider.urlopen")
    def test_malformed_http_body(self, opener):
        for raw in [b"", b"not json", b"\xff", b"x" * 1_000_001]:
            self.mock_response(opener, raw)
            with self.assertRaises(PredictionError):
                self.provider(self.clinical)

    def test_response_validation(self):
        malformed = [None, [], {}, {"error": {}}, {"candidates": []},
                     {"candidates": [None]}, response_payload(""), response_payload("  "),
                     response_payload("x" * 5001), response_payload(23)]
        for reason in ["SAFETY", "MAX_TOKENS", "RECITATION"]:
            payload = response_payload()
            payload["candidates"][0]["finishReason"] = reason
            malformed.append(payload)
        for parts in [[], {}, [None], [{"functionCall": {}}], [{"thought": True, "text": "hidden"}]]:
            payload = response_payload()
            payload["candidates"][0]["content"]["parts"] = parts
            malformed.append(payload)
        payload = response_payload()
        payload["promptFeedback"] = {"blockReason": "SAFETY"}
        malformed.append(payload)
        for payload in malformed:
            with self.subTest(payload=str(payload)[:80]):
                with self.assertRaises(PredictionError):
                    parse_response(payload)
        payload = response_payload()
        payload["candidates"][0]["content"]["parts"] = [
            {"thought": True, "text": "hidden reasoning"}, {"text": "Final "}, {"text": "review"}]
        self.assertEqual(parse_response(payload), "Final review")

    @patch("app.provider.urlopen")
    def test_configuration_errors_do_not_call_network(self, opener):
        for key, model, timeout in [("", "model", 7), ("key", "../bad", 7),
                                    ("key", "model", "nan"), ("key", "model", 0),
                                    ("key", "model", "oops"), ("key", "model", 121)]:
            with self.assertRaises(PredictionError):
                GeminiProvider(key, model, timeout)(self.clinical)
        opener.assert_not_called()
