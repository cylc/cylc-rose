# THIS FILE IS PART OF THE ROSE-CYLC PLUGIN FOR THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Utility for parsing Jinja2 expressions."""

from ast import literal_eval as python_literal_eval
from copy import deepcopy
from contextlib import contextmanager
import re

from jinja2.nativetypes import NativeEnvironment  # type: ignore
from jinja2.nodes import (  # type: ignore
    Literal,
    Output,
    Pair,
    Template,
    Neg,
    Pos
)
import jinja2.lexer

from cylc.flow import LOG


def _strip_leading_zeros(string):
    """Strip leading zeros from a string.

    Examples:
        >>> _strip_leading_zeros('1')
        '1'
        >>> _strip_leading_zeros('01')
        '1'
        >>> _strip_leading_zeros('001')
        '1'
        >>> _strip_leading_zeros('0001')
        '1'
        >>> _strip_leading_zeros('0')
        '0'
        >>> _strip_leading_zeros('000')
        '0'

    """
    ret = string.lstrip('0')
    return ret or '0'


def _lexer_wrap(fcn):
    """Helper for patch_jinja2_leading_zeros.

    Patches the jinja2.lexer.Lexer.wrap method.
    """
    instances = set()

    def _stream(stream):
        """Patch the token stream to strip the leading zero where necessary."""
        nonlocal instances  # record of uses of deprecated syntax
        for lineno, token, value_str in stream:
            if (
                token == jinja2.lexer.TOKEN_INTEGER
                and len(value_str) > 1
                and value_str[0] == '0'
            ):
                instances.add(value_str)
            yield (lineno, token, _strip_leading_zeros(value_str))

    def _inner(
        self,
        stream,  # : t.Iterable[t.Tuple[int, str, str]],
        name,  # : t.Optional[str] = None,
        filename,  # : t.Optional[str] = None,
    ):  # -> t.Iterator[Token]:
        nonlocal fcn
        return fcn(self, _stream(stream), name, filename)

    _inner.__wrapped__ = fcn  # save the un-patched function
    _inner._instances = instances  # save the set of uses of deprecated syntax

    return _inner


@contextmanager
def patch_jinja2_leading_zeros():
    """Back support integers with leading zeros in Jinja2 v3.

    Jinja2 v3 dropped support for integers with leading zeros, these are
    heavily used throughout Rose configurations. Since there was no deprecation
    warning in Jinja2 v2 we have implemented this patch to extend support for
    a short period to help our users to transition.

    This patch will issue a warning if usage of the deprecated syntax is
    detected during the course of its usage.

    Warning:
        This is a *global* patch applied to the Jinja2 library whilst the
        context manager is open. Do not use this with parallel/async code
        as the patch could apply to code outside of the context manager.

    Examples:
        >>> env = NativeEnvironment()

        The integer "1" is ok:
        >>> env.parse('{{ 1 }}')
        Template(body=[Output(nodes=[Const(value=1)])])

        However "01" is no longer supported:
        >>> env.parse('{{ 01 }}')
        Traceback (most recent call last):
        jinja2.exceptions.TemplateSyntaxError: expected token ...

        The patch returns support (the leading-zero gets stripped):
        >>> with patch_jinja2_leading_zeros():
        ...     env.parse('{{ 01 }}')
        Template(body=[Output(nodes=[Const(value=1)])])

        The patch can handle any number of arbitrary leading zeros:
        >>> with patch_jinja2_leading_zeros():
        ...     env.parse('{{ 0000000001 }}')
        Template(body=[Output(nodes=[Const(value=1)])])

        Once the "with" closes we go back to vanilla Jinja2 behaviour:
        >>> env.parse('{{ 01 }}')
        Traceback (most recent call last):
        jinja2.exceptions.TemplateSyntaxError: expected token ...

    """
    # clear any previously cashed lexer instances
    jinja2.lexer._lexer_cache.clear()

    # apply the code patch (new lexer instances will pick up these changes)
    _integer_re = deepcopy(jinja2.lexer.integer_re)
    jinja2.lexer.integer_re = re.compile(
        rf'''
            # Jinja2 no longer recognises zero-padded integers as integers
            # so we must patch its regex to allow them to be detected.
            (
                [0-9](_?\d)* # decimal (which supports zero-padded integers)
                |
                {jinja2.lexer.integer_re.pattern}
            )
        ''',
        re.IGNORECASE | re.VERBOSE,
    )
    jinja2.lexer.Lexer.wrap = _lexer_wrap(jinja2.lexer.Lexer.wrap)

    # execute the body of the "with" statement
    yield

    # report any usage of deprecated syntax
    if jinja2.lexer.Lexer.wrap._instances:
        num_examples = 5
        LOG.warning(
            'Support for integers with leading zeros was dropped'
            ' in Jinja2 v3.'
            ' Rose will extend support until a future version.'
            '\nPlease amend your Rose configuration files e.g:'
            '\n * '
            + (
                '\n * '.join(
                    f'{before} => {_strip_leading_zeros(before)}'
                    for before in list(
                        jinja2.lexer.Lexer.wrap._instances
                    )[:num_examples]
                )
            )

        )

    # revert the code patch
    jinja2.lexer.integer_re = _integer_re
    jinja2.lexer.Lexer.wrap = jinja2.lexer.Lexer.wrap.__wrapped__

    # clear any patched lexers to return Jinja2 to normal operation
    jinja2.lexer._lexer_cache.clear()


