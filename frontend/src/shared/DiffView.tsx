import { useState } from 'react'
import { langOf, tokenize, type Lang } from './highlight'

export type Kind = 'add' | 'del' | 'hunk' | 'meta' | 'ctx'

export interface DiffLine {
  kind: Kind
  text: string
  oldNo: number | null
  newNo: number | null
}
export interface DiffFile {
  path: string
  add: number
  del: number
  lines: DiffLine[]
}

function classifyLine(line: string): Kind {
  if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('diff ') || line.startsWith('index '))
    return 'meta'
  if (line.startsWith('\\')) return 'meta'
  if (line.startsWith('@@')) return 'hunk'
  if (line.startsWith('+')) return 'add'
  if (line.startsWith('-')) return 'del'
  return 'ctx'
}

/** Parse a unified diff into files with per-line numbers. Pure: it only re-shapes the API's diff text. */
export function parseDiff(diff: string): DiffFile[] {
  const files: DiffFile[] = []
  let cur: DiffFile | null = null
  let o = 0
  let n = 0
  const start = (path: string): DiffFile => {
    const f: DiffFile = { path, add: 0, del: 0, lines: [] }
    files.push(f)
    cur = f
    return f
  }
  for (const raw of diff.replace(/\n$/, '').split('\n')) {
    const kind = classifyLine(raw)
    if (kind === 'meta' && raw.startsWith('diff --git')) {
      const m = / b\/(.+)$/.exec(raw)
      start(m ? m[1] : raw).lines.push({ kind, text: raw, oldNo: null, newNo: null })
      continue
    }
    const open = cur as DiffFile | null
    // A new "--- " header after hunk content (and without a preceding "diff --git") starts the next file.
    if (kind === 'meta' && raw.startsWith('--- ') && (!open || open.lines.some((l) => l.kind !== 'meta'))) {
      start(raw.slice(4).replace(/^a\//, ''))
    }
    const f = (cur as DiffFile | null) ?? start('(patch)')
    if (kind === 'meta' && raw.startsWith('+++ ')) {
      const p = raw.slice(4).replace(/^b\//, '')
      if (p !== '/dev/null') f.path = p
    }
    if (kind === 'hunk') {
      const m = /^@@ -(\d+)(?:,\d+)? \+(\d+)/.exec(raw)
      o = m ? Number(m[1]) : 0
      n = m ? Number(m[2]) : 0
      f.lines.push({ kind, text: raw, oldNo: null, newNo: null })
    } else if (kind === 'add') {
      f.add++
      f.lines.push({ kind, text: raw.slice(1), oldNo: null, newNo: n++ })
    } else if (kind === 'del') {
      f.del++
      f.lines.push({ kind, text: raw.slice(1), oldNo: o++, newNo: null })
    } else if (kind === 'ctx') {
      f.lines.push({ kind, text: raw.slice(1), oldNo: o++, newNo: n++ })
    } else {
      f.lines.push({ kind, text: raw, oldNo: null, newNo: null })
    }
  }
  return files
}

export function Highlighted({ text, lang }: { text: string; lang: Lang }) {
  const toks = tokenize(text, lang)
  if (toks.length === 0) return <> </>
  return (
    <>
      {toks.map((t, i) =>
        t.cls ? (
          <span key={i} className={`tk-${t.cls}`}>
            {t.text}
          </span>
        ) : (
          t.text
        ),
      )}
    </>
  )
}

const SIGN: Record<Kind, string> = { add: '+', del: '-', ctx: ' ', hunk: '', meta: '' }

function UnifiedFile({ file }: { file: DiffFile }) {
  const lang = langOf(file.path)
  return (
    <>
      {file.lines.map((l, i) => (
        <div key={i} className={`diff-line diff-${l.kind}`} data-kind={l.kind}>
          {l.kind === 'hunk' || l.kind === 'meta' ? (
            <span className="tx">{l.text || ' '}</span>
          ) : (
            <>
              <span className="ln">{l.oldNo ?? ''}</span>
              <span className="ln">{l.newNo ?? ''}</span>
              <span className="tx" data-sign={SIGN[l.kind]}>
                <Highlighted text={l.text} lang={lang} />
              </span>
            </>
          )}
        </div>
      ))}
    </>
  )
}

interface Pair {
  l?: DiffLine
  r?: DiffLine
  full?: DiffLine
}
function pairLines(lines: DiffLine[]): Pair[] {
  const out: Pair[] = []
  let i = 0
  while (i < lines.length) {
    const l = lines[i]
    if (l.kind === 'hunk' || l.kind === 'meta') {
      out.push({ full: l })
      i++
    } else if (l.kind === 'ctx') {
      out.push({ l, r: l })
      i++
    } else {
      const dels: DiffLine[] = []
      const adds: DiffLine[] = []
      while (i < lines.length && lines[i].kind === 'del') dels.push(lines[i++])
      while (i < lines.length && lines[i].kind === 'add') adds.push(lines[i++])
      for (let k = 0; k < Math.max(dels.length, adds.length); k++) out.push({ l: dels[k], r: adds[k] })
    }
  }
  return out
}

function SplitFile({ file }: { file: DiffFile }) {
  const lang = langOf(file.path)
  const half = (line: DiffLine | undefined, side: 'l' | 'r') => {
    if (!line) return <div className="half empty-cell" />
    const no = side === 'l' ? line.oldNo : line.newNo
    return (
      <div className={`half ${line.kind === 'add' ? 'diff-add' : line.kind === 'del' ? 'diff-del' : ''}`}>
        <span className="ln">{no ?? ''}</span>
        <span className="tx">
          <Highlighted text={line.text} lang={lang} />
        </span>
      </div>
    )
  }
  return (
    <div className="diff-split">
      {pairLines(file.lines).map((p, i) =>
        p.full ? (
          <div key={i} className={`span-all diff-line diff-${p.full.kind}`} data-kind={p.full.kind}>
            <span className="tx">{p.full.text}</span>
          </div>
        ) : (
          <div key={i} style={{ display: 'contents' }}>
            {half(p.l, 'l')}
            {half(p.r, 'r')}
          </div>
        ),
      )}
    </div>
  )
}

export function DiffView({ diff }: { diff: string }) {
  const [mode, setMode] = useState<'unified' | 'split'>('unified')
  if (!diff.trim()) return <p className="muted" style={{ padding: 16 }}>The patch diff is empty.</p>
  const files = parseDiff(diff)
  return (
    <div>
      <div className="diff-toolbar">
        <span className="grow muted">
          {files.length} file{files.length === 1 ? '' : 's'} ·{' '}
          <span className="plus">+{files.reduce((a, f) => a + f.add, 0)}</span>{' '}
          <span className="minus">−{files.reduce((a, f) => a + f.del, 0)}</span>
        </span>
        <div className="seg" role="group" aria-label="Diff layout">
          <button type="button" aria-pressed={mode === 'unified'} onClick={() => setMode('unified')}>
            Unified
          </button>
          <button type="button" aria-pressed={mode === 'split'} onClick={() => setMode('split')}>
            Split
          </button>
        </div>
      </div>
      <div className="diff" role="region" aria-label={mode === 'unified' ? 'Unified diff' : 'Split diff'} tabIndex={0}>
        {files.map((f, i) => (
          <div key={i} className="diff-file" data-path={f.path}>
            <div className="diff-file-head">
              <span>{f.path}</span>
              <span className="plus">+{f.add}</span>
              <span className="minus">−{f.del}</span>
            </div>
            {mode === 'unified' ? <UnifiedFile file={f} /> : <SplitFile file={f} />}
          </div>
        ))}
      </div>
    </div>
  )
}
