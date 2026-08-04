"""Bootstrap tests — verify all modules import and basic contracts hold."""

from pathlib import Path


def test_version_exists():
    from rw_promptforge import __version__
    assert __version__ == "0.1.0"


def test_provider_import():
    from rw_promptforge.provider import Provider
    provider = Provider()
    assert provider.model == "gpt-4o-mini"
    assert provider.endpoint == "https://api.openai.com/v1"
    provider.close()


def test_provider_from_env():
    import os
    from rw_promptforge.provider import Provider

    os.environ["OPENROUTER_API_KEY"] = "sk-test-123"
    provider = Provider.from_env()
    assert "openrouter.ai" in provider.endpoint
    assert provider.api_key == "sk-test-123"
    del os.environ["OPENROUTER_API_KEY"]
    provider.close()


def test_shell_evaluator_import():
    from rw_promptforge.evaluator.shell import EvalResult, ShellEvaluator

    eval_result = EvalResult(0, "ok", "", "test", 0.5)
    assert eval_result.passed
    assert not eval_result.failed
    assert "PASS" in eval_result.format_trace()

    evaluator = ShellEvaluator("hermes test --skill {path}")
    assert "{path}" in evaluator.command_template


def test_skill_target():
    from rw_promptforge.targets.skill import SkillTarget

    target = SkillTarget(__file__)
    assert Path(target.path) == Path(__file__)
    assert target.estimate_tokens() > 0


def test_soul_target():
    from rw_promptforge.targets.soul import SoulTarget

    target = SoulTarget(__file__)
    assert Path(target.path) == Path(__file__)
    assert target.estimate_tokens() > 0
    assert "machine_protocol" in SoulTarget.ARMORED_SECTIONS


def test_reflector_import():
    from rw_promptforge.reflector.engine import REFLECTION_SYSTEM_PROMPT, REFLECTION_USER_TEMPLATE, Reflector

    from rw_promptforge.provider import Provider

    reflector = Reflector(Provider())
    assert reflector is not None
    assert "CURRENT ARTIFACT" in REFLECTION_USER_TEMPLATE
    assert "prompt engineering expert" in REFLECTION_SYSTEM_PROMPT


def test_session_db_reader():
    from rw_promptforge.datastore.session_db import SessionDBReader

    reader = SessionDBReader()
    assert reader.db_path.name == "sessions.db"
    assert not reader.exists()  # Won't exist unless we're in a Hermes environment with session_db