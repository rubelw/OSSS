#!/usr/bin/env python3

"""
Annotate SQLAlchemy models with __table_args__ comments ...
"""
from __future__ import annotations
import logging
from functools import wraps
import os
_LOG_LEVEL = os.getenv('ANNOTATE_MODELS_LOG', 'DEBUG').upper()
logger = logging.getLogger('annotate_models')
import inspect

def log_here(msg, *args):
    import inspect
    frame = inspect.currentframe().f_back
    try:
        lineno = frame.f_lineno if frame and hasattr(frame, 'f_lineno') else -1
    except Exception:
        lineno = -1
    try:
        logger.debug('line %d: ' + msg, lineno, *args)
    except Exception:
        logger.debug('line %d: %s', lineno, msg)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d: %(message)s'))
    logger.addHandler(_handler)
try:
    logger.setLevel(getattr(logging, _LOG_LEVEL, logging.DEBUG))
except Exception:
    logger.setLevel(logging.DEBUG)

def log_call(fn):

    @wraps(fn)
    def _wrapper(*args, **kwargs):
        log_here('→ %s args=%r kwargs=%r', fn.__name__, args, kwargs)
        try:
            result = fn(*args, **kwargs)
            log_here('← %s result=%r', fn.__name__, result)
            return result
        except Exception:
            logger.exception('✖ %s failed', fn.__name__)
            raise
    return _wrapper

import logging
from functools import wraps
import os
_LOG_LEVEL = os.getenv('ANNOTATE_MODELS_LOG', 'DEBUG').upper()
logger = logging.getLogger('annotate_models')
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d: %(message)s'))
    logger.addHandler(_handler)
try:
    logger.setLevel(getattr(logging, _LOG_LEVEL, logging.DEBUG))
except Exception:
    logger.setLevel(logging.DEBUG)
import logging
from functools import wraps
import os
_LOG_LEVEL = os.getenv('ANNOTATE_MODELS_LOG', 'DEBUG').upper()
logger = logging.getLogger('annotate_models')
if not logger.handlers:
    log_here('if-branch entered')
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d: %(message)s'))
    logger.addHandler(_handler)
try:
    log_here('try-block entered')
    logger.setLevel(getattr(logging, _LOG_LEVEL, logging.DEBUG))
except Exception:
    log_here('except-block entered')
    logger.setLevel(logging.DEBUG)
VERY_VERBOSE = os.getenv('ANNOTATE_MODELS_VERY_VERBOSE', '1') not in ('0', 'false', 'False', '')

@log_call
def _short(x):
    log_here('enter function: %s', '_short')
    try:
        log_here('try-block entered')
        s = repr(x)
    except Exception:
        log_here('except-block entered')
        return '<unrepr-able>'
    return s[:300] + '…' if len(s) > 300 else s
import logging
from functools import wraps
import os
_LOG_LEVEL = os.getenv('ANNOTATE_MODELS_LOG', 'DEBUG').upper()
logger = logging.getLogger('annotate_models')
if not logger.handlers:
    log_here('if-branch entered')
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d: %(message)s'))
    logger.addHandler(_handler)
try:
    log_here('try-block entered')
    logger.setLevel(getattr(logging, _LOG_LEVEL, logging.DEBUG))
except Exception:
    log_here('except-block entered')
    logger.setLevel(logging.DEBUG)
import logging
from functools import wraps
import os
_LOG_LEVEL = os.getenv('ANNOTATE_MODELS_LOG', 'DEBUG').upper()
logger = logging.getLogger('annotate_models')
if not logger.handlers:
    log_here('if-branch entered')
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d: %(message)s'))
    logger.addHandler(_handler)
try:
    log_here('try-block entered')
    logger.setLevel(getattr(logging, _LOG_LEVEL, logging.DEBUG))
except Exception:
    log_here('except-block entered')
    logger.setLevel(logging.DEBUG)
import logging
from functools import wraps
import os
_LOG_LEVEL = os.getenv('ANNOTATE_MODELS_LOG', 'DEBUG').upper()
if not logger.handlers:
    log_here('if-branch entered')
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d: %(message)s'))
    logger.addHandler(_handler)
try:
    log_here('try-block entered')
    logger.setLevel(getattr(logging, _LOG_LEVEL, logging.DEBUG))
except Exception:
    log_here('except-block entered')
    logger.setLevel(logging.DEBUG)
import logging
from functools import wraps
import os
_LOG_LEVEL = os.getenv('ANNOTATE_MODELS_LOG', 'DEBUG').upper()
if not logger.handlers:
    log_here('if-branch entered')
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d: %(message)s'))
    logger.addHandler(_handler)
