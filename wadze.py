# wadze.py
#
# Web Assembly Decoder - Zero Extras
#
# Copyright (C) 2019
# David M. Beazley (https://www.dabeaz.com)
# All Rights Reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:

# * Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.  
# * Redistributions in binary form must reproduce the above copyright notice, 
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.  
# * Neither the name of the David Beazley or Dabeaz LLC may be used to
#   endorse or promote products derived from this software without
#   specific prior written permission. 
#
# This software is provided "as is."  The risks of using it are yours.

from collections import namedtuple
from itertools import islice
import struct

_typemap = {
    0x7f : 'i32', 
    0x7e : 'i64', 
    0x7d : 'f32',  
    0x7c : 'f64', 
    0x70 : 'anyfunc',
    0x60 : 'func',
    0x40 : None,
}

def parse_unsigned(stream):
    result = shift = 0
    while True:
        b = next(stream)
        result |= (b & 0x7f) << shift
        shift += 7
        if not (b & 0x80):
            break
    return result

def parse_signed(stream):
    result = shift = 0
    while True:
        b = next(stream)
        result |= (b & 0x7f) << shift
        shift += 7
        if not (b & 0x80):
            break
    if b & 0x40:
        result |= (~0 << shift)
    return result

def parse_float32(stream):
    return struct.unpack('<f', bytes(islice(stream, 4)))[0]

def parse_float64(stream):
    return struct.unpack('<d', bytes(islice(stream, 8)))[0]

def parse_vector(stream, func):
    return [ func(stream) for _ in range(parse_unsigned(stream)) ]

def parse_string(stream):
    return bytes(parse_vector(stream, next)).decode('utf-8')

FunctionType = namedtuple('FunctionType', ['params', 'returns'])

def parse_functype(stream):
    sigtype = next(stream)
    params = [ _typemap[t] for t in parse_vector(stream, next) ]
    returns = [ _typemap[t] for t in parse_vector(stream, next) ]
    return FunctionType(params, returns)

Limits = namedtuple('Limits', ['min', 'max'])

def parse_limits(stream):
    return Limits(parse_unsigned(stream), parse_unsigned(stream)) if next(stream) else (parse_unsigned(stream), None)

TableType = namedtuple('TableType', ['elemtype', 'limits'])

def parse_tabletype(stream):
    return TableType(_typemap[next(stream)], parse_limits(stream))


GlobalType = namedtuple('GlobalType', ['type', 'mut'])

def parse_globaltype(stream):
    return GlobalType(_typemap[next(stream)], next(stream))

ImportFunction = namedtuple('ImportFunction', ['module','name','typeidx'])
ImportTable = namedtuple('ImportTable', ['module','name', 'tabletype'])
ImportMemory = namedtuple('ImportMemory', ['module', 'name', 'limits'])
ImportGlobal = namedtuple('ImportGlobal', ['module', 'name', 'globaltype'])

_imports = {
    0 : (ImportFunction, parse_unsigned),
    1 : (ImportTable, parse_tabletype),
    2 : (ImportMemory, parse_limits),
    3 : (ImportGlobal, parse_globaltype),
}    

def parse_import(stream):
    module = parse_string(stream)
    name = parse_string(stream)
    cls, func = _imports[next(stream)]
    return cls(module, name, func(stream))

Global = namedtuple('Global', ['globaltype', 'expr'])

def parse_global(stream):
    return Global(parse_globaltype(stream), parse_instructions(stream))

ExportFunction = namedtuple('ExportFunction', ['name', 'ref'])
ExportTable = namedtuple('ExportTable', ['name', 'ref'])
ExportMemory = namedtuple('ExportMemory', ['name', 'ref'])
ExportGlobal = namedtuple('ExportGlobal', ['name', 'ref'])

_exports = { 0: ExportFunction, 1: ExportTable, 2: ExportMemory, 3: ExportGlobal }

def parse_export(stream):
    name = parse_string(stream)
    return _exports[next(stream)](name, parse_unsigned(stream))

