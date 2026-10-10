import { useEffect } from 'react';
import { useTranslation } from '../../hooks/useLanguage';
import type { Installation } from '../../services/prerequisitesService';

const DANGER_BUTTON =
  'rounded border border-red-300 bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60';

const SECONDARY_BUTTON =
  'rounded border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60';

const TITLE_ID = 'delete-installation-dialog-title';

export interface DeleteInstallationDialogProps {
  /** The Installation being deleted, or `null`/undefined when the dialog is closed. */
  installation: Installation | null;
  /** Invoked when the user confirms the hard delete (Req 6.2). */
  onConfirm: () => void;
  /** Invoked when the user cancels; closes without calling the service (Req 6.3). */
  onCancel: () => void;
  /** When true, the delete request is in flight (disables the buttons). */
  deleting?: boolean;
}

/**
 * Confirmation dialog for the hard delete of an Installation. Its visible text
 * contains the target Installation's `project_name` (Req 6.1). Confirm invokes
 * `onConfirm` (the parent runs `deleteInstallation` — Req 6.2); Cancel and the
 * Escape key / backdrop invoke `onCancel`, which closes the dialog without ever
 * touching the service (Req 6.3).
 *
 * Rendered as an accessible modal (`role="dialog"`, `aria-modal="true"`,
 * `aria-labelledby`). When `installation` is null the component renders nothing.
 */
export const DeleteInstallationDialog = ({
  installation,
  onConfirm,
  onCancel,
  deleting = false,
}: DeleteInstallationDialogProps) => {
  const { t } = useTranslation();

  // Escape closes the dialog (cancel) while it is open and not mid-delete.
  useEffect(() => {
    if (!installation) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleting) {
        onCancel();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [installation, deleting, onCancel]);

  if (!installation) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={() => {
        if (!deleting) onCancel();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={TITLE_ID}
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id={TITLE_ID}
          className="mb-3 text-lg font-bold text-[#000E9C]"
        >
          {t('prereq.installations.delete.button')}
        </h2>

        <p className="mb-5 text-sm text-gray-700">
          {t('prereq.installations.delete.confirm')} «{' '}
          {installation.project_name} »
        </p>

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={deleting}
            className={SECONDARY_BUTTON}
          >
            {t('prereq.installations.edit.cancel')}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={deleting}
            className={DANGER_BUTTON}
          >
            {deleting
              ? t('prereq.installations.delete.deleting')
              : t('prereq.installations.delete.confirmButton')}
          </button>
        </div>
      </div>
    </div>
  );
};
