/** Tiny single-line tokenizers for Python and YAML (diff lines are highlighted one at a time). */
export interface Tok {
  text: string
  cls?: 'kw' | 'str' | 'num' | 'com' | 'fn' | 'key'
}
export type Lang = 'python' | 'yaml' | 'plain'

const PY_KW = new Set(
  (
    'False None True and as assert async await break class continue def del elif else except finally for from ' +
    'global if import in is lambda nonlocal not or pass raise return try while with yield match case'
  ).split(' '),
)

const PY_RE =
  /(#.*$)|((?:[rRbBfFuU]{0,2})(?:"""(?:[^"\\]|\\.)*(?:"""|$)|'''(?:[^'\\]|\\.)*(?:'''|$)|"(?:[^"\\]|\\.)*(?:"|$)|'(?:[^'\\]|\\.)*(?:'|$)))|(\b\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|([A-Za-z_]\w*)/g

function tokenizePython(line: string): Tok[] {
  const out: Tok[] = []
  let last = 0
  let prevWord = ''
  for (const m of line.matchAll(PY_RE)) {
    const i = m.index ?? 0
    if (i > last) out.push({ text: line.slice(last, i) })
    const [full, com, str, num, word] = m
    if (com !== undefined) out.push({ text: full, cls: 'com' })
    else if (str !== undefined) out.push({ text: full, cls: 'str' })
    else if (num !== undefined) out.push({ text: full, cls: 'num' })
    else if (PY_KW.has(word)) out.push({ text: full, cls: 'kw' })
    else if (prevWord === 'def' || prevWord === 'class') out.push({ text: full, cls: 'fn' })
    else out.push({ text: full })
    prevWord = word !== undefined ? word : ''
    last = i + full.length
  }
  if (last < line.length) out.push({ text: line.slice(last) })
  return out
}

const YAML_KEY = /^(\s*(?:-\s+)?)([^\s#:"'][^:#]*?|"[^"]*"|'[^']*')(\s*:)(?=\s|$)/
const YAML_VAL = /(#.*$)|("(?:[^"\\]|\\.)*"|'[^']*')|(\b-?\d+(?:\.\d+)?\b)|(\b(?:true|false|null|yes|no|on|off)\b)/g

function tokenizeYaml(line: string): Tok[] {
  const out: Tok[] = []
  let rest = line
  const k = YAML_KEY.exec(line)
  if (k) {
    if (k[1]) out.push({ text: k[1] })
    out.push({ text: k[2], cls: 'key' })
    out.push({ text: k[3] })
    rest = line.slice(k[0].length)
  }
  let last = 0
  for (const m of rest.matchAll(YAML_VAL)) {
    const i = m.index ?? 0
    if (i > last) out.push({ text: rest.slice(last, i) })
    out.push({ text: m[0], cls: m[1] ? 'com' : m[2] ? 'str' : m[3] ? 'num' : 'kw' })
    last = i + m[0].length
  }
  if (last < rest.length) out.push({ text: rest.slice(last) })
  return out
}

export function langOf(path: string | null | undefined): Lang {
  if (!path) return 'plain'
  if (/\.pyi?$/i.test(path)) return 'python'
  if (/\.ya?ml$/i.test(path)) return 'yaml'
  return 'plain'
}

export function tokenize(line: string, lang: Lang): Tok[] {
  if (!line) return []
  if (lang === 'python') return tokenizePython(line)
  if (lang === 'yaml') return tokenizeYaml(line)
  return [{ text: line }]
}