try:
    log_here('try-block entered')
    logger.setLevel(getattr(logging, _LOG_LEVEL, logging.DEBUG))
except Exception:
    log_here('except-block entered')
    logger.setLevel(logging.DEBUG)
import ast
import os
import re
import csv
import json
import zipfile
import shutil
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
DEFAULT_MODELS_DIR = '../src/OSSS/db/models'
DEFAULT_DEPTS_CSV = '../tooling/departments.csv'
DEFAULT_POSNS_CSV = '../tooling/positions.csv'
OUT_CHANGED_ZIP = 'changed_models.zip'
CATEGORY_KEYWORDS = {'student': ['student', 'enrollment', 'attendance', 'grade', 'behavior', 'discipline', 'immunization'], 'staff': ['staff', 'employee', 'hr', 'payroll', 'position'], 'finance': ['invoice', 'order', 'ticket', 'payment', 'budget', 'asset', 'procurement', 'work_order'], 'governance': ['board', 'committee', 'cic', 'policy', 'minutes', 'agenda', 'resolution', 'meeting'], 'academics': ['course', 'section', 'assignment', 'evaluation', 'curriculum', 'calendar', 'event', 'subject'], 'facilities': ['facility', 'bus', 'route', 'maintenance'], 'communications': ['channel', 'publication', 'post', 'page', 'subscription'], 'health': ['health', 'nurse', 'medical']}

@log_call
def _read_names_from_csv(path: str) -> List[str]:
    log_here('enter function: %s', '_read_names_from_csv')
    log_here('ENTER _read_names_from_csv')
    names: List[str] = []
    if not path or not os.path.exists(path):
        log_here('if-branch entered: names:'+str(names))
        return names
    try:
        log_here('try-block entered')
        with open(path, 'r', encoding='utf-8') as f:
            log_here('with-block entered')
            log_here('WITH open(...) block entered')
            log_here('opening file in with-block')
            r = csv.DictReader(f)
            first_row = None
            for row in r:
                log_here('for-loop entered')
                if first_row is None:
                    log_here('if-branch entered')
                    first_row = row
                for key in ('name', 'title', 'department', 'dept', 'position', 'label'):
                    log_here('for-loop entered')
                    if key in row and row[key]:
                        log_here('if-branch entered')
                        names.append(str(row[key]))
                        break
                else:
                    if row and first_row:
                        log_here('if-branch entered')
                        first_key = list(first_row.keys())[0]
                        if first_key in row and row[first_key]:
                            log_here('if-branch entered')
                            names.append(str(row[first_key]))
        return [n.strip() for n in names if str(n).strip()]
    except Exception:
        log_here('except-block entered - names:'+str(names))
        return names

@log_call
def best_department_for(model_name: str, departments: List[str]) -> Optional[str]:
    log_here('enter function: %s', 'best_department_for')
    log_here('ENTER best_department_for model_name:'+str(model_name)+' departments: '+str(departments))
    m = model_name.lower()
    scores: Dict[str, int] = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        log_here('ca')
        scores[cat] = sum((1 for kw in kws if kw in m))
    best_cat = max(scores.items(), key=lambda kv: kv[1])[0] if scores else None
    if not departments:
        log_here('there are no departments')
        return None
    if best_cat:
        log_here('best category: '+str(best_cat))
        for d in departments:
            log_here('department: '+str(d))
            dl = d.lower()
            if best_cat in dl:
                log_here('there is a best category in department: '+str(d))
                return d
            for kw in CATEGORY_KEYWORDS.get(best_cat, []):
                log_here('keyword: '+str(kw))
                if kw in dl:
                    log_here('found keyword in department: '+str(d))
                    return d
    for pref in ('student', 'teaching', 'learning', 'academ', 'govern', 'human resources'):
        log_here('preference: '+str(pref))
        for d in departments:
            log_here('department: '+str(d))
            if pref in d.lower():
                log_here('pref: '+str(d))
                return d
    return departments[0]

@log_call
def relevant_positions_for(model_name: str, positions: List[str]) -> List[str]:
    log_here('enter function: %s', 'relevant_positions_for')
    log_here('ENTER relevant_positions_for')
    m = model_name.lower()
    picks: List[str] = []
    for p in positions:
        log_here('for-loop entered')
        pl = p.lower()
        if any((kw in pl for kws in CATEGORY_KEYWORDS.values() for kw in kws if kw in m)):
            log_here('if-branch entered')
            picks.append(p)
    out = []
    seen = set()
    for p in picks:
        log_here('for-loop entered')
        if p not in seen:
            log_here('if-branch entered')
            out.append(p)
            seen.add(p)
        if len(out) >= 6:
            log_here('if-branch entered')
            break
    return out