Element = namedtuple('Element', ['tableidx', 'offset', 'values'])

def parse_element(stream):
    return Element(parse_unsigned(stream), parse_instructions(stream), parse_vector(stream, parse_unsigned))

def parse_locals(stream):
    return parse_unsigned(stream) * (_typemap[next(stream)],)

Code = namedtuple('Code', ['locals', 'instructions'])

def parse_rawcode(stream):
    return bytes(islice(stream, parse_unsigned(stream)))

def parse_code(raw):
    if isinstance(raw, bytes):
        code = iter(raw)
    locals = [ ]
    for loc in parse_vector(code, parse_locals):
        locals.extend(loc)
    instructions = parse_instructions(code)
    return Code(locals, instructions)

Data = namedtuple('Data', ['memidx', 'offset', 'values'])

def parse_data(stream):
    return Data(parse_unsigned(stream), parse_instructions(stream), parse_vector(stream, next))

def parse_instructions(stream):
    instructions = [ ]
    while True:
        op = next(stream)
        if op == 0x0b:
            break
        name, *funcs = _opcodes[op]
        instructions.append((name, *(func(stream) for func in funcs)))
    return instructions

def _split_else(instructions):
    if ('else',) in instructions:
        index = instructions.index(('else',))
        return (instructions[:index], instructions[index+1:])
    else:
        return (instructions, [])

