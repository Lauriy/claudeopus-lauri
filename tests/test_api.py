"""Tests for molt.api."""

from molt.api import _check_get, _check_post, _find_verification


class TestCheckGet:
    def test_success(self) -> None:
        assert _check_get({"success": True, "data": "ok"}) is True

    def test_status_code_error(self) -> None:
        assert _check_get({"statusCode": 404, "error": "Not found"}) is False

    def test_error_field(self) -> None:
        assert _check_get({"error": "Something went wrong"}) is False

    def test_empty_response(self) -> None:
        assert _check_get({}) is True


class TestCheckPost:
    def test_success(self) -> None:
        result = _check_post({"success": True, "post": {"id": "123"}})
        assert result is not None
        assert result["success"] is True

    def test_failure(self) -> None:
        assert _check_post({"success": False, "error": "Rate limited"}) is None

    def test_status_code_error(self) -> None:
        assert _check_post({"statusCode": 429, "error": "Too many requests"}) is None

    def test_verification_detected(self, capsys: object) -> None:
        response = {
            "success": True,
            "verification_required": True,
            "verification": {"code": "moltbook_verify_test123", "challenge": "TtEeSsTt", "instructions": "solve this"},
        }
        _check_post(response)
        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "VERIFICATION CHALLENGE" in captured.out
        assert "moltbook_verify_test123" in captured.out


class TestFindVerification:
    def test_top_level(self) -> None:
        v = _find_verification({"verification_required": True, "verification": {"code": "abc", "challenge": "test"}})
        assert v is not None
        assert v["code"] == "abc"

    def test_nested_in_comment(self) -> None:
        v = _find_verification({
            "success": True,
            "comment": {"id": "c1", "verification": {"verification_code": "xyz", "challenge": "test"}},
        })
        assert v is not None
        assert v["verification_code"] == "xyz"

    def test_nested_in_post(self) -> None:
        v = _find_verification({
            "success": True,
            "post": {"id": "p1", "verification": {"code": "def", "challenge": "test"}},
        })
        assert v is not None
        assert v["code"] == "def"

    def test_no_verification(self) -> None:
        assert _find_verification({"success": True}) is None
        assert _find_verification({}) is None

    def test_empty_verification_object(self) -> None:
        d = {"success": True, "comment": {"id": "c1", "verification": {"note": "not a real challenge"}}}
        assert _find_verification(d) is None
