# Copyright (c) 2016 GeoSpark
#
# Released under the MIT License (MIT)
# See the LICENSE file, or visit http://opensource.org/licenses/MIT

# Inspired by: https://thoughtsbyclayg.blogspot.co.uk/2008/10/parsing-list-of-numbers-in-python.html

# return a set of selected values when a string in the form:
# 1-4,6
# would return:
# 1,2,3,4,6
# as expected...


def parse_disjoint_range(range_string):
    selection = set()
    invalid = set()

    tokens = [x.strip() for x in range_string.split(',')]
    for token in tokens:
        try:
            selection.add(int(token))
        except ValueError:
            try:
                token_parts = [int(x) for x in token.split('-')]

                if len(token_parts) != 2:
                    raise ValueError

                token_parts.sort()
                selection = selection.union(range(token_parts[0], token_parts[1] + 1))
            except ValueError:
                invalid.add(token)

    return sorted(selection), invalid
