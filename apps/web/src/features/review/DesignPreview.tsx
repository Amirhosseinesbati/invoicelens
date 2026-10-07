import { ArrowUpRight, CircleDot, ScanLine } from 'lucide-react'
import type { DocumentDetail } from '../../api/types'
import { formatMoney } from '../../lib/format'
import { reviewDesignHref, type ReviewDesign } from '../../lib/design-lab'

export function DesignPreviewControl({ id, design, demo }: { id: string; design?: ReviewDesign; demo: boolean }) {
  return <nav className="design-preview-control" aria-label="Local design prototypes">
    <span>PROTOTYPE{demo ? ' / DEMO' : ''}</span>
    <a href={reviewDesignHref(id, 'command')} aria-current={design === 'command' ? 'page' : undefined}>A <span>Command</span></a>
    <a href={reviewDesignHref(id, 'studio')} aria-current={design === 'studio' ? 'page' : undefined}>B <span>Studio</span></a>
    <a href={reviewDesignHref(id)} aria-current={!design ? 'page' : undefined} title="Return to the production Command workspace">Production</a>
  </nav>
}

export function DesignEvidenceContext({ document, design, onReview }: { document: DocumentDetail; design: ReviewDesign; onReview: () => void }) {
  const findings = document.findings.filter(item => ['open', 'pending', 'needs_review'].includes(item.status))
  const priceFinding = findings.find(item => item.code === 'UNIT_PRICE_MISMATCH' && item.details.invoice_price != null && item.details.po_price != null)
  const currency = document.fields.currency?.value || document.currency
  const invoicePrice = priceFinding ? Number(priceFinding.details.invoice_price) : NaN
  const poPrice = priceFinding ? Number(priceFinding.details.po_price) : NaN
  const comparable = Number.isFinite(invoicePrice) && Number.isFinite(poPrice)
  return <div className="design-evidence-context">
    <div className="design-context-top"><span><CircleDot size={14} />{design === 'command' ? 'EVIDENCE REVIEW' : 'THE REVIEW DOSSIER'}</span><small>v{document.version}</small></div>
    <h2>{priceFinding ? 'Unit price variance.' : findings.length ? 'Your next review decision.' : 'The record, ready for review.'}</h2>
    {comparable ? <div className="design-price-comparison"><div><span>INVOICE / UNIT</span><strong>{formatMoney(invoicePrice, currency)}</strong></div><div><span>ORDER / UNIT</span><strong>{formatMoney(poPrice, currency)}</strong></div><div><span>VARIANCE / UNIT</span><strong>{invoicePrice > poPrice ? '+' : ''}{formatMoney(invoicePrice - poPrice, currency)}</strong></div></div> : <p>{findings[0]?.message || 'Inspect the source and extracted fields before approving this version.'}</p>}
    <div className="design-context-bottom"><span><ScanLine size={14} />{priceFinding ? `Line ${Number(priceFinding.details.invoice_line_index) + 1} · ${String(priceFinding.details.sku || 'Price variance')}` : `${document.pages.length} source page${document.pages.length === 1 ? '' : 's'} · ${document.lines.length} line items`}</span><button onClick={onReview}>{findings.length ? `${findings.length} open finding${findings.length === 1 ? '' : 's'}` : 'Inspect record'}<ArrowUpRight size={15} /></button></div>
  </div>
}
