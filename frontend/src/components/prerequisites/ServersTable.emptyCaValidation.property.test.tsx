import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { validateCredentialsForm } from './ServersTable';

// ===========================================================================
// Feature: openstack-ca-certificate, Property 2: Empty CA certificate never
// gates save or retrieve
//
// For any otherwise-valid credentials form state (auth URL, credential id, and
// Nova endpoint non-empty, and a secret supplied or already stored), an empty
// or whitespace-only CA certificate SHALL NOT cause validation to fail:
// `validateCredentialsForm` returns `null`.
//
// Validates: Requirements 1.3
// ===========================================================================

// Arbitrary that yields strings which are non-empty after trimming, so they
// satisfy the required-field checks in `validateCredentialsForm`.
const nonBlank = fc
  .string({ minLength: 1 })
  .map((s) => `x${s}`) // guarantee at least one non-whitespace character
  .filter((s) => s.trim().length > 0);

// Arbitrary for empty / whitespace-only CA certificate values: the field is
// optional and must never gate validation.
const blankCaCertificate = fc.constantFrom('', ' ', '   ', '\t', '\n', '  \n\t ');

describe('Feature: openstack-ca-certificate, Property 2: Empty CA certificate never gates save or retrieve', () => {
  it('returns null for otherwise-valid states regardless of an empty/whitespace CA certificate', () => {
    fc.assert(
      fc.property(
        nonBlank, // authUrl
        nonBlank, // credentialId
        nonBlank, // novaEndpoint
        blankCaCertificate, // caCertificate (empty or whitespace)
        // Secret side: either the operator typed a non-blank secret, or none
        // was typed but one is already stored server-side. Both keep the form
        // valid, so the empty CA certificate is the only variable under test.
        fc.oneof(
          fc.record({ credentialSecret: nonBlank, secretStored: fc.boolean() }),
          fc.record({ credentialSecret: fc.constant(''), secretStored: fc.constant(true) }),
        ),
        (authUrl, credentialId, novaEndpoint, caCertificate, secret) => {
          const state = {
            authUrl,
            credentialId,
            credentialSecret: secret.credentialSecret,
            novaEndpoint,
            caCertificate,
          };

          expect(validateCredentialsForm(state, secret.secretStored)).toBeNull();
        },
      ),
      { numRuns: 100 },
    );
  });
});
