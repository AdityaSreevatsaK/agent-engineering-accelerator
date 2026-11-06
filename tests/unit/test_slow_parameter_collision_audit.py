"""Guard the source-backed seven-case special lane for original comparison tests."""

from reconstruction_tools.verify_slow_parameter_collision import assert_source_contract


def test_numeric_runs_parametrisation_is_not_an_actual_subprocess_fixture():
    assert assert_source_contract() == 7
