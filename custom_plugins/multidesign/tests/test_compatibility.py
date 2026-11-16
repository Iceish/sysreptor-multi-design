from copy import deepcopy

import pytest

from ..compatibility import compare_fields


def field(kind='string', **kwargs):
    return {'id': 'summary', 'type': kind, **kwargs}


def test_extra_source_fields_are_allowed():
    assert compare_fields([field(), {'id': 'detail', 'type': 'markdown'}], [field()]) == []


def test_missing_optional_target_is_rejected():
    assert 'missing' in compare_fields([], [field(required=False)])[0]


@pytest.mark.parametrize('source,target', [('string', 'markdown'), ('number', 'string'), ('boolean', 'number')])
def test_mismatched_types(source, target):
    assert 'incompatible types' in compare_fields([field(source)], [field(target)])[0]


def test_nested_list_object_and_enum():
    source = field('list', items={'type': 'object', 'properties': [field('enum', choices=[{'value': 'high'}, {'value': 'low'}])]})
    target = deepcopy(source)
    target['items']['properties'][0]['choices'] = [{'value': 'low'}]
    assert 'summary[].summary' in compare_fields([source], [target])[0]
    assert 'high' in compare_fields([source], [target])[0]


@pytest.mark.parametrize('kind,key,a,b', [('json', 'schema', {'type': 'string'}, {}),
                                        ('cvss', 'cvss_version', None, 'CVSS:4.0'),
                                        ('number', 'maximum', 10, 5),
                                        ('string', 'pattern', None, '[a-z]+')])
def test_constraints(kind, key, a, b):
    assert compare_fields([field(kind, **{key: a})], [field(kind, **{key: b})])


def test_unknown_type_fails_closed():
    assert compare_fields([field('future-type')], [field('future-type')])
