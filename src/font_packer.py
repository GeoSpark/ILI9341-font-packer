# Copyright (c) 2016 GeoSpark
#
# Released under the MIT License (MIT)
# See the LICENSE file, or visit http://opensource.org/licenses/MIT

"""ILI9341 Font Packer

Converts TrueType fonts to a compact binary bitmap format for use with Paul Stoffregen's ILI9341 library for the Teensy.

Usage:
    font_packer.py --height=<pixels> [--range=<range-string>] [--placeholder=<ascii-code>] [--packed|--code|--smoke]
                   <font-file> [<output>]
    font_packer.py -h | --help
    font_packer.py --version

Options:
    -h --help                   Show this screen.
    --version                   Show version.
    --height=<pixels>           The maximum height of the glyphs.
    --range=<range-string>      A range of ASCII codes to generate glyphs for [default: 32-126].
    --placeholder=<ascii-code>  A placeholder character to use for ones not in the set. Defaults to the first one.
    --packed                    Sends the packed binary bitmap font to output or stdout.
    --code                      Generates C structs to output or stdout.
    --smoke                     Smoke proof. Displays to output or stdout the bitmaps of each character as asterisks.
    output                      Output file name or stdout if not supplied.
"""

import os
import sys
import struct
import math
import binascii
from collections import OrderedDict

import io
from bitstring import Bits, BitString
from docopt import docopt

from font import Font
from range_parser import parse_disjoint_range


