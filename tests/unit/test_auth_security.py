from invoice_processing.auth.security import generate_session_token, hash_password, verify_password


def test_verify_password_accepts_the_correct_password():
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed)


def test_verify_password_rejects_the_wrong_password():
    hashed = hash_password("correct-horse-battery-staple")
    assert not verify_password("wrong-password", hashed)


def test_hash_password_does_not_store_the_plaintext():
    hashed = hash_password("correct-horse-battery-staple")
    assert "correct-horse-battery-staple" not in hashed


def test_hash_password_is_salted_so_the_same_password_hashes_differently():
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_password_fails_closed_on_a_malformed_hash():
    assert not verify_password("anything", "not-a-real-bcrypt-hash")


def test_generate_session_token_is_unique_and_url_safe():
    tokens = {generate_session_token() for _ in range(20)}
    assert len(tokens) == 20
    for token in tokens:
        assert "/" not in token and "+" not in token
