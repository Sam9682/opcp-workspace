import { useMemo, useRef, useState } from 'react';
import type { User } from '../services/adminService';
import { filterUsers } from './UserPicker';

interface SingleUserPickerProps {
  /** Candidate users, typically from adminService.listUsers(). */
  users: User[];
  /** Currently selected user id, or null when nothing is selected. */
  value: string | null;
  /** Called with the selected user id, or null when the selection is cleared. */
  onChange: (userId: string | null) => void;
  /** Label rendered above the control. */
  label?: string;
  /** Placeholder for the search input. */
  placeholder?: string;
  /** Text shown when nothing is selected. */
  emptyText?: string;
}

const FIELD_CLASS =
  'w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent';

/**
 * Controlled, searchable, single-select user picker used by the create and edit
 * task modals to choose an Owner. The selected user appears as a removable chip;
 * the search input filters users (case-insensitive over name + email) and, on
 * click, replaces the current selection. Removing the chip clears the value.
 *
 * Adapted from `MultiUserPicker` but restricted to a single value.
 */
export const SingleUserPicker = ({
  users,
  value,
  onChange,
  label = 'Assign to a user',
  placeholder = 'Search for a user...',
  emptyText = 'None selected',
}: SingleUserPickerProps) => {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedUser = useMemo(
    () => (value === null ? null : users.find((u) => u.id === value) ?? null),
    [users, value]
  );

  // Candidates = filtered users that are not already the selected one.
  const candidates = useMemo(
    () => filterUsers(users, query).filter((u) => u.id !== value),
    [users, query, value]
  );

  const select = (userId: string) => {
    onChange(userId);
    setQuery('');
    setOpen(false);
  };

  const clear = () => {
    onChange(null);
    setQuery('');
    setOpen(false);
  };

  return (
    <div ref={containerRef}>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>

      {selectedUser ? (
        <div className="flex flex-wrap gap-2 mb-2">
          <span className="inline-flex items-center gap-1 rounded-full bg-[#EEF0FF] text-[#000E9C] text-xs px-2 py-1">
            <span className="truncate max-w-[220px]">
              {selectedUser.first_name} {selectedUser.last_name}
            </span>
            <button
              type="button"
              aria-label={`Retirer ${selectedUser.first_name} ${selectedUser.last_name}`}
              onClick={clear}
              className="flex-shrink-0 text-[#4949FF] hover:text-[#000E9C] focus:outline-none focus:ring-2 focus:ring-[#4949FF] rounded"
            >
              ×
            </button>
          </span>
        </div>
      ) : (
        <p className="text-xs text-gray-500 mb-2">{emptyText}</p>
      )}

      <div className="relative">
        <input
          type="text"
          value={query}
          placeholder={placeholder}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => {
            // Delay so a click on a dropdown option registers before close.
            window.setTimeout(() => setOpen(false), 150);
          }}
          className={FIELD_CLASS}
        />

        {open && (
          <ul
            role="listbox"
            className="absolute z-10 mt-1 w-full max-h-56 overflow-y-auto rounded border border-gray-200 bg-white shadow-lg"
          >
            {candidates.length === 0 ? (
              <li className="px-3 py-2 text-sm text-gray-500">Aucun utilisateur trouvé</li>
            ) : (
              candidates.map((u) => (
                <li key={u.id} role="option" aria-selected={false}>
                  <button
                    type="button"
                    onMouseDown={(e) => {
                      // onMouseDown fires before input blur, keeping the click.
                      e.preventDefault();
                      select(u.id);
                    }}
                    className="w-full px-3 py-2 text-left text-sm text-gray-800 hover:bg-[#4949FF] hover:text-white focus:bg-[#4949FF] focus:text-white focus:outline-none"
                  >
                    <span className="font-medium">
                      {u.first_name} {u.last_name}
                    </span>
                    <span className="block text-xs opacity-80">{u.email}</span>
                  </button>
                </li>
              ))
            )}
          </ul>
        )}
      </div>
    </div>
  );
};

export default SingleUserPicker;
