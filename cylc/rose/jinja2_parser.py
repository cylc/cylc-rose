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
            >>> parser.literal_eval('042')
            42
            >>> parser.literal_eval('true')
            True
            >>> parser.literal_eval('1,2,3')
            (1, 2, 3)
            >>> parser.literal_eval('01,true,')
            (1, True)

            # multiline literals
            >>> parser.literal_eval('"a"\n" string"')
            'a string'
            >>> parser.literal_eval('1,\n2,\n3')
            (1, 2, 3)

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