_opcodes = {
    0x00 : ('unreachable', ),
    0x01 : ('nop', ),
    0x02 : ('block', lambda s: _typemap[next(s)], parse_instructions),
    0x03 : ('loop', lambda s: _typemap[next(s)], parse_instructions),
    0x04 : ('if', lambda s: _typemap[next(s)], lambda s: _split_else(parse_instructions(s))),
    0x05 : ('else',),
    0x0c : ('br', parse_unsigned),
    0x0d : ('br_if', parse_unsigned),
    0x0e : ('br_table', lambda s: parse_vector(s, parse_unsigned), parse_unsigned),
    0x0f : ('return', ),
    0x10 : ('call', parse_unsigned),
    0x11 : ('call_indirect', parse_unsigned, next),
    0x1a : ('drop', ),
    0x1b : ('select', ),
    0x20 : ('local.get', parse_unsigned),
    0x21 : ('local.set', parse_unsigned),
    0x22 : ('local.tee', parse_unsigned),
    0x23 : ('global.get', parse_unsigned),
    0x24 : ('global.set', parse_unsigned),
    0x28 : ('i32.load', parse_signed, parse_signed),
    0x29 : ('i64.load', parse_signed, parse_signed),
    0x2a : ('f32.load', parse_signed, parse_signed),
    0x2b : ('f64.load', parse_signed, parse_signed),
    0x2c : ('i32.load8_s', parse_signed, parse_signed),
    0x2d : ('i32.load8_u', parse_signed, parse_signed),
    0x2e : ('i32.load16_s', parse_signed, parse_signed),
    0x2f : ('i32.load16_u', parse_signed, parse_signed),
    0x30 : ('i64.load8_s', parse_signed, parse_signed),
    0x31 : ('i64.load8_u', parse_signed, parse_signed),
    0x32 : ('i64.load16_s', parse_signed, parse_signed),
    0x33 : ('i64.load16_u', parse_signed, parse_signed),
    0x34 : ('i64.load32_s', parse_signed, parse_signed),
    0x35 : ('i64.load32_u', parse_signed, parse_signed),
    0x36 : ('i32.store', parse_signed, parse_signed),
    0x37 : ('i64.store', parse_signed, parse_signed),
    0x38 : ('f32.store', parse_signed, parse_signed),
    0x39 : ('f64.store', parse_signed, parse_signed),
    0x3a : ('i32.store8', parse_signed, parse_signed),
    0x3b : ('i32.store16', parse_signed, parse_signed),
    0x3c : ('i64.store8', parse_signed, parse_signed),
    0x3d : ('i64.store16', parse_signed, parse_signed),
    0x3e : ('i64.store32', parse_signed, parse_signed),
    0x3f : ('memory.size', next),
    0x40 : ('memory.grow', next),
    0x41 : ('i32.const', parse_signed),
    0x42 : ('i64.const', parse_signed),
    0x43 : ('f32.const', parse_float32),
    0x44 : ('f64.const', parse_float64),
    0x45 : ('i32.eqz', ),
    0x46 : ('i32.eq', ),
    0x47 : ('i32.ne', ),
    0x48 : ('i32.lt_s', ),
    0x49 : ('i32.lt_u', ),
    0x4a : ('i32.gt_s', ),
    0x4b : ('i32.gt_u', ),
    0x4c : ('i32.le_s', ),
    0x4d : ('i32.le_u', ),
    0x4e : ('i32.ge_s', ),
    0x4f : ('i32.ge_u', ),
    0x50 : ('i64.eqz', ),
    0x51 : ('i64.eq', ),
    0x52 : ('i64.ne', ),
    0x53 : ('i64.lt_s', ),
    0x54 : ('i64.lt_u', ),
    0x55 : ('i64.gt_s', ),
    0x56 : ('i64.gt_u', ),
    0x57 : ('i64.le_s', ),
    0x58 : ('i64.le_u', ),
    0x59 : ('i64.ge_s', ),
    0x5a : ('i64.ge_u', ),
    0x5b : ('f32.eq', ),
    0x5c : ('f32.ne', ),
    0x5d : ('f32.lt', ),
    0x5e : ('f32.gt', ),
    0x5f : ('f32.le', ),
    0x60 : ('f32.ge', ),
    0x61 : ('f64.eq', ),
    0x62 : ('f64.ne', ),
    0x63 : ('f64.lt', ),
    0x64 : ('f64.gt', ),
    0x65 : ('f64.le', ),
    0x66 : ('f64.ge', ),
    0x67 : ('i32.clz', ),
    0x68 : ('i32.ctz', ),
    0x69 : ('i32.popcnt', ),
    0x6a : ('i32.add', ),
    0x6b : ('i32.sub', ),
    0x6c : ('i32.mul', ),
    0x6d : ('i32.div_s', ),
    0x6e : ('i32.div_u', ),
    0x6f : ('i32.rem_s', ),
    0x70 : ('i32.rem_u', ),
    0x71 : ('i32.and', ),
    0x72 : ('i32.or', ),
    0x73 : ('i32.xor', ),
    0x74 : ('i32.shl', ),
    0x75 : ('i32.shr_s', ),
    0x76 : ('i32.shr_u', ),
    0x77 : ('i32.rotl', ),
    0x78 : ('i32.rotr', ),
    0x79 : ('i64.clz', ),
    0x7a : ('i64.ctz', ),
    0x7b : ('i64.popcnt', ),
    0x7c : ('i64.add', ),
    0x7d : ('i64.sub', ),
    0x7e : ('i64.mul', ),
    0x7f : ('i64.div_s', ),
    0x80 : ('i64.div_u', ),
    0x81 : ('i64.rem_s', ),
    0x82 : ('i64.rem_u', ),
    0x83 : ('i64.and', ),
    0x84 : ('i64.or', ),
    0x85 : ('i64.xor', ),
    0x86 : ('i64.shl', ),
    0x87 : ('i64.shr_s', ),
    0x88 : ('i64.shr_u', ),
    0x89 : ('i64.rotl', ),
    0x8a : ('i64.rotr', ),
    0x8b : ('f32.abs', ),
    0x8c : ('f32.neg', ),
    0x8d : ('f32.ceil', ),
    0x8e : ('f32.floor', ),
    0x8f : ('f32.trunc', ),
    0x90 : ('f32.nearest', ),
    0x91 : ('f32.sqrt', ),
    0x92 : ('f32.add', ),
    0x93 : ('f32.sub', ),
    0x94 : ('f32.mul', ),
    0x95 : ('f32.div', ),
    0x96 : ('f32.min', ),
    0x97 : ('f32.max', ),
    0x98 : ('f32.copysign', ),
    0x99 : ('f64.abs', ),
    0x9a : ('f64.neg', ),
    0x9b : ('f64.ceil', ),
    0x9c : ('f64.floor', ),
    0x9d : ('f64.trunc', ),
    0x9e : ('f64.nearest', ),
    0x9f : ('f64.sqrt', ),
    0xa0 : ('f64.add', ),
    0xa1 : ('f64.sub', ),
    0xa2 : ('f64.mul', ),
    0xa3 : ('f64.div', ),
    0xa4 : ('f64.min', ),
    0xa5 : ('f64.max', ),
    0xa6 : ('f64.copysign', ),
    0xa7 : ('i32.wrap_i64', ),
    0xa8 : ('i32.trunc_f32_s', ),
    0xa9 : ('i32.trunc_f32_u', ),
    0xaa : ('i32.trunc_f64_s', ),
    0xab : ('i32.trunc_f64_u', ),
    0xac : ('i64.extend_i32_s', ),
    0xad : ('i64.extend_i32_u', ),
    0xae : ('i64.trunc_f32_s', ),
    0xaf : ('i64.trunc_f32_u', ),
    0xb0 : ('i64.trunc_f64_s', ),
    0xb1 : ('i64.trunc_f64_u', ),
    0xb2 : ('f32.convert_i32_s', ),
    0xb3 : ('f32.convert_i32_u', ),
    0xb4 : ('f32.convert_i64_s', ),
    0xb5 : ('f32.convert_i64_u', ),
    0xb6 : ('f32.demote_f64', ),
    0xb7 : ('f64.convert_i32_s', ),
    0xb8 : ('f64.convert_i32_u', ),
    0xb9 : ('f64.convert_i64_s', ),
    0xba : ('f64.convert_i64_u', ),
    0xbb : ('f64.promote_f32', ),
    0xbc : ('i32.reinterpret_f32', ),
    0xbd : ('i64.reinterpret_f64', ),
    0xbe : ('f32.reinterpret_i32', ),
    0xbf : ('f64.reinterpret_i64', ),
}

