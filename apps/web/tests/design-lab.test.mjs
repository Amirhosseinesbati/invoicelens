import test from 'node:test'
import assert from 'node:assert/strict'
import { reviewDesignFromHash, reviewDesignHref } from '../src/lib/design-lab.ts'

test('production cannot activate experimental visuals through a copied preview URL', () => {
  assert.equal(reviewDesignFromHash('#/document/demo?design=command', false), undefined)
  assert.equal(reviewDesignFromHash('#/document/demo?design=studio', false), undefined)
})
test('preview links preserve the document identity and only accept known directions', () => {
  assert.equal(reviewDesignFromHash(reviewDesignHref('doc/1', 'studio'), true), 'studio')
  assert.equal(reviewDesignFromHash('#/document/demo?design=unknown', true), undefined)
  assert.equal(reviewDesignHref('doc/1'), '#/document/doc%2F1')
})