class Parser(NativeEnvironment):

    _LITERAL_NODES = (
        # template node representing the string we passed in
        Template,
        # output node representing our attempt to get the value out
        Output,
        # all valid literals
        Literal,
        # key: value pairs in dictionaries
        Pair,
        # Signed floats (+2.0, -4.2)
        Neg,
        Pos
    )

    _STRING_REGEX = re.compile(
        '^[\'"].*[\'"]$'
    )

    def literal_eval(self, value):
        r"""A jinja2 equivalent to Python's ast.literal_eval.

        Parses and returns valid literals.

        Raises:
            ValueError: When it encounters expressions.

        Examples:
            >>> parser = Parser()

            # valid pythonic literals
            >>> parser.literal_eval('"42"')
            '42'
            >>> parser.literal_eval('42')
            42
            >>> parser.literal_eval('(1,2,3)')
            (1, 2, 3)
            >>> parser.literal_eval('-1.2')
            -1.2
            >>> parser.literal_eval('+1.2')
            1.2
            >>> parser.literal_eval('[1,2,3]')
            [1, 2, 3]
            >>> parser.literal_eval('{"a": 1, "b": 2, "c": 3}')
            {'a': 1, 'b': 2, 'c': 3}
            >>> parser.literal_eval('True')
            True
            >>> parser.literal_eval('None')

            # valid jinja2 variants
            >>> parser.literal_eval('true')
            True
            >>> parser.literal_eval('1,2,3')
            (1, 2, 3)
            >>> parser.literal_eval('1,true,')
            (1, True)

            # multiline literals
            >>> parser.literal_eval('"a"\n" string"')
            'a string'
            >>> parser.literal_eval('1,\n2,\n3')
            (1, 2, 3)

            # back-supported jinja2 variants
            >>> with patch_jinja2_leading_zeros():
            ...     parser.literal_eval('042')
            42

            # invalid examples
            >>> parser.literal_eval('1 + 1')
            Traceback (most recent call last):
            ValueError: Invalid literal: 1 + 1
            <class 'jinja2.nodes.Add'>
            >>> parser.literal_eval('range(5)')
            Traceback (most recent call last):
            ValueError: Invalid literal: range(5)
            <class 'jinja2.nodes.Call'>
            >>> parser.literal_eval('1 if True else 0')
            Traceback (most recent call last):
            ValueError: Invalid literal: 1 if True else 0
            <class 'jinja2.nodes.CondExpr'>

            # quirks
            >>> parser.literal_eval('{1,2,3}')  # Jinja2 cannot handle sets
            Traceback (most recent call last):
            jinja2.exceptions.TemplateSyntaxError: expected token ':', got ','

        """
        # pass string values through ast.literal_eval
        # (jinja2 will peel back the quotes to get at what's inside)
        value = value.strip()
        if self._STRING_REGEX.match(value):
            return python_literal_eval(value)
        # dump this value into a Jinja2 template
        templ = '{{ %s }}' % value
        # check that this expression consists only of literals
        ast = self.parse(templ)
        stack = [ast]
        while stack:
            node = stack.pop()
            if not isinstance(node, self._LITERAL_NODES):
                raise ValueError(
                    f'Invalid literal: {value}'
                    f'\n{type(node)}'
                )
            stack.extend(list(node.iter_child_nodes()))
        # evaluate it
        return self.from_string('{{ %s }}' % value).render()