def generate(height, ascii_range, font_file_path, output_file_name, placeholder, packed, code, smoke):
    glyphs = [chr(x) for x in ascii_range]

    font = Font(font_file_path, height)

    if smoke:
        f = sys.stdout.buffer
        if output_file_name is not None:
            f = open(output_file_name, 'wt')

        if placeholder is not None:
            ch = font.render_character(chr(placeholder))
            f.write(chr(placeholder) + '\n')
            f.write(repr(ch))
            f.write('\n\n')

        for cur_glyph in glyphs:
            ch = font.render_character(cur_glyph)
            f.write(cur_glyph + '\n')
            f.write(repr(ch))
            f.write('\n\n')

        f.close()
        return

    ili9341_t3_font = OrderedDict()
    ili9341_t3_font['index'] = 0
    ili9341_t3_font['unicode'] = 0
    ili9341_t3_font['data'] = 0
    ili9341_t3_font['version'] = 1
    ili9341_t3_font['reserved'] = 0
    ili9341_t3_font['index1_first'] = ascii_range[0]
    ili9341_t3_font['index1_last'] = ascii_range[-1]
    ili9341_t3_font['index2_first'] = 0
    ili9341_t3_font['index2_last'] = 0
    ili9341_t3_font['bits_index'] = 0
    ili9341_t3_font['bits_width'] = 0
    ili9341_t3_font['bits_height'] = 0
    ili9341_t3_font['bits_xoffset'] = 0
    ili9341_t3_font['bits_yoffset'] = 0
    ili9341_t3_font['bits_delta'] = 0
    ili9341_t3_font['line_space'] = font.height
    e_cap = font.glyph_for_character('E')
    ili9341_t3_font['cap_height'] = e_cap.height - e_cap.descent

    max_width = 1
    max_height = 1
    max_xoffset = 1
    max_yoffset = 1
    max_delta = 1

    glyph_data = dict()

    if placeholder is not None:
        glyph_header = build_glyph(chr(placeholder), font, glyph_data, True)
        max_width = max(max_width, glyph_header['width'])
        max_height = max(max_height, glyph_header['height'])
        max_xoffset = max(abs(max_xoffset), abs(glyph_header['xoffset']))
        max_yoffset = max(abs(max_yoffset), abs(glyph_header['yoffset']))
        max_delta = max(max_delta, glyph_header['delta'])

    for cur_glyph in glyphs:
        glyph_header = build_glyph(cur_glyph, font, glyph_data)
        max_width = max(max_width, glyph_header['width'])
        max_height = max(max_height, glyph_header['height'])
        max_xoffset = max(abs(max_xoffset), abs(glyph_header['xoffset']))
        max_yoffset = max(abs(max_yoffset), abs(glyph_header['yoffset']))
        max_delta = max(max_delta, glyph_header['delta'])

    ili9341_t3_font['bits_width'] = int(math.floor(math.log(max_width, 2))) + 1
    ili9341_t3_font['bits_height'] = int(math.floor(math.log(max_height, 2))) + 1
    ili9341_t3_font['bits_xoffset'] = int(math.floor(math.log(max_xoffset, 2))) + 2
    ili9341_t3_font['bits_yoffset'] = int(math.floor(math.log(max_yoffset, 2))) + 2
    ili9341_t3_font['bits_delta'] = int(math.floor(math.log(max_delta, 2))) + 1

    output_data = bytearray()
    index = list()
    total_size = 0

    if placeholder is not None:
        glyph = glyph_data['placeholder']
        glyph_bytes = pack_glyph(glyph, ili9341_t3_font)
        output_data.extend(glyph_bytes)
        total_size += len(glyph_bytes)

    for ascii_code in range(ili9341_t3_font['index1_first'], ili9341_t3_font['index1_last'] + 1):
        ch = chr(ascii_code)

        if ch not in glyph_data:
            index.append(0)
            continue

        index.append(total_size)
        glyph = glyph_data[ch]
        glyph_bytes = pack_glyph(glyph, ili9341_t3_font)
        output_data.extend(glyph_bytes)
        total_size += len(glyph_bytes)

    ili9341_t3_font['bits_index'] = int(math.floor(math.log(total_size, 2))) + 1

    index_bits = BitString()

    for idx in index:
        index_bits.append(Bits(uint=idx, length=ili9341_t3_font['bits_index']))

    if packed:
        f = sys.stdout.buffer

        if output_file_name is not None:
            f = open(output_file_name, 'wb')

        f.write(struct.pack('<3I14Bxx', *tuple(ili9341_t3_font.values())))
        index_bits.tofile(f)
        f.write(output_data)
        f.close()

    if code:
        f = sys.stdout.buffer

        if output_file_name is not None:
            f = open(output_file_name, 'wb')

        variable_name = os.path.splitext(os.path.basename(font_file_path))[0] + '_' + str(height)
        c = io.StringIO()

        c.write('// extern const ILI9341_t3_font_t {};\n\n'.format(variable_name))

        c.write('static const unsigned char {}_data[] = {{\n'.format(variable_name))
        data_byte_array = ['0x' + binascii.hexlify(bytes([x])).decode() for x in output_data]
        for i in range(0, len(data_byte_array), 10):
            c.write(','.join(data_byte_array[i:i + 10]) + ',\n')
        c.write('};\n')
        c.write('/* font data size: {} bytes */\n\n'.format(len(data_byte_array)))

        c.write('static const unsigned char {}_index[] = {{\n'.format(variable_name))
        index_byte_array = ['0x' + binascii.hexlify(bytes([x])).decode() for x in index_bits.tobytes()]
        for i in range(0, len(index_byte_array), 10):
            c.write(','.join(index_byte_array[i:i + 10]) + ',\n')
        c.write('};\n')
        c.write('/* font index size: {} bytes */\n\n'.format(len(index_byte_array)))

        c.write('const ILI9341_t3_font_t {} = {{\n'.format(variable_name))
        c.write('    {}_index,\n'.format(variable_name))
        c.write('    {},\n'.format(ili9341_t3_font['unicode']))
        c.write('    {}_data,\n'.format(variable_name))
        c.write('    {},\n'.format(ili9341_t3_font['version']))
        c.write('    {},\n'.format(ili9341_t3_font['reserved']))
        c.write('    {},\n'.format(ili9341_t3_font['index1_first']))
        c.write('    {},\n'.format(ili9341_t3_font['index1_last']))
        c.write('    {},\n'.format(ili9341_t3_font['index2_first']))
        c.write('    {},\n'.format(ili9341_t3_font['index2_last']))
        c.write('    {},\n'.format(ili9341_t3_font['bits_index']))
        c.write('    {},\n'.format(ili9341_t3_font['bits_width']))
        c.write('    {},\n'.format(ili9341_t3_font['bits_height']))
        c.write('    {},\n'.format(ili9341_t3_font['bits_xoffset']))
        c.write('    {},\n'.format(ili9341_t3_font['bits_yoffset']))
        c.write('    {},\n'.format(ili9341_t3_font['bits_delta']))
        c.write('    {},\n'.format(ili9341_t3_font['line_space']))
        c.write('    {}\n'.format(ili9341_t3_font['cap_height']))
        c.write('};\n')

        f.write(c.getvalue().encode('ascii'))


