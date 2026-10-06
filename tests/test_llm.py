"""Tests for the Ollama client.

Nothing here contacts a real Ollama: the SDK import and the HTTP transport are
both patched. What is under test is the fallback contract, which is where the
real defects were -- a swallowed SDK error, and a mid-stream fallback that
would have shown the user the same answer twice.
"""
import logging
import sys
import types
import unittest
from unittest import mock

from lc.engine.llm import LLMClient, LLMUnavailableError

# The client logs a warning on every fallback; that is expected here and would
# otherwise bury the test report.
logging.getLogger("lc.engine.llm").setLevel(logging.CRITICAL)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def install_fake_ollama(_modules=None, *, chat_result=None, chat_error=None, stream=None):
    """Put a fake `ollama` module in sys.modules and return it.

    `llm.chat` does `import ollama` inside the function, so patching
    sys.modules is the only way to intercept it -- patching the module object
    in this file's namespace would have no effect.
    """
    mod = types.ModuleType("ollama")

    class Client:
        def __init__(self, host=None, **kwargs):
            self.host = host

        def chat(self, **kwargs):
            if kwargs.get("stream"):
                if chat_error is not None:
                    raise chat_error
                return stream if stream is not None else iter(())
            if chat_error is not None:
                raise chat_error
            return chat_result

    mod.Client = Client
    sys.modules["ollama"] = mod
    return mod


class TestChat(unittest.TestCase):
    def setUp(self):
        self._saved = sys.modules.get("ollama")
        self.addCleanup(self._restore)
        # No test in this suite may reach the real network. If the fake SDK is
        # not installed, block the HTTP fallback outright rather than letting
        # it resolve localhost and hang for seconds.
        self._http = mock.patch.object(LLMClient, "_http_chat", side_effect=AssertionError("unexpected HTTP"))
        self._http.start()
        self.addCleanup(self._http.stop)

    def _restore(self):
        if self._saved is None:
            sys.modules.pop("ollama", None)
        else:
            sys.modules["ollama"] = self._saved

    def test_sdk_success_returns_content(self):
        install_fake_ollama(chat_result={"message": {"content": "hello"}})
        client = LLMClient(host="http://x", model="m")
        self.assertEqual(client.chat([{"role": "user", "content": "hi"}]), "hello")

    def test_falls_back_to_http_on_sdk_failure(self):
        install_fake_ollama(chat_error=RuntimeError("sdk exploded"))
        client = LLMClient(host="http://x", model="m")

        with mock.patch.object(client, "_http_chat", return_value="from http") as http_chat:
            self.assertEqual(client.chat([{"role": "user", "content": "hi"}]), "from http")
        http_chat.assert_called_once()

    def test_error_reports_both_failures(self):
        # The fallback's own error is usually a bare 404; reporting only that
        # hid the real cause. Both must appear.
        install_fake_ollama(chat_error=RuntimeError("SDK_ROOT_CAUSE"))
        client = LLMClient(host="http://x", model="m")

        with mock.patch.object(client, "_http_chat", side_effect=RuntimeError("HTTP_ROOT_CAUSE")):
            with self.assertRaises(LLMUnavailableError) as cm:
                client.chat([{"role": "user", "content": "hi"}])

        message = str(cm.exception)
        self.assertIn("SDK_ROOT_CAUSE", message)
        self.assertIn("HTTP_ROOT_CAUSE", message)
        self.assertIn("http://x", message)

    def test_missing_sdk_uses_http_fallback(self):
        sys.modules.pop("ollama", None)
        client = LLMClient(host="http://x", model="m")
        with mock.patch.object(client, "_http_chat", return_value="no sdk needed"):
            self.assertEqual(client.chat([{"role": "user", "content": "hi"}]), "no sdk needed")

    def test_options_include_temperature_and_num_predict(self):
        seen = {}

        class Client:
            def __init__(self, host=None, **kwargs):
                pass

            def chat(self, **kwargs):
                seen.update(kwargs)
                return {"message": {"content": "ok"}}

        mod = types.ModuleType("ollama")
        mod.Client = Client
        sys.modules["ollama"] = mod

        client = LLMClient(host="http://x", model="m")
        client.chat([{"role": "user", "content": "hi"}], temperature=0.7, max_tokens=123)

        self.assertEqual(seen["options"]["temperature"], 0.7)
        self.assertEqual(seen["options"]["num_predict"], 123)


