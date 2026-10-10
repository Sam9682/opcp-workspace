import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, within, fireEvent, act } from '@testing-library/react';
import fc from 'fast-check';
import type React from 'react';
import { QuestionAnswerForm } from './QuestionAnswerForm';
import type { QuestionFormConfig } from './types';
import { LanguageProvider } from '../../hooks/useLanguage';
import { authService } from '../../services/authService';
import { prerequisitesService } from '../../services/prerequisitesService';
import { buildVcfDomainJson, MANAGEMENT_DOMAIN_TEMPLATE } from './vcfDomainTemplates';

// Minimum property-test iterations mandated by the design (>= 100).
const NUM_RUNS = 100;

// QuestionAnswerForm reads authentication/role through authService and persists
// answers through prerequisitesService. Mock both modules so the component's
// behavior is driven entirely by the test rather than the network or
// localStorage. Individual tests set the return values they need.
vi.mock('../../services/authService', () => ({
  authService: {
    isAuthenticated: vi.fn(),
    isAdmin: vi.fn(),
  },
}));

vi.mock('../../services/prerequisitesService', () => ({
  prerequisitesService: {
    loadClientAnswers: vi.fn(),
    saveClientAnswer: vi.fn(),
  },
}));

const mockedAuth = vi.mocked(authService);
const mockedPrereq = vi.mocked(prerequisitesService);

// Configure authService for a given member/non-member flag. After the
// opcp-installations-response-fields-editable fix, canAnswer === isAuthenticated(),
// so BOTH branches are authenticated and therefore editable:
// - member: authenticated && !admin  -> canAnswer === true
// - non-member: modeled here as an authenticated admin -> canAnswer === true
//   (authenticated admins are now editable; only unauthenticated visitors are
//   read-only — see setAuthUnauthenticated below).
function setAuth(isMember: boolean) {
  mockedAuth.isAuthenticated.mockReturnValue(true);
  mockedAuth.isAdmin.mockReturnValue(!isMember);
}

// QuestionAnswerForm now resolves its marker labels through the translation
// layer (t(labelKey)). Under the default French language the markers resolve to
// their French copy; the per-row marker's aria-label uses this resolved text.
const MARKER_LABEL_MANDATORY = 'Obligatoire';
const MARKER_LABEL_OPTIONAL = 'Optionnel';

// Render QuestionAnswerForm inside a LanguageProvider so useTranslation works.
// A helper keeps the many render sites concise while wrapping every mount.
function renderForm(ui: React.ReactElement) {
  return render(<LanguageProvider>{ui}</LanguageProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  // Clear the language store so the default French language is active and the
  // marker labels resolve to their French copy.
  localStorage.clear();
  // Default: loads resolve to empty answers so mount never rejects.
  mockedPrereq.loadClientAnswers.mockResolvedValue({ slug: '', answers: {} });
  mockedPrereq.saveClientAnswer.mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
});

// ---------------------------------------------------------------------------
// Generators
// ---------------------------------------------------------------------------

// A single generated row with index-derived, page-unique fields. questionPrimary
// must be unique because it keys the Client answer control's accessible label;
// exampleValue/commentsHint are made unique and non-empty so annotation lookups
// never collide (the component renders '—' only when a field is absent).
function makeRow(sIdx: number, rIdx: number, mandatory: boolean) {
  return {
    id: `s${sIdx}-r${rIdx}`,
    questionPrimary: `Question ${sIdx}-${rIdx}`,
    questionSecondary: `Détail ${sIdx}-${rIdx}`,
    mandatory,
    exampleValue: `Exemple-${sIdx}-${rIdx}`,
    commentsHint: `Indice-${sIdx}-${rIdx}`,
  };
}

// Arbitrary, well-formed QuestionFormConfig: 1-3 sections, each with 1-4 rows.
// The per-row `mandatory` flag is drawn from fast-check so the marker property
// exercises both branches. All ids/labels are unique across the whole config.
const questionConfigArb: fc.Arbitrary<QuestionFormConfig> = fc
  .array(fc.array(fc.boolean(), { minLength: 1, maxLength: 4 }), {
    minLength: 1,
    maxLength: 3,
  })
  .map((sections) => ({
    sections: sections.map((mandatories, sIdx) => ({
      id: `section-${sIdx}`,
      title: `Section ${sIdx}`,
      rows: mandatories.map((mandatory, rIdx) => makeRow(sIdx, rIdx, mandatory)),
    })),
  }));

