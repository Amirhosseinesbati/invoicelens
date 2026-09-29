// Validate browser-facing TypeScript shapes against FastAPI's generated OpenAPI contract.
// CI passes OPENAPI_SPEC from the backend's offline exporter; local runs use the API.
import { readFile } from 'node:fs/promises'

const source = process.env.OPENAPI_SPEC || process.argv[2] || 'http://127.0.0.1:8790/openapi.json'
const spec = source.startsWith('http') ? await fetch(source).then(async (response) => {
  if (!response.ok) throw new Error(`OpenAPI request failed: ${response.status}`)
  return response.json()
}) : JSON.parse(await readFile(source, 'utf8'))

const operations = [
  ['post', '/api/auth/login', 'LoginResponse', 'LoginRequest'], ['get', '/api/auth/me', 'UserView'],
  ['post', '/api/auth/logout'], ['get', '/api/overview', 'OverviewView'],
  ['get', '/api/documents', 'DocumentSummary[]'], ['get', '/api/documents/{document_id}', 'DocumentDetail'],
  ['get', '/api/documents/{document_id}/source'], ['get', '/api/documents/{document_id}/pages/{page_number}/image'],
  ['post', '/api/uploads', 'UploadResponse'], ['get', '/api/jobs', 'JobView[]'],
  ['get', '/api/jobs/{job_id}/events'], ['post', '/api/jobs/{job_id}/cancel', 'JobView'],
  ['post', '/api/jobs/{job_id}/retry', 'JobView'],
  ['post', '/api/documents/{document_id}/corrections', 'DocumentDetail', 'CorrectionRequest'],
  ['post', '/api/documents/{document_id}/revalidate', 'DocumentDetail'],
  ['post', '/api/documents/{document_id}/findings/{finding_id}/decisions', 'DocumentDetail', 'DecisionRequest'],
  ['post', '/api/documents/{document_id}/matches/decision', 'DocumentDetail', 'MatchDecisionRequest'],
  ['post', '/api/documents/{document_id}/line-matches/decision', 'DocumentDetail', 'LineMatchDecisionRequest'],
  ['post', '/api/documents/{document_id}/approve', 'DocumentDetail', 'ApprovalRequest'],
  ['get', '/api/documents/{document_id}/exports'],
  ['get', '/api/vendors', 'VendorView[]'], ['get', '/api/settings', 'SettingsView'],
]

const expectedSchemas = {
  LoginResponse: { user: 'ref:UserView' },
  UserView: { id: 'string', email: 'string', role: 'string', workspace_id: 'string', workspace_name: 'string' },
  OverviewView: { total_documents: 'integer', needs_review: 'integer', approved: 'integer', processing: 'integer', findings_open: 'integer', vendors: 'integer', export_count: 'integer' },
  DocumentSummary: { id: 'string', filename: 'string', kind: 'string', status: 'string', version: 'integer', page_count: 'integer', findings_count: 'integer', created_at: 'string', total: 'string' },
  DocumentDetail: { id: 'string', version: 'integer', pages: 'array:PageView', fields: 'map:FieldEvidence', lines: 'array:LineView', findings: 'array:FindingView', matches: 'array:MatchView', match_resolution: 'ref:MatchResolutionView', line_matches: 'map:string', line_match_candidates: 'array:LineMatchCandidateView', history: 'array:HistoryView', approval: 'ref:ApprovalView' },
  PageView: { page_number: 'integer', text: 'string', source_type: 'string', width: 'number', height: 'number' },
  FieldEvidence: { raw: 'string', value: 'string', page_number: 'integer', span_start: 'integer', span_end: 'integer', bbox: 'array:number', source: 'string' },
  LineView: { id: 'string', sku: 'string', description: 'string', quantity: 'string', unit: 'string', unit_price: 'string', amount: 'string', evidence: 'map:FieldEvidence' },
  FindingView: { id: 'string', code: 'string', severity: 'string', message: 'string', status: 'string', details: 'object' },
  MatchView: { po_id: 'string', document_id: 'string', po_number: 'string', score: 'number', status: 'string', details: 'object' },
  MatchResolutionView: { version: 'integer', decision: 'string', po_id: 'string', note: 'string' },
  LineMatchCandidateView: { invoice_line_index: 'integer', sku: 'string', candidates: 'array:POLineCandidateView' },
  POLineCandidateView: { po_line_id: 'string', description: 'string', quantity: 'string', unit_price: 'string', amount: 'string' },
  HistoryView: { id: 'string', action: 'string', version: 'integer', created_at: 'string' },
  ApprovalView: { version: 'integer', hash: 'string', approved_by: 'string', approved_at: 'string' },
  JobView: { id: 'string', document_id: 'string', status: 'string', progress: 'integer', current_page: 'integer', total_pages: 'integer', created_at: 'string', updated_at: 'string' },
  UploadResponse: { items: 'array:UploadItem' }, UploadItem: { status: 'string', deduplicated: 'boolean' },
  VendorView: { id: 'string', name: 'string', invoice_count: 'integer' },
  SettingsView: { mode: 'string', model_configured: 'boolean', ocr_available: 'boolean', workspace_name: 'string', export_formats: 'array:string' },
  LoginRequest: { email: 'string', password: 'string' },
  CorrectionRequest: { field: 'string', value: 'string', reason: 'string' },
  DecisionRequest: { decision: 'string' }, ApprovalRequest: { version: 'integer' },
  MatchDecisionRequest: { version: 'integer', decision: 'string', po_id: 'string', note: 'string' },
  LineMatchDecisionRequest: { version: 'integer', invoice_line_index: 'integer', po_line_id: 'string', note: 'string' },
}