@log_call
def build_comment(model_name: str, table_name: str, departments: List[str], positions: List[str]) -> str:
    log_here('enter function: %s', 'build_comment')
    log_here('ENTER build_comment')
    owner = best_department_for(model_name + ' ' + table_name, departments) or 'Unassigned'
    pos = relevant_positions_for(model_name + ' ' + table_name, positions)
    pos_list = ', '.join(pos) if pos else 'N/A'
    description = f'{model_name} records for OSSS application.'
    ownership = f'Data owner: {owner}. Typical stakeholder positions: {pos_list}.'
    note = 'Annotation generated automatically; edit in model if needed.'
    return f'Description: {description} Data ownership: {ownership} Notes: {note}'

class ModelEditor(ast.NodeTransformer):
    log_here('Visiting class ModelEditor')

    @log_call
    def __init__(self, departments: List[str], positions: List[str], path: str):
        log_here('enter function: %s', '__init__')
        log_here('ENTER __init__')
        self.departments = departments
        self.positions = positions
        self.path = path
        self.modified = False

    @log_call
    def visit_ClassDef(self, node: ast.ClassDef):
        log_here('enter function: %s', 'visit_ClassDef')
        log_here('ENTER visit_ClassDef')
        tablename = None
        for n in node.body:
            log_here('visit_ClassDef - node:'+str(n))
            if isinstance(n, ast.Assign):
                log_here('isinstance')
                for t in n.targets:
                    log_here('taret: '+str(t))
                    if isinstance(t, ast.Name) and t.id == '__tablename__':
                        log_here('isinstance of tablename')
                        try:
                            log_here('try-block entered')
                            if isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                                log_here('if-branch entered')
                                tablename = n.value.value
                                log_here('table name: '+str(tablename))
                        except Exception:
                            log_here('except-block entered')
                            pass
        if not tablename:
            log_here('there is no table name')
            return node
        model_name = node.name
        log_here('model name: '+str(model_name))

        comment_text = build_comment(model_name, tablename, self.departments, self.positions)
        table_args_idx = None
        for idx, n in enumerate(node.body):
            log_here('iterating node body:'+str(idx))
            if isinstance(n, ast.Assign):
                log_here('if-branch entered')
                if any((isinstance(t, ast.Name) and t.id == '__table_args__' for t in n.targets)):
                    log_here('if-branch entered')
                    table_args_idx = idx
                    break

        @log_call
        def _make_comment_dict():
            log_here('_make_comment_dict() - enter function: %s', '_make_comment_dict')
            log_here('ENTER _make_comment_dict')
            return ast.Dict(keys=[ast.Constant('comment')], values=[ast.Constant(comment_text)])
        if table_args_idx is None:
            log_here('if-branch entered')
            assign = ast.Assign(targets=[ast.Name(id='__table_args__', ctx=ast.Store())], value=ast.Tuple(elts=[_make_comment_dict()], ctx=ast.Load()), type_comment=None)
            node.body.append(assign)
            self.modified = True
            return node
        assign_node = node.body[table_args_idx]
        val = assign_node.value

        @log_call
        def add_or_update_comment_in_tuple(tup: ast.Tuple) -> ast.Tuple:
            log_here('enter function: %s', 'add_or_update_comment_in_tuple')
            log_here('ENTER add_or_update_comment_in_tuple')
            if tup.elts and isinstance(tup.elts[-1], ast.Dict):
                log_here('if-branch entered')
                d: ast.Dict = tup.elts[-1]
                for i, k in enumerate(d.keys):
                    log_here('for-loop entered')
                    if isinstance(k, ast.Constant) and k.value == 'comment':
                        log_here('if-branch entered')
                        d.values[i] = ast.Constant(comment_text)
                        self.modified = True
                        return tup
                d.keys.append(ast.Constant('comment'))
                d.values.append(ast.Constant(comment_text))
                self.modified = True
                return tup
            else:
                log_here('else-branch entered')
                tup.elts.append(_make_comment_dict())
                self.modified = True
                return tup
        if isinstance(val, ast.Tuple):
            log_here('if-branch entered')
            assign_node.value = add_or_update_comment_in_tuple(val)
        else:
            log_here('else-branch entered')
            if isinstance(val, ast.Dict):
                log_here('if-branch entered')
                for i, k in enumerate(val.keys):
                    log_here('for-loop entered')
                    if isinstance(k, ast.Constant) and k.value == 'comment':
                        log_here('if-branch entered')
                        val.values[i] = ast.Constant(comment_text)
                        self.modified = True
                        break
                else:
                    val.keys.append(ast.Constant('comment'))
                    val.values.append(ast.Constant(comment_text))
                    self.modified = True
            else:
                log_here('else-branch entered')
                comment = ast.Expr(value=ast.Constant(value=f'# NOTE: __table_args__ replaced by annotation tool; original type was {type(val).__name__}'))
                new_assign = ast.Assign(targets=[ast.Name(id='__table_args__', ctx=ast.Store())], value=ast.Tuple(elts=[_make_comment_dict()], ctx=ast.Load()))
                node.body.insert(table_args_idx, comment)
                node.body[table_args_idx + 1] = new_assign
                self.modified = True
        return node