def pack_glyph(glyph, ili9341_t3_font):
    glyph_bits = BitString()
    header = glyph['header']
    glyph_bits.append(Bits(uint=header['encoding'], length=3))
    glyph_bits.append(Bits(uint=header['width'], length=ili9341_t3_font['bits_width']))
    glyph_bits.append(Bits(uint=header['height'], length=ili9341_t3_font['bits_height']))
    glyph_bits.append(Bits(int=header['xoffset'], length=ili9341_t3_font['bits_xoffset']))
    glyph_bits.append(Bits(int=header['yoffset'], length=ili9341_t3_font['bits_yoffset']))
    glyph_bits.append(Bits(uint=header['delta'], length=ili9341_t3_font['bits_delta']))
    for row in glyph['data']:
        if row['repeat'] == 0:
            glyph_bits.append(Bits(bool=False))
        else:
            glyph_bits.append(Bits(bool=True))
            glyph_bits.append(Bits(uint=row['repeat'] - 1, length=3))

        for bit in row['bits']:
            glyph_bits.append(Bits(bool=bit == 1))
    glyph_bytes = glyph_bits.tobytes()
    return glyph_bytes


def build_glyph(cur_glyph, font, glyph_data, isplaceholder=False):
    glyph_header = dict()
    g = font.glyph_for_character(cur_glyph)
    glyph_header['encoding'] = 0
    glyph_header['width'] = g.width
    glyph_header['height'] = g.height
    glyph_header['xoffset'] = g.x_bearing
    glyph_header['yoffset'] = g.top-g.height
    glyph_header['delta'] = g.advance_width
    rows = list()
    rows.append({'repeat': 0, 'bits': g.bitmap.pixels[0:g.bitmap.width]})
    row_idx = 0

    for row in range(1, g.bitmap.height):
        start = row * g.bitmap.width
        bits = g.bitmap.pixels[start:start + g.bitmap.width]

        if rows[row_idx]['repeat'] < 7 and bits == rows[row_idx]['bits']:
            rows[row_idx]['repeat'] += 1
        else:
            row_idx += 1
            rows.append({'repeat': 0, 'bits': bits})

    if isplaceholder:
        glyph_data['placeholder'] = {'header': glyph_header, 'data': rows}
    else:
        glyph_data[cur_glyph] = {'header': glyph_header, 'data': rows}

    return glyph_header


if __name__ == '__main__':
    args = docopt(__doc__, version='ILI9341 Font Packer v1.0')

    if not (args['--packed'] or args['--code'] or args['--smoke']):
        args['--packed'] = True

    r, invalid = parse_disjoint_range(args['--range'])

    if len(invalid) > 0:
        sys.stderr.write('Warning, invalid values in range: {}'.format(invalid))

    generate(int(args['--height']), r, args['<font-file>'], args['<output>'], int(args['--placeholder']),
             args['--packed'], args['--code'], args['--smoke'])