_sections = {
    1 : ('type', lambda s: parse_vector(s, parse_functype)),
    2 : ('import', lambda s: parse_vector(s, parse_import)),
    3 : ('func', lambda s: parse_vector(s, parse_unsigned)),
    4 : ('table', lambda s: parse_vector(s, parse_tabletype)),
    5 : ('memory', lambda s: parse_vector(s, parse_limits)),
    6 : ('global', lambda s: parse_vector(s, parse_global)),
    7 : ('export', lambda s: parse_vector(s, parse_export)),
    8 : ('start', parse_unsigned),
    9 : ('element', lambda s: parse_vector(s, parse_element)),
    10 : ('code', lambda s: parse_vector(s, parse_rawcode)),
    11 : ('data', lambda s: parse_vector(s, parse_data)),
}

def parse_section(stream):
    sectnum = next(stream)
    size = parse_unsigned(stream)
    if sectnum in _sections:
        sectname, parse_func = _sections[sectnum]
        return (sectname, parse_func(stream))
    else:
        return (sectnum, bytes(islice(stream, size)))

def parse_module(stream):
    '''
    Parse binary .wasm format data into a dictionary representing the
    different sections of a Wasm module. stream is either an iterator
    producing bytes or a byte string containing the raw data from a
    .wasm file.
    '''
    if isinstance(stream, bytes):
        stream = iter(stream)
    header = bytes(islice(stream, 8))
    if header[:4] != b'\x00asm':
        raise ValueError('Expected .wasm')
    sections = { }
    while True:
        try:
            sectname, items = parse_section(stream)
            sections[sectname] = items
        except StopIteration:
            break
    return sections

# Example use
if __name__ == '__main__':
    module = parse_module(open('input.wasm','rb').read())
    # If you want to parse instruction code, also include this
    module['code'] = [ parse_code(c) for c in module['code']]



        