const errors = []
const schemas = spec.components?.schemas || {}
const variants = (node) => node?.anyOf || [node]
const hasRef = (node, name) => variants(node).some((part) => part?.$ref === `#/components/schemas/${name}`)
const hasType = (node, type) => variants(node).some((part) => part?.type === type)
function matchesType(node, expected) {
  if (!node) return false
  if (expected.startsWith('ref:')) return hasRef(node, expected.slice(4))
  if (expected.startsWith('array:')) {
    const itemType = expected.slice(6)
    return variants(node).some((part) => part?.type === 'array' && (schemas[itemType] ? hasRef(part.items, itemType) : hasType(part.items, itemType)))
  }
  if (expected.startsWith('map:')) {
    const itemType = expected.slice(4)
    return variants(node).some((part) => part?.type === 'object' && (schemas[itemType] ? hasRef(part.additionalProperties, itemType) : hasType(part.additionalProperties, itemType)))
  }
  return hasType(node, expected)
}

for (const [name, properties] of Object.entries(expectedSchemas)) {
  const schema = schemas[name]
  if (!schema) { errors.push(`missing schema ${name}`); continue }
  for (const [key, expected] of Object.entries(properties)) {
    if (!(key in (schema.properties || {}))) errors.push(`${name}.${key} is missing`)
    else if (!matchesType(schema.properties[key], expected)) errors.push(`${name}.${key} must be ${expected}`)
  }
}

const canonical = (path) => path.replace(/\{[^}]+\}/g, '{}')
for (const [method, path, expectedResponse, expectedRequest] of operations) {
  const entry = Object.entries(spec.paths || {}).find(([actual]) => canonical(actual) === canonical(path))
  const operation = entry?.[1]?.[method]
  if (!operation) { errors.push(`missing ${method.toUpperCase()} ${path}`); continue }
  if (expectedRequest && !matchesType(operation.requestBody?.content?.['application/json']?.schema, `ref:${expectedRequest}`)) {
    errors.push(`${method.toUpperCase()} ${path} must accept ${expectedRequest}`)
  }
  if (!expectedResponse) continue // File, image, SSE and logout do not return typed JSON.
  const response = operation.responses?.['200']?.content?.['application/json']?.schema
  if (!response) { errors.push(`${method.toUpperCase()} ${path} has no JSON response schema`); continue }
  const isArray = expectedResponse.endsWith('[]')
  const name = isArray ? expectedResponse.slice(0, -2) : expectedResponse
  if (isArray ? !matchesType(response, `array:${name}`) : !matchesType(response, `ref:${name}`)) {
    errors.push(`${method.toUpperCase()} ${path} must return ${expectedResponse}`)
  }
}

if (errors.length) {
  console.error(`OpenAPI contract mismatch (${source}):\n- ${errors.join('\n- ')}`)
  process.exit(1)
}
console.log(`OpenAPI contract verified: ${operations.length} routes, ${Object.keys(expectedSchemas).length} typed schemas.`)
