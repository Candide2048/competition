import { useMemo, type ReactNode } from 'react'

/** 行内：**bold** + 转义 \$ → $。返回 React 节点数组。 */
function renderInline(text: string): ReactNode[] {
  const unescaped = text.replace(/\\\$/g, '$')
  const parts = unescaped.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**')) {
      return <strong key={i}>{p.slice(2, -2)}</strong>
    }
    return <span key={i}>{p}</span>
  })
}

type Block =
  | { kind: 'h1'; text: string }
  | { kind: 'h2'; text: string }
  | { kind: 'quote'; lines: string[] }
  | { kind: 'ul'; items: string[] }
  | { kind: 'table'; header: string[]; rows: string[][] }
  | { kind: 'hr' }
  | { kind: 'p'; text: string }

/** 极简 Markdown 解析：仅覆盖 report.generate_report 产出的块类型。 */
function parse(md: string): Block[] {
  const lines = md.replace(/\r\n/g, '\n').split('\n')
  const blocks: Block[] = []
  let i = 0

  const splitRow = (line: string) =>
    line.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())

  while (i < lines.length) {
    const line = lines[i]
    const t = line.trim()

    if (t === '') { i++; continue }
    if (t === '---' || t === '***') { blocks.push({ kind: 'hr' }); i++; continue }

    if (t.startsWith('## ')) { blocks.push({ kind: 'h2', text: t.slice(3) }); i++; continue }
    if (t.startsWith('# ')) { blocks.push({ kind: 'h1', text: t.slice(2) }); i++; continue }

    if (t.startsWith('>')) {
      const qs: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        qs.push(lines[i].trim().replace(/^>\s?/, ''))
        i++
      }
      blocks.push({ kind: 'quote', lines: qs })
      continue
    }

    if (t.startsWith('- ')) {
      const items: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('- ')) {
        items.push(lines[i].trim().slice(2))
        i++
      }
      blocks.push({ kind: 'ul', items })
      continue
    }

    // 表格：当前行是 | ... |，下一行是分隔线 |---|
    if (t.startsWith('|') && i + 1 < lines.length && /^\|?[\s:-]*-[\s:|-]*$/.test(lines[i + 1].trim())) {
      const header = splitRow(t)
      i += 2 // 跳过表头 + 分隔线
      const rows: string[][] = []
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        rows.push(splitRow(lines[i].trim()))
        i++
      }
      blocks.push({ kind: 'table', header, rows })
      continue
    }

    // 普通段落：合并连续非空非特殊行
    const buf: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !/^(#|>|-\s|\|)/.test(lines[i].trim()) &&
      lines[i].trim() !== '---'
    ) {
      buf.push(lines[i].trim())
      i++
    }
    blocks.push({ kind: 'p', text: buf.join(' ') })
  }
  return blocks
}

/** 分析报告面板：把后端 report_md（generate_report）渲染为亮色排版。 */
export default function ReportPanel({ md }: { md: string }) {
  const blocks = useMemo(() => parse(md), [md])

  return (
    <div className="report card">
      {blocks.map((b, i) => {
        switch (b.kind) {
          case 'h1':
            return <h2 key={i} className="report-h1">{renderInline(b.text)}</h2>
          case 'h2':
            return <h3 key={i} className="report-h2">{renderInline(b.text)}</h3>
          case 'hr':
            return <hr key={i} className="report-hr" />
          case 'quote':
            return (
              <blockquote key={i} className="report-quote">
                {b.lines.map((l, j) => (
                  <p key={j}>{renderInline(l)}</p>
                ))}
              </blockquote>
            )
          case 'ul':
            return (
              <ul key={i} className="report-ul">
                {b.items.map((it, j) => (
                  <li key={j}>{renderInline(it)}</li>
                ))}
              </ul>
            )
          case 'table':
            return (
              <div key={i} className="report-table-wrap">
                <table className="report-table">
                  <thead>
                    <tr>
                      {b.header.map((h, j) => (
                        <th key={j}>{renderInline(h)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {b.rows.map((r, j) => (
                      <tr key={j}>
                        {r.map((c, k) => (
                          <td key={k} className={k > 0 ? 'num' : ''}>{renderInline(c)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          default:
            return <p key={i} className="report-p">{renderInline(b.text)}</p>
        }
      })}
    </div>
  )
}
