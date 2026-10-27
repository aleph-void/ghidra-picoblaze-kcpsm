"""Spelling helpers shared by the PicoBlaze tests: Ghidra's disassembly text -> opbasm source,
and a canonical form of both texts."""
import re

REG = re.compile(r'\bs([0-9A-Fa-f])_b\b')

def to_opbasm(text, pb6=True):
    """Ghidra text ("ADD s1,0x12", "JUMP NZ,0x0abc", "STAR s3_b,s4") -> opbasm source"""
    t = REG.sub(r's\1', text.strip())
    t = re.sub(r'0x([0-9a-fA-F]+)', lambda m: m.group(1).upper(), t)
    t = re.sub(r'\s*,\s*', ', ', t)
    return t.lower()

def canon(text):
    """lower-case, constants as decimal values, single blanks; registers s0..sF"""
    t = text.strip().lower()
    t = REG.sub(lambda m: 's' + m.group(1), t)       # bank B names are only used by STAR
    t = re.sub(r'0x([0-9a-f]+)', lambda m: str(int(m.group(1), 16)), t)
    t = re.sub(r'\s*,\s*', ',', t)
    t = re.sub(r'\s+', ' ', t)
    return t
