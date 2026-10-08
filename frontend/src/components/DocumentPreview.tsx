import ReactMarkdown from 'react-markdown'
import { DownloadIcon, FileIcon } from './icons'

interface Props {
  markdown: string
  downloadUrl: string
  isComplete: boolean
}

// react-markdown does not render raw HTML, and the backend escapes user text, so the
// document cannot inject markup.
export function DocumentPreview({ markdown, downloadUrl, isComplete }: Props) {
  return (
    <section className="card document" aria-labelledby="document-heading">
      <div className="card-header">
        <div className="card-title">
          <span className="card-icon" aria-hidden="true">
            <FileIcon size={16} />
          </span>
          <div>
            <h2 id="document-heading">Draft document</h2>
            <p className="card-subtitle">
              {isComplete ? 'All sections complete' : 'Updates live · gaps are marked in brackets'}
            </p>
          </div>
        </div>
        <a className="btn btn-secondary btn-sm" href={downloadUrl} download>
          <DownloadIcon size={15} /> Download .md
        </a>
      </div>
      <div className="sheet-wrap">
        <article className="sheet">
          <ReactMarkdown>{markdown}</ReactMarkdown>
        </article>
      </div>
    </section>
  )
}
