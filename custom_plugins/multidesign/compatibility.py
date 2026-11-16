"""Conservative, schema-only validation. Never converts or logs report data."""

SUPPORTED = {'string', 'markdown', 'cvss', 'cwe', 'date', 'number', 'boolean',
             'enum', 'combobox', 'user', 'json', 'object', 'list'}


def compare_fields(source, target, path=''):
    issues = []
    source_by_id = {f['id']: f for f in source}
    for field in target:
        name = f"{path}.{field['id']}" if path else field['id']
        original = source_by_id.get(field['id'])
        if original is None:
            issues.append(f'{name}: field missing in source design (including optional fields).')
        else:
            issues.extend(compare_type(original, field, name))
    return issues


def compare_type(source, target, path):
    kind = target.get('type')
    if kind not in SUPPORTED or source.get('type') != kind:
        return [f"{path}: incompatible types {source.get('type')} → {kind}."]
    issues = []
    if kind == 'object':
        issues += compare_fields(source.get('properties', []), target.get('properties', []), path)
    elif kind == 'list':
        issues += compare_type(source.get('items', {}), target.get('items', {}), path + '[]')
    elif kind == 'enum':
        values = {c['value'] for c in source.get('choices', [])}
        accepted = {c['value'] for c in target.get('choices', [])}
        if not values <= accepted:
            issues.append(f'{path}: target enum omits source choices: {", ".join(sorted(values - accepted))}.')
    # Constraints must match even when current data happens to satisfy a narrower target.
    constraints = {'cvss': ['cvss_version'], 'json': ['schema'],
                   'number': ['minimum', 'maximum'], 'string': ['pattern']}
    for key in constraints.get(kind, []):
        if source.get(key) != target.get(key):
            issues.append(f'{path}: different {key} constraint.')
    return issues


def check_designs(source, target):
    return (
        compare_fields([f for s in source.report_sections for f in s['fields']],
                       [f for s in target.report_sections for f in s['fields']], 'report')
        + compare_fields(source.finding_fields, target.finding_fields, 'findings')
    )
