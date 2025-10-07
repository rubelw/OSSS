from app.config import settings

def test_defaults():
    assert settings.TUTOR_MAX_TOKENS > 0
