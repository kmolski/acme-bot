import re

import pytest
from discord.ext import commands

from acme_bot.shell import validate_options, trim_double_newline, execute_system_cmd


def test_validate_options_passes_on_valid_opt():
    regex = re.compile(r"-[ABC]+")
    validate_options(["-ABC"], regex)


def test_validate_options_throws_on_invalid_opt():
    regex = re.compile(r"-[ABC]+")
    with pytest.raises(commands.CommandError):
        validate_options(["-DEF"], regex)


def test_trim_double_newline_with_single_newline():
    string = "foo\n"
    assert trim_double_newline(string) == string


def test_trim_double_newline_with_double_newline():
    assert trim_double_newline("foo\n\n") == "foo\n"
