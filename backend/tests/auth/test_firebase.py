import pytest

from app.auth.firebase import InvalidAuthToken, verify_id_token


def test_rejects_garbage_token():
    with pytest.raises(InvalidAuthToken):
        verify_id_token("not-a-real-jwt")


def test_rejects_empty_token():
    with pytest.raises(InvalidAuthToken):
        verify_id_token("")
