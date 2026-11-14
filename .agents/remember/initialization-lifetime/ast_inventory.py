"""Read-only AST inventory; deliberately does not rewrite any source."""
import collections
import json
import sys
root = json.load(open(sys.argv[1]))
counts = collections.Counter()
def visit(n):
    k = n.get('kind')
    if k in {'CXXNewExpr', 'CXXConstructExpr', 'CXXDeleteExpr', 'CXXThrowExpr', 'CXXTryStmt', 'CXXCatchStmt', 'CXXDestructorDecl', 'CXXCtorInitializer'}:
        counts[k] += 1
        if k == 'CXXNewExpr':
            print(k, 'placement=', n.get('isPlacement', False), 'array=', n.get('isArray', False), 'range=', n.get('range'))
    for child in n.get('inner', []):
        visit(child)
visit(root)
print('Full TU counts (includes headers):', dict(counts))
assert counts['CXXNewExpr'] == 4
assert counts['CXXThrowExpr'] >= 1