class TestChatStream(unittest.TestCase):
    def setUp(self):
        self._saved = sys.modules.get("ollama")
        self.addCleanup(self._restore)
        # Block the HTTP fallback so a test that forgets to patch it fails fast
        # instead of resolving localhost.
        self._http = mock.patch.object(LLMClient, "_http_chat", side_effect=AssertionError("unexpected HTTP"))
        self._http.start()
        self.addCleanup(self._http.stop)

    def _restore(self):
        if self._saved is None:
            sys.modules.pop("ollama", None)
        else:
            sys.modules["ollama"] = self._saved

    def _client(self, **kwargs):
        install_fake_ollama(sys.modules, **kwargs)
        return LLMClient(host="http://x", model="m")

    def test_yields_each_token(self):
        chunks = [
            {"message": {"content": "He"}},
            {"message": {"content": "llo"}},
        ]
        client = self._client(stream=iter(chunks))
        self.assertEqual(list(client.chat_stream([{"role": "user", "content": "hi"}])), ["He", "llo"])

    def test_fallback_before_first_token(self):
        # Nothing emitted yet, so switching transport cannot duplicate output.
        mod = install_fake_ollama(sys.modules, chat_error=RuntimeError("no stream"))
        client = LLMClient(host="http://x", model="m")
        with mock.patch.object(client, "_http_chat", return_value="whole answer"):
            self.assertEqual(list(client.chat_stream([])), ["whole answer"])

    def test_mid_stream_failure_raises_instead_of_falling_back(self):
        # The regression: emitting tokens then falling back would show the user
        # a partial answer and then the full one, twice.
        def exploding_stream():
            yield {"message": {"content": "partial"}}
            raise RuntimeError("stream died")

        client = self._client(stream=exploding_stream())
        with mock.patch.object(client, "_http_chat", return_value="SHOULD NOT APPEAR") as http_chat:
            with self.assertRaises(RuntimeError):
                list(client.chat_stream([]))
        http_chat.assert_not_called()

    def test_error_message_mentions_the_pull_command(self):
        # Force the SDK path to fail too, without importing the real ollama package
        # (which would attempt a real connection and take seconds).
        install_fake_ollama(chat_error=RuntimeError("sdk unavailable"))
        client = LLMClient(host="http://host", model="some:model")
        # Release the class-level block; this test is specifically about the
        # failure path of the HTTP fallback.
        self._http.stop()
        with mock.patch.object(client, "_http_chat", side_effect=RuntimeError("down")):
            with self.assertRaises(LLMUnavailableError) as cm:
                list(client.chat_stream([]))
        self.assertIn("ollama pull some:model", str(cm.exception))


class TestAvailability(unittest.TestCase):
    def test_is_available_true_on_200(self):
        with mock.patch("lc.engine.llm.httpx.get", return_value=FakeResponse({}, 200)):
            self.assertTrue(LLMClient().is_available())

    def test_is_available_false_on_error(self):
        with mock.patch("lc.engine.llm.httpx.get", side_effect=OSError("refused")):
            self.assertFalse(LLMClient().is_available())

    def test_list_models_reads_names(self):
        payload = {"models": [{"name": "a:1b"}, {"name": "b:2b"}]}
        with mock.patch("lc.engine.llm.httpx.get", return_value=FakeResponse(payload, 200)):
            self.assertEqual(LLMClient().list_models(), ["a:1b", "b:2b"])

    def test_list_models_empty_on_failure(self):
        with mock.patch("lc.engine.llm.httpx.get", side_effect=OSError("refused")):
            self.assertEqual(LLMClient().list_models(), [])


if __name__ == "__main__":
    unittest.main()