#!/usr/bin/env python3
"""Fail-closed C++17 main-file new-expression feasibility transformer."""
import json, subprocess, sys, pathlib, hashlib
src, dst = map(pathlib.Path, sys.argv[1:3])
s = src.read_text()
if not s.isascii(): sys.exit('REJECTED: ASCII source required for byte offsets')
if 'namespace tc' in s: sys.exit('REJECTED: reserved runtime namespace tc')
p = subprocess.run(['clang++-18','-std=c++17','-Xclang','-ast-dump=json','-fsyntax-only',str(src)], capture_output=True,text=True)
if p.returncode: sys.exit(p.stderr)
ast=json.loads(p.stdout); sites=[]; errors=[]
def span(n):
    r=n['range']; a,b=r['begin'],r['end']
    if 'offset' not in a or 'offset' not in b: raise ValueError('macro/non-file range')
    return a['offset'],b['offset']+b['tokLen']
def descendants(n):
    yield n
    for c in n.get('inner',[]): yield from descendants(c)
class_ops={x['id'] for x in descendants(ast) if x.get('kind')=='CXXMethodDecl' and x.get('name') in ('operator new','operator new[]')}
def walk(n, parents=()):
    if n.get('kind')=='CXXNewExpr':
        # Header ranges have includedFrom; only main-file expressions are candidates.
        r=n.get('range',{}).get('begin',{})
        if 'includedFrom' not in r:
            try:
                a,b=span(n)
                if not s[a:b].lstrip().startswith('new') and not s[a:b].lstrip().startswith('::new'): raise ValueError('macro or unexpected spelling')
                if n.get('operatorNewDecl',{}).get('id') in class_ops: raise ValueError('class-specific allocator')
                if n.get('isPlacement') or n.get('placementArgs'): raise ValueError('placement/nothrow')
                if any('spellingLoc' in x.get('range',{}).get(edge,{}) for x in descendants(n) for edge in ('begin','end')): raise ValueError('macro descendant')
                op=n.get('operatorNewDecl',{}).get('type',{}).get('qualType','')
                if 'align_val_t' in op or 'nothrow' in op or op.count(','): raise ValueError('aligned/placement allocation')
                if any(x.get('kind') in ('FunctionTemplateDecl','ClassTemplateDecl','UnaryExprOrTypeTraitExpr','CXXNoexceptExpr','DecltypeType','TypeTraitExpr') for x in parents): raise ValueError('template or unevaluated context')
                if any(x.get('constexpr') for x in parents): raise ValueError('constexpr function')
                if not any(x.get('kind') in ('FunctionDecl','CXXMethodDecl','CXXConstructorDecl') for x in parents): raise ValueError('non-function context')
                if any(x.get('kind') in ('MaterializeTemporaryExpr','CXXBindTemporaryExpr','LambdaExpr','CXXThisExpr','PredefinedExpr','CoawaitExpr','CoyieldExpr','SourceLocExpr','StmtExpr','CXXDefaultArgExpr','CXXDefaultInitExpr') for x in descendants(n)): raise ValueError('temporary/lambda/this/context-sensitive expression')
                if '[' in n.get('type',{}).get('qualType',''): raise ValueError('multidimensional')
                bound=None
                if n.get('isArray'):
                    bound=span(n['inner'][0])
                sites.append(dict(start=a,end=b,bound=bound,type=n['type']['qualType'],array=bool(n.get('isArray')),init=n.get('initStyle','none'),line=s.count('\n',0,a)+1))
            except (ValueError,KeyError) as e: errors.append(str(e)+': '+str(r))
    for c in n.get('inner',[]): walk(c,parents+(n,))
walk(ast)
if errors: sys.exit('REJECTED\n'+'\n'.join(errors))
sites.sort(key=lambda x:x['start'])
for i,x in enumerate(sites): x['id']=i+1
# Recursive range rendering handles nested new expressions without overlapping edits.
def render(a,b,exclude=None):
    children=[x for x in sites if a<=x['start'] and x['end']<=b and x is not exclude]
    roots=[x for x in children if not any(y is not x and y['start']<=x['start'] and x['end']<=y['end'] for y in children)]
    out=''; pos=a
    for x in roots:
        out+=s[pos:x['start']]+wrap(x); pos=x['end']
    return out+s[pos:b]
def wrap(x):
    a,b=x['start'],x['end']; token='tc_spike_'+str(x['id'])
    if token in s: raise ValueError('reserved name collision')
    if x['bound']:
        c,d=x['bound']; expr=render(a,c,x)+'::tc::bound('+token+', ('+render(c,d,x)+'))'+render(d,b,x)
    else: expr=render(a,b,x)
    result=token+'_result'
    return '([&]() { ::tc::Request '+token+'('+str(x['id'])+', '+('true' if x['array'] else 'false')+'); try { auto *'+result+' = '+expr+'; '+token+'.success('+result+'); return '+result+'; } catch (...) { '+token+'.failure(); throw; } }())'
dst.write_text('#include "runtime.hpp"\n#line 1 "'+str(src)+'"\n'+render(0,len(s)))
check=subprocess.run(['clang++-18','-std=c++17','-fsyntax-only','-I'+str(pathlib.Path(__file__).parent),str(dst)],capture_output=True,text=True)
if check.returncode: sys.exit('REJECTED generated-code validation: '+check.stderr)
dst.with_suffix('.sites.json').write_text(json.dumps(dict(source=str(src),sha256=hashlib.sha256(s.encode()).hexdigest(),sites=sites),indent=2))
print('transformed',len(sites),'sites')
