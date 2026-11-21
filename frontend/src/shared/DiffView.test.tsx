import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { DiffView, parseDiff } from './DiffView'
import { tokenize } from './highlight'

describe('DiffView', () => {
  it('classifies additions, deletions, hunks and file headers', () => {
    const diff = '--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,2 @@\n ctx\n-old\n+new\n'
    const { container } = render(<DiffView diff={diff} />)
    const kinds = [...container.querySelectorAll('.diff-line')].map((e) => e.getAttribute('data-kind'))
    expect(kinds).toEqual(['meta', 'meta', 'hunk', 'ctx', 'del', 'add'])
  })

  it('shows a message for an empty diff', () => {
    render(<DiffView diff="  " />)
    expect(screen.getByText('The patch diff is empty.')).toBeInTheDocument()
  })

  it('numbers lines from hunk headers and counts +/- per file', () => {
    const diff = '--- a/a.py\n+++ b/a.py\n@@ -10,2 +10,3 @@\n keep\n-old\n+new\n+more\n--- a/b.yml\n+++ b/b.yml\n@@ -1 +1 @@\n-a: 1\n+a: 2\n'
    const files = parseDiff(diff)
    expect(files.map((f) => [f.path, f.add, f.del])).toEqual([
      ['a.py', 2, 1],
      ['b.yml', 1, 1],
    ])
    const lines = files[0].lines.filter((l) => l.kind !== 'meta' && l.kind !== 'hunk')
    expect(lines.map((l) => [l.oldNo, l.newNo])).toEqual([
      [10, 10],
      [11, null],
      [null, 11],
      [null, 12],
    ])
  })

  it('highlights Python and offers a split layout', async () => {
    const diff = '--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-def f(): return 1\n+def f(): return "x"  # c\n'
    const { container } = render(<DiffView diff={diff} />)
    expect(container.querySelector('.tk-kw')?.textContent).toBe('def')
    expect(container.querySelector('.tk-str')?.textContent).toBe('"x"')
    await userEvent.click(screen.getByRole('button', { name: 'Split' }))
    expect(screen.getByLabelText('Split diff')).toBeInTheDocument()
    expect(container.querySelectorAll('.diff-split .half.diff-add')).toHaveLength(1)
    expect(container.querySelectorAll('.diff-split .half.diff-del')).toHaveLength(1)
  })
})

describe('tokenize', () => {
  it('tokenizes YAML keys, strings and numbers', () => {
    const t = tokenize('  port: 8080 # note', 'yaml')
    expect(t.find((x) => x.cls === 'key')?.text).toBe('port')
    expect(t.find((x) => x.cls === 'num')?.text).toBe('8080')
    expect(t.find((x) => x.cls === 'com')?.text).toBe('# note')
  })

  it('never drops characters', () => {
    const line = 'class A(B):  x = "a\\"b" + 3.5  # z'
    expect(tokenize(line, 'python').map((t) => t.text).join('')).toBe(line)
  })
})
