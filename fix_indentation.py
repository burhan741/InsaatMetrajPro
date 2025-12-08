#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Girinti hatalarını düzelt"""
import re

file_path = "app/ui/main_window.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Girinti hatalarını düzelt
fixed_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Try bloğundan sonra girinti hatası varsa düzelt
    if i > 0 and 'try:' in lines[i-1] and line.strip() and not line.startswith(' ' * (len(lines[i-1]) - len(lines[i-1].lstrip()) + 4)):
        # Try'den sonraki satırı girintile
        indent = len(lines[i-1]) - len(lines[i-1].lstrip())
        if not line.strip().startswith('except') and not line.strip().startswith('finally'):
            line = ' ' * (indent + 4) + line.lstrip()
    
    # If bloğundan sonra girinti hatası varsa düzelt
    if i > 0 and lines[i-1].strip().endswith(':') and not lines[i-1].strip().startswith('#') and line.strip() and not line.startswith(' ' * (len(lines[i-1]) - len(lines[i-1].lstrip()) + 4)):
        # If'ten sonraki satırı girintile
        indent = len(lines[i-1]) - len(lines[i-1].lstrip())
        if not line.strip().startswith('elif') and not line.strip().startswith('else') and not line.strip().startswith('except') and not line.strip().startswith('finally'):
            line = ' ' * (indent + 4) + line.lstrip()
    
    fixed_lines.append(line)
    i += 1

# Dosyayı yaz
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print("Girinti hataları düzeltildi!")