function totalRows(config: QuestionFormConfig): number {
  return config.sections.reduce((sum, s) => sum + s.rows.length, 0);
}

// Installation-scoped id threaded through every render + service assertion.
const INSTALL_ID = '11111111-1111-1111-1111-111111111111';

// ---------------------------------------------------------------------------
// Property 6: Question pages show read-only questions and an editable member
// answer. Validates: Requirements 5.1, 5.2, 5.3
// ---------------------------------------------------------------------------

// Feature: opcp-prerequisites-tabs, Property 6: Question pages show read-only
// questions and an editable answer for any authenticated user.
// Updated by opcp-installations-response-fields-editable (task 3.3): the answer
// control is editable iff the user is authenticated (canAnswer === isAuthenticated),
// so an authenticated administrator is now editable, not read-only. Since setAuth
// keeps isAuthenticated() === true for both branches, every row is editable here.
describe('Property 6: read-only questions + editable answer for any authenticated user', () => {
  it('renders both question columns as non-editable text and exactly one Client answer control per row, editable for any authenticated user (member or admin)', () => {
    fc.assert(
      fc.property(questionConfigArb, fc.boolean(), (config, isMember) => {
        cleanup();
        setAuth(isMember);

        renderForm(
          <QuestionAnswerForm
            installationId={INSTALL_ID}
            slug="network-checklist"
            title="Test"
            config={config}
          />,
        );

        // Post-fix: canAnswer === isAuthenticated(). setAuth always authenticates
        // (member and admin alike), so the control is editable in both branches.
        const canAnswer = true;

        for (const section of config.sections) {
          for (const row of section.rows) {
            // The two question columns render as static text, not inputs. Their
            // exact strings appear in the document as plain text nodes.
            const primaryNode = screen.getByText(row.questionPrimary);
            const secondaryNode = screen.getByText(row.questionSecondary!);
            expect(primaryNode.tagName).not.toBe('INPUT');
            expect(primaryNode.tagName).not.toBe('TEXTAREA');
            expect(secondaryNode.tagName).not.toBe('INPUT');
            expect(secondaryNode.tagName).not.toBe('TEXTAREA');

            // Exactly one editable-or-readonly Client answer control per row,
            // addressed by its unique accessible label.
            const answer = screen.getByLabelText(
              `Réponse client — ${row.questionPrimary}`,
            ) as HTMLInputElement;
            expect(answer.tagName).toBe('INPUT');

            // Editable for any authenticated user (member or admin) after the
            // fix. Unauthenticated read-only behavior is covered by Property 2.
            expect(canAnswer).toBe(true);
            expect(answer).not.toHaveAttribute('readonly');
            expect(answer).not.toBeDisabled();
          }
        }

        // Exactly one Client answer control exists per row overall.
        const allAnswers = screen.getAllByLabelText(/^Réponse client — /);
        expect(allAnswers).toHaveLength(totalRows(config));

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 7: Every question row displays its required annotations.
// Validates: Requirements 5.4, 5.5, 5.6
// ---------------------------------------------------------------------------

// Feature: opcp-prerequisites-tabs, Property 7: Every question row displays its
// required annotations.
describe('Property 7: required row annotations', () => {
  it('shows the correct mandatory/optional marker, example value, and comments hint for each row', () => {
    fc.assert(
      fc.property(questionConfigArb, fc.boolean(), (config, isMember) => {
        cleanup();
        setAuth(isMember);

        renderForm(
          <QuestionAnswerForm
            installationId={INSTALL_ID}
            slug="vcf"
            title="Test"
            config={config}
          />,
        );

        // Under the default French language the markers resolve to their French
        // labels; the mandatory marker uses the 🔴 icon and the optional ⚪.
        const expectedMandatory = { label: MARKER_LABEL_MANDATORY, icon: '🔴' };
        const expectedOptional = { label: MARKER_LABEL_OPTIONAL, icon: '⚪' };

        for (const section of config.sections) {
          for (const row of section.rows) {
            const expected = row.mandatory ? expectedMandatory : expectedOptional;

            // Markers repeat across rows (many rows share the same flag), so
            // scope the assertion to this row's container. The answer input's
            // unique label anchors the row; the marker lives in the same row.
            const answer = screen.getByLabelText(
              `Réponse client — ${row.questionPrimary}`,
            );
            const rowEl = answer.closest('div.border-b') as HTMLElement;
            expect(rowEl).not.toBeNull();

            // The marker icon is rendered on a node whose aria-label is the
            // resolved marker label; within the row it is unique.
            const markerIcon = within(rowEl).getByLabelText(expected.label);
            expect(markerIcon).toHaveTextContent(expected.icon);
            // The opposite marker is absent from this row.
            const opposite = row.mandatory ? expectedOptional : expectedMandatory;
            expect(within(rowEl).queryByLabelText(opposite.label)).toBeNull();

            // The example value and comments hint render as their exact text.
            expect(within(rowEl).getByText(row.exampleValue!)).toBeInTheDocument();
            expect(within(rowEl).getByText(row.commentsHint!)).toBeInTheDocument();
          }
        }

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 9: Saving a client answer forwards it to the service.
// Validates: Requirements 5.7
// ---------------------------------------------------------------------------

// A minimal fixed config used by the DOM-interaction properties (save + error).
// A single row keeps the interaction unambiguous while fast-check varies the
// typed value.
const fixedConfig: QuestionFormConfig = {
  sections: [
    {
      id: 'section-0',
      title: 'Section 0',
      rows: [makeRow(0, 0, true)],
    },
  ],
};
const FIXED_ROW_ID = 's0-r0';
const FIXED_LABEL = 'Réponse client — Question 0-0';

// Feature: opcp-prerequisites-tabs, Property 9: Saving a client answer forwards
// it to the service.
describe('Property 9: saving a client answer forwards it to the service', () => {
  it('calls saveClientAnswer(installationId, slug, rowId, value) on blur for a member', async () => {
    // fast-check varies the typed value across the input space. A member
    // changes the answer, then blurs to trigger the onBlur save.
    await fc.assert(
      fc.asyncProperty(fc.string(), async (value) => {
        cleanup();
        vi.clearAllMocks();
        mockedPrereq.loadClientAnswers.mockResolvedValue({ slug: '', answers: {} });
        mockedPrereq.saveClientAnswer.mockResolvedValue(undefined);
        setAuth(true);

        const slug = 'core-control-plane';
        renderForm(
          <QuestionAnswerForm
            installationId={INSTALL_ID}
            slug={slug}
            title="Test"
            config={fixedConfig}
          />,
        );

        // Let the mount-time loadClientAnswers promise resolve before typing.
        await act(async () => {
          await Promise.resolve();
        });

        const input = screen.getByLabelText(FIXED_LABEL) as HTMLInputElement;
        await act(async () => {
          fireEvent.change(input, { target: { value } });
          fireEvent.blur(input, { target: { value } });
          await Promise.resolve();
        });

        expect(mockedPrereq.saveClientAnswer).toHaveBeenCalledWith(
          INSTALL_ID,
          slug,
          FIXED_ROW_ID,
          value,
        );

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// ---------------------------------------------------------------------------
// Property 11: A failed save shows an error indication.
// Validates: Requirements 6.5
// ---------------------------------------------------------------------------

// Feature: opcp-prerequisites-tabs, Property 11: A failed save shows an error
// indication.
describe('Property 11: a failed save shows an error indication', () => {
  it('renders a per-row error alert and preserves the typed value when saveClientAnswer rejects', async () => {
    await fc.assert(
      fc.asyncProperty(fc.string({ minLength: 1 }), async (value) => {
        cleanup();
        vi.clearAllMocks();
        mockedPrereq.loadClientAnswers.mockResolvedValue({ slug: '', answers: {} });
        // The save rejects, so the component should surface a per-row error.
        mockedPrereq.saveClientAnswer.mockRejectedValue(new Error('save failed'));
        setAuth(true);

        renderForm(
          <QuestionAnswerForm
            installationId={INSTALL_ID}
            slug="cloudstore"
            title="Test"
            config={fixedConfig}
          />,
        );

        // Let the mount-time loadClientAnswers promise resolve first; otherwise
        // its late setAnswers({}) would clobber the value typed below.
        await act(async () => {
          await Promise.resolve();
        });

        const input = screen.getByLabelText(FIXED_LABEL) as HTMLInputElement;
        // The controlled input tracks React state: change sets the typed value,
        // blur triggers the (rejecting) save. Wrap both in act and flush the
        // rejected promise so the per-row error state commits before asserting.
        await act(async () => {
          fireEvent.change(input, { target: { value } });
          fireEvent.blur(input);
          await Promise.resolve();
          await Promise.resolve();
        });

        // A visible, per-row error indication renders (role="alert").
        const alert = await screen.findByRole('alert');
        expect(alert).toBeInTheDocument();

        // The typed value persists in the input despite the failed save.
        expect((screen.getByLabelText(FIXED_LABEL) as HTMLInputElement).value).toBe(
          value,
        );

        cleanup();
      }),
      { numRuns: NUM_RUNS },
    );
  });
});

// ===========================================================================
// Bugfix spec: opcp-installations-response-fields-editable (task 1)
// Property 1: Bug Condition — Editable "Réponse client" for Any Authenticated User
//
// EXPLORATION / FIX-CHECKING TEST. These assertions encode the EXPECTED
// (post-fix) behavior: an authenticated administrator on a QA tab must see every
// "Réponse client" input editable. On the UNFIXED code they MUST FAIL, because
// `canAnswer = isAuthenticated() && !isAdmin()` renders the admin's input
// readOnly/disabled with the `cursor-not-allowed` (READONLY_FIELD_CLASS) style.
//
// Scoped PBT: the bug condition is deterministic
// (X.tab.kind = 'qa' AND isAuthenticated(X.user) AND NOT canAnswer(X.user), i.e.
// authenticated administrators). We scope to the concrete failing cases: an
// authenticated administrator across the four QA slugs.
// ===========================================================================

// The `cursor-not-allowed` class is the tell-tale of READONLY_FIELD_CLASS in
// QuestionAnswerForm.tsx; an editable field uses FIELD_CLASS which never carries
// it. Asserting on this class keeps the test resilient to the rest of the class
// string while pinning the observable "not-allowed cursor" defect.
const NOT_ALLOWED_CLASS = 'cursor-not-allowed';

// The four question/answer slugs backed by QuestionAnswerForm.
const QA_SLUGS = ['network-checklist', 'core-control-plane', 'cloudstore', 'vcf'] as const;

// Configure authService as an authenticated administrator (the bug condition):
// isAuthenticated() === true, isAdmin() === true.
function setAuthAdmin() {
  mockedAuth.isAuthenticated.mockReturnValue(true);
  mockedAuth.isAdmin.mockReturnValue(true);
}

describe('Property 1 (bug condition): authenticated admin can edit "Réponse client" across QA slugs', () => {
  it.each(QA_SLUGS)(
    'renders every "Réponse client" input editable for an authenticated admin on the %s tab',
    (slug) => {
      // Scoped-PBT config: exercise arbitrary QuestionFormConfig shapes so the
      // property holds for every row on the tab, not one hand-picked row.
      fc.assert(
        fc.property(questionConfigArb, (config) => {
          cleanup();
          setAuthAdmin();

          renderForm(
            <QuestionAnswerForm
              installationId={INSTALL_ID}
              slug={slug}
              title="Test"
              config={config}
            />,
          );

          for (const section of config.sections) {
            for (const row of section.rows) {
              const answer = screen.getByLabelText(
                `Réponse client — ${row.questionPrimary}`,
              ) as HTMLInputElement;

              // Expected (post-fix): editable — not readOnly, not disabled, and
              // without the not-allowed cursor style.
              expect(answer).not.toHaveAttribute('readonly');
              expect(answer).not.toBeDisabled();
              expect(answer.className).not.toContain(NOT_ALLOWED_CLASS);
            }
          }

          cleanup();
        }),
        { numRuns: NUM_RUNS },
      );
    },
  );
});

// ===========================================================================
// Bugfix spec: opcp-installations-response-fields-editable (task 1)
// Property 1 (VCF overlay): an admin-entered "Réponse client" value flows into
// the generated domain JSON via buildVcfDomainJson.
//
// buildVcfDomainJson is a pure overlay; the defect is INDIRECT — on the unfixed
// code an authenticated admin cannot type into the VCF field (it is
// disabled/readOnly), so no value ever reaches component state and the overlay
// falls back to the template default. This test renders the VCF form as an
// admin, types a value into a MAPPED VCF row, then asserts the overlay picks it
// up. On the unfixed code the change is rejected (disabled input) so the
// generated value stays at the template default and the assertion FAILS.
// ===========================================================================

// A management-domain row that maps to a VCF JSON key
// (`vcf_mgmt_network_name` -> row id `vcf-mgmt-network-name`).
const VCF_MAPPED_ROW_ID = 'vcf-mgmt-network-name';
const VCF_MAPPED_JSON_KEY = 'vcf_mgmt_network_name';

// Minimal VCF config whose single row is the mapped management row above.
const vcfMappedConfig: QuestionFormConfig = {
  sections: [
    {
      id: 'section-0',
      title: 'Section 0',
      rows: [
        {
          id: VCF_MAPPED_ROW_ID,
          questionPrimary: 'vcf_mgmt_network_name',
          questionSecondary: 'VCF Network',
          mandatory: true,
          exampleValue: 'vcf_network',
          commentsHint: '—',
        },
      ],
    },
  ],
};
const VCF_MAPPED_LABEL = 'Réponse client — vcf_mgmt_network_name';

describe('Property 1 (bug condition, VCF overlay): admin-entered value flows into buildVcfDomainJson', () => {
  it('overlays the admin-typed value onto the management domain template for the mapped key', async () => {
    cleanup();
    vi.clearAllMocks();
    mockedPrereq.loadClientAnswers.mockResolvedValue({ slug: '', answers: {} });
    mockedPrereq.saveClientAnswer.mockResolvedValue(undefined);
    setAuthAdmin();

    const adminValue = 'admin-custom-network';

    renderForm(
      <QuestionAnswerForm
        installationId={INSTALL_ID}
        slug="vcf"
        title="Test"
        config={vcfMappedConfig}
      />,
    );

    await act(async () => {
      await Promise.resolve();
    });

    const input = screen.getByLabelText(VCF_MAPPED_LABEL) as HTMLInputElement;

    // The VCF overlay defect is INDIRECT: buildVcfDomainJson is a correct pure
    // overlay, but on the unfixed code an admin cannot enter a value because the
    // input is disabled/readOnly, so no admin answer ever reaches state and the
    // overlay can only emit the template default. The real, reliable gate for
    // "an admin can supply a value" is the field's editability — assert it here.
    // (In jsdom `fireEvent.change` bypasses the `disabled` guard a real browser
    // enforces, so we must not rely on simulated typing to detect the bug.)
    //
    // EXPECTED OUTCOME on unfixed code: FAILS — the input is disabled/readOnly,
    // so the admin cannot provide the value the overlay would need.
    expect(input).not.toBeDisabled();
    expect(input).not.toHaveAttribute('readonly');
    expect(input.className).not.toContain(NOT_ALLOWED_CLASS);

    // Given the admin CAN type (post-fix), that value flows into the overlay for
    // the mapped key rather than falling back to the template default.
    const generated = buildVcfDomainJson('management', {
      [VCF_MAPPED_ROW_ID]: adminValue,
    });
    expect(generated[VCF_MAPPED_JSON_KEY]).toBe(adminValue);
    expect(generated[VCF_MAPPED_JSON_KEY]).not.toBe(
      MANAGEMENT_DOMAIN_TEMPLATE[VCF_MAPPED_JSON_KEY],
    );

    cleanup();
  });
});

// ===========================================================================
// Bugfix spec: opcp-installations-response-fields-editable (task 2)
// Property 2: Preservation — Non-Buggy Inputs Behave Identically
//
// PRESERVATION / observation-first. These assertions encode behavior OBSERVED
// on the UNFIXED code for NON-bug-condition inputs and must CONTINUE to hold
// after the fix. isBugCondition(X) = X.tab.kind='qa' AND isAuthenticated(X.user)
// AND NOT canAnswer(X.user). The complement covered here:
//   (a) authenticated non-admin members (already correct: editable + save),
//   (b) unauthenticated visitors (must STAY read-only after the fix, because
//       canAnswer will become just isAuthenticated()).
//
// EXPECTED OUTCOME on unfixed code: PASS (baseline to preserve).
//
// Note on reuse: the "authenticated non-admin member is editable and can save on
// blur" preservation cases are already covered by Property 6 (editable-iff-member
// rendering) and Property 9 (blur forwards the save to the service) above; those
// tests are kept as the member-editing preservation coverage rather than
// duplicated here. This block adds the case those do NOT exercise — a genuinely
// UNAUTHENTICATED visitor (isAuthenticated() === false).
// ===========================================================================

// Configure authService as an unauthenticated visitor: isAuthenticated() is
// false, so canAnswer is false both before (isAuthenticated && !isAdmin) and
// after (isAuthenticated) the fix. isAdmin() is irrelevant here but stubbed for
// completeness.
function setAuthUnauthenticated() {
  mockedAuth.isAuthenticated.mockReturnValue(false);
  mockedAuth.isAdmin.mockReturnValue(false);
}

describe('Property 2 (preservation): unauthenticated visitor keeps read-only "Réponse client" across QA slugs', () => {
  it.each(QA_SLUGS)(
    'renders every "Réponse client" input read-only/disabled for an unauthenticated visitor on the %s tab',
    (slug) => {
      // Scoped-PBT config: exercise arbitrary QuestionFormConfig shapes so the
      // property holds for every row on the tab, not one hand-picked row.
      fc.assert(
        fc.property(questionConfigArb, (config) => {
          cleanup();
          setAuthUnauthenticated();

          renderForm(
            <QuestionAnswerForm
              installationId={INSTALL_ID}
              slug={slug}
              title="Test"
              config={config}
            />,
          );

          for (const section of config.sections) {
            for (const row of section.rows) {
              const answer = screen.getByLabelText(
                `Réponse client — ${row.questionPrimary}`,
              ) as HTMLInputElement;

              // Preserved: an unauthenticated visitor sees the field read-only,
              // disabled, and carrying the not-allowed cursor style. This is the
              // scope boundary of the fix — authentication is still required.
              expect(answer).toHaveAttribute('readonly');
              expect(answer).toBeDisabled();
              expect(answer.className).toContain(NOT_ALLOWED_CLASS);
            }
          }

          cleanup();
        }),
        { numRuns: NUM_RUNS },
      );
    },
  );

  it.each(QA_SLUGS)(
    'never forwards a save to the service on blur for an unauthenticated visitor on the %s tab',
    async (slug) => {
      // The onBlur handler guards on canAnswer, so a blur from an unauthenticated
      // visitor must not call saveClientAnswer. This preserves the
      // "authentication required to persist" boundary after the fix.
      cleanup();
      vi.clearAllMocks();
      mockedPrereq.loadClientAnswers.mockResolvedValue({ slug: '', answers: {} });
      mockedPrereq.saveClientAnswer.mockResolvedValue(undefined);
      setAuthUnauthenticated();

      renderForm(
        <QuestionAnswerForm
          installationId={INSTALL_ID}
          slug={slug}
          title="Test"
          config={fixedConfig}
        />,
      );

      await act(async () => {
        await Promise.resolve();
      });

      const input = screen.getByLabelText(FIXED_LABEL) as HTMLInputElement;
      await act(async () => {
        fireEvent.blur(input, { target: { value: 'anything' } });
        await Promise.resolve();
      });

      expect(mockedPrereq.saveClientAnswer).not.toHaveBeenCalled();

      cleanup();
    },
  );
});