@log_call
def process_file(path: str, departments: List[str], positions: List[str], write: bool) -> bool:
    log_here('enter function: %s', 'process_file')
    log_here('ENTER process_file')
    src = open(path, 'r', encoding='utf-8').read()
    try:
        log_here('try-block entered')
        tree = ast.parse(src)
    except SyntaxError:
        log_here('except-block entered')
        return False
    editor = ModelEditor(departments, positions, path)
    new_tree = editor.visit(tree)
    ast.fix_missing_locations(new_tree)
    if not editor.modified:
        log_here('if-branch entered')
        return False
    try:
        log_here('try-block entered')
        new_src = ast.unparse(new_tree)
    except Exception:
        log_here('except-block entered')
        return False
    if write:
        log_here('if-branch entered')
        backup = path + '.bak'
        if not os.path.exists(backup):
            log_here('if-branch entered')
            with open(backup, 'w', encoding='utf-8') as f:
                log_here('with-block entered')
                log_here('WITH open(...) block entered')
                log_here('opening file in with-block')
                log_here('Checkpoint reached')
                f.write(src)
                log_here('Checkpoint reached')
        with open(path, 'w', encoding='utf-8') as f:
            log_here('with-block entered')
            log_here('WITH open(...) block entered')
            log_here('opening file in with-block')
            log_here('Checkpoint reached')
            f.write(new_src)
            log_here('Checkpoint reached')
    return True

@log_call
def main():
    log_here('enter function: %s', 'main')
    log_here('ENTER main')
    ap = argparse.ArgumentParser(description='Annotate SQLAlchemy models with __table_args__ comments.')
    ap.add_argument('--models-dir', default=DEFAULT_MODELS_DIR, help='Directory containing model .py files')
    ap.add_argument('--departments', default=DEFAULT_DEPTS_CSV, help='CSV with department names')
    ap.add_argument('--positions', default=DEFAULT_POSNS_CSV, help='CSV with position names')
    ap.add_argument('--dry-run', action='store_true', help='Only show what would change')
    ap.add_argument('--write', action='store_true', help='Write changes to files')
    args = ap.parse_args()
    departments = _read_names_from_csv(args.departments)
    positions = _read_names_from_csv(args.positions)
    print(f'[info] models-dir: {args.models_dir}')
    print(f'[info] departments loaded: {len(departments)}')
    print(f'[info] positions loaded: {len(positions)}')
    changed: List[str] = []
    for root, _dirs, files in os.walk(args.models_dir):
        log_here('iterating models directory')
        for fn in files:
            log_here('for-loop entered for '+str(fn))
            if not fn.endswith('.py'):
                log_here('file does not end with .py')
                continue
            path = os.path.join(root, fn)
            log_here('path: '+str(path))
            ok = process_file(path, departments, positions, write=args.write and (not args.dry_run))
            if ok:
                log_here('if-branch entered')
                changed.append(path)
    if not changed:
        log_here('if-branch entered')
        print('[info] No files changed.')
        return
    print(f'[info] Changed files: {len(changed)}')
    for p in changed:
        log_here('for-loop entered')
        print(' -', p)
    if args.write and (not args.dry_run):
        log_here('if-branch entered')
        os.makedirs(os.path.dirname(OUT_CHANGED_ZIP), exist_ok=True)
        with zipfile.ZipFile(OUT_CHANGED_ZIP, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            log_here('with-block entered')
            log_here('entering ZipFile with-block')
            for p in changed:
                log_here('for-loop entered')
                z.write(p, arcname=os.path.relpath(p, start=os.getcwd()))
                log_here('Checkpoint reached')
        print(f'[info] Wrote {OUT_CHANGED_ZIP}')
if __name__ == '__main__':
    log_here('if-branch entered')
    main()