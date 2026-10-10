import type React from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, cleanup, within } from '@testing-library/react';
import fc from 'fast-check';
import { TrackingForm } from './TrackingForm';
import { STATUS_OPTIONS } from './types';
import type { FormConfig } from './types';
import { cloudStoreConfig } from './configs';
import { LanguageProvider } from '../../hooks/useLanguage';

// Minimum property-test iterations mandated by the design (>= 100).
const NUM_RUNS = 100;

// TrackingForm resolves its status labels through the translation layer, so
// render it inside a LanguageProvider. localStorage is cleared before each test
// (and before each fast-check run) so the default French language is active and
// status labels resolve to their French copy ('Reçu', 'En attente', ...).
function renderForm(ui: React.ReactElement) {
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

beforeEach(() => {
  localStorage.clear();
});

// Generator for an arbitrary, well-formed FormConfig: 1-3 sections, each with
// 1-4 rows. Row ids/labels are made globally unique via section/row indices so
// the rendered form has no duplicate keys or ambiguous labels.
const formConfigArb: fc.Arbitrary<FormConfig> = fc
  .array(fc.integer({ min: 1, max: 4 }), { minLength: 1, maxLength: 3 })
  .map((rowCounts) => ({
    sections: rowCounts.map((rowCount, sIdx) => ({
      id: `section-${sIdx}`,
      title: `Section ${sIdx}`,
      rows: Array.from({ length: rowCount }, (_, rIdx) => ({
        id: `s${sIdx}-r${rIdx}`,
        label: `Paramètre ${sIdx}-${rIdx}`,
      })),
    })),
  }));

function totalRows(config: FormConfig): number {
  return config.sections.reduce((sum, s) => sum + s.rows.length, 0);
}

// Property 2: Every parameter row renders all four fields.
// Validates: Requirements 5.1, 6.3, 6.4
describe('Property 2: every parameter row renders all four fields', () => {
  it('renders exactly one Value, Status, Date Received, and Comments field per row', () => {
    fc.assert(
      fc.property(formConfigArb, fc.string({ minLength: 1 }), (config, keySuffix) => {
        localStorage.clear();
        cleanup();

        renderForm(
          <TrackingForm
            title="Test Form"
            storageKey={`prop2-${keySuffix}`}
            config={config}
          />,
        );

        const expected = totalRows(config);

        // Per-field accessible-label prefixes wired by TrackingForm.
        const valueFields = screen.getAllByLabelText(/^Valeur — /);
        const statusFields = screen.getAllByLabelText(/^Statut — /);
        const dateFields = screen.getAllByLabelText(/^Date de réception — /);
        const commentFields = screen.getAllByLabelText(/^Commentaires — /);

        expect(valueFields).toHaveLength(expected);
        expect(statusFields).toHaveLength(expected);
        expect(dateFields).toHaveLength(expected);
        expect(commentFields).toHaveLength(expected);

        // Each row exposes its own four fields, keyed by its unique label. A
        // getByLabelText (singular) also asserts there is exactly one control
        // per field per row.
        for (const section of config.sections) {
          for (const row of section.rows) {
            const valueInput = screen.getByLabelText(`Valeur — ${row.label}`);
            const statusInput = screen.getByLabelText(`Statut — ${row.label}`);
            const dateInput = screen.getByLabelText(`Date de réception — ${row.label}`);
            const commentsInput = screen.getByLabelText(`Commentaires — ${row.label}`);

            expect(valueInput).toHaveAttribute('type', 'text');
            expect(statusInput.tagName).toBe('SELECT');
            expect(dateInput).toHaveAttribute('type', 'date');
            expect(commentsInput.tagName).toBe('TEXTAREA');
          }
        }

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// Property 3: Status field offers exactly the four status choices.
// Validates: Requirement 5.2
describe('Property 3: status field offers exactly the four status choices', () => {
  it('each Status select exposes exactly {received, pending, blocked, na}', () => {
    const expectedValues = STATUS_OPTIONS.map((o) => o.value);

    fc.assert(
      fc.property(formConfigArb, fc.string({ minLength: 1 }), (config, keySuffix) => {
        localStorage.clear();
        cleanup();

        renderForm(
          <TrackingForm
            title="Test Form"
            storageKey={`prop3-${keySuffix}`}
            config={config}
          />,
        );

        const statusSelects = screen.getAllByLabelText(/^Statut — /);
        expect(statusSelects).toHaveLength(totalRows(config));

        for (const select of statusSelects) {
          const options = within(select as HTMLElement).getAllByRole('option');
          const optionValues = options.map((o) => (o as HTMLOptionElement).value);
          expect(optionValues).toHaveLength(4);
          expect(optionValues).toEqual(expectedValues);
        }

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// Unit test for the status legend and French labels.
// Validates: Requirements 5.3, 8.2
describe('status legend and French labels', () => {
  beforeEach(() => {
    localStorage.clear();
    cleanup();
  });

  it('maps each status to its icon and French label in the legend', () => {
    renderForm(
      <TrackingForm
        title="CloudStore"
        storageKey="legend-test"
        config={cloudStoreConfig}
      />,
    );

    const legendPairs: Array<[string, string]> = [
      ['Reçu', '✅'],
      ['En attente', '⏳'],
      ['Bloqué', '❌'],
      ['N/A', '—'],
    ];

    for (const [label, icon] of legendPairs) {
      // The legend renders each entry as: <span aria-hidden>{icon}</span>{label}
      const labelNode = screen.getAllByText(label)[0];
      const entry = labelNode.parentElement as HTMLElement;
      expect(entry).toHaveTextContent(icon);
      expect(entry).toHaveTextContent(label);
    }
  });

  it('renders section headings and row labels in French for CloudStore', () => {
    renderForm(
      <TrackingForm
        title="CloudStore"
        storageKey="french-test"
        config={cloudStoreConfig}
      />,
    );

    // Sample of French section headings.
    expect(screen.getByText('Configuration réseau')).toBeInTheDocument();
    expect(screen.getByText('Configuration DNS')).toBeInTheDocument();
    expect(screen.getByText('Sécurité & Certificats')).toBeInTheDocument();
    expect(screen.getByText('Actions côté client')).toBeInTheDocument();

    // Sample of French row labels.
    expect(screen.getByText('Nom du réseau')).toBeInTheDocument();
    expect(screen.getByText('Nom du sous-réseau')).toBeInTheDocument();
    expect(screen.getByText('Chemin de sauvegarde')).toBeInTheDocument();
  });
});
