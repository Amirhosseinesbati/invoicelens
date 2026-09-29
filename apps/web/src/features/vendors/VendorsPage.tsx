import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ArrowUpRight, BriefcaseBusiness, Search } from 'lucide-react'
import { api } from '../../api/client'
import { EmptyState, ErrorState, LoadingState, StatusPill } from '../../components/States'
import { formatDate, formatMoney, initials, kindLabel, statusLabel, statusTone } from '../../lib/format'

export function VendorsPage({ onOpenDocument }: { onOpenDocument: (id: string) => void }) {
  const [selected, setSelected] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const vendors = useQuery({ queryKey: ['vendors'], queryFn: api.vendors })
  const documents = useQuery({ queryKey: ['documents'], queryFn: api.documents })
  const filtered = useMemo(() => (vendors.data ?? []).filter((vendor) => vendor.name.toLowerCase().includes(search.toLowerCase())).sort((a, b) => b.invoice_count - a.invoice_count || a.name.localeCompare(b.name)), [vendors.data, search])
  const selectedVendor = vendors.data?.find((vendor) => vendor.id === selected) ?? filtered[0]
  const history = (documents.data ?? []).filter((document) => document.vendor?.toLowerCase() === selectedVendor?.name.toLowerCase()).sort((a, b) => b.created_at.localeCompare(a.created_at))
  if (vendors.isPending || documents.isPending) return <main className="page"><LoadingState label="Loading vendor history…" /></main>
  if (vendors.isError) return <main className="page"><ErrorState error={vendors.error} onRetry={() => vendors.refetch()} /></main>
  if (documents.isError) return <main className="page"><ErrorState error={documents.error} onRetry={() => documents.refetch()} /></main>
  return <main className="page vendors-page"><div className="page-head compact"><div><span className="eyebrow"><span className="eyebrow-line" /> COUNTERPARTY REGISTER</span><h1>Vendor history<span className="title-period">.</span></h1><p>Follow document activity and discrepancies by supplier.</p></div><div className="head-count"><strong>{vendors.data.length}</strong><span>vendors</span></div></div>
    <div className="vendor-layout"><section className="surface vendor-list"><div className="section-heading"><div><span className="section-kicker">DIRECTORY</span><h2>Suppliers</h2></div></div><label className="vendor-search"><Search size={16} /><input aria-label="Search vendors" placeholder="Find a vendor" value={search} onChange={(event) => setSearch(event.target.value)} /></label>{filtered.length ? <div className="vendor-items">{filtered.map((vendor) => <button key={vendor.id} className={`vendor-item ${selectedVendor?.id === vendor.id ? 'vendor-selected' : ''}`} onClick={() => setSelected(vendor.id)}><span className="vendor-monogram">{initials(vendor.name)}</span><span><strong>{vendor.name}</strong><small>{vendor.invoice_count} invoice{vendor.invoice_count === 1 ? '' : 's'}</small></span><ArrowRight size={16} /></button>)}</div> : <EmptyState title="No vendors found" description="Try another search or add documents for a new vendor." />}</section>
      <section className="surface vendor-history"><div className="section-heading"><div><span className="section-kicker">ACCOUNT HISTORY</span><h2>{selectedVendor?.name || 'Select a vendor'}</h2></div><BriefcaseBusiness size={22} /></div>{selectedVendor && <div className="vendor-overview"><div><span>DOCUMENTS ON FILE</span><strong>{history.length}</strong></div><div><span>NEEDING REVIEW</span><strong>{history.filter((item) => item.status === 'needs_review').length}</strong></div><div><span>APPROVED</span><strong>{history.filter((item) => item.status === 'approved').length}</strong></div></div>}{history.length ? <div className="vendor-documents">{history.map((document) => <button key={document.id} className="vendor-document" onClick={() => onOpenDocument(document.id)}><span><strong>{document.number || document.filename}</strong><small>{kindLabel(document.kind)} · {formatDate(document.date || document.created_at)}</small></span><span className="vendor-document-right"><b>{formatMoney(document.total, document.currency)}</b><StatusPill tone={statusTone(document.status)}>{statusLabel(document.status)}</StatusPill></span><ArrowUpRight size={17} /></button>)}</div> : <EmptyState title="No linked documents" description="Documents classified for this vendor will appear here." />}</section></div>
  </main>
}
