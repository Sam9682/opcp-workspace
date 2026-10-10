import { useMemo, useRef, useState } from 'react';
import type { User } from '../services/adminService';

/**
 * Pure helper that filters a list of users by a search query.
 *
 * The match is case-insensitive and tests the query against the user's full
 * name ("first_name last_name") and email. An empty (or whitespace-only) query
 * returns the full list unchanged.
 *
 * Extracted as a pure function so it can be property-tested independently of
 * the React component (see Property 7).
 */
// eslint-disable-next-line react-refresh/only-export-components
export function filterUsers(users: User[], query: string): User[] {
  const q = query.trim().toLowerCase();
  if (!q) return users;
  return users.filter(
    (u) =>
      `${u.first_name} ${u.last_name}`.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q)
  );
}

interface UserPickerProps {
  /** Candidate users, typically from adminService.listUsers(). */
  users: User[];
  /** Currently selected user id, or null when nothing is selected. */
  value: string | null;
  /** Called with the selected user id, or null when the selection is cleared. */
  onChange: (userId: string | null) => void;
  /** French label rendered above the control. */
  label?: string;
  /** Placeholder for the search input. */
  placeholder?: string;
}

const FIELD_CLASS =
  'w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent';

/**
 * Controlled, searchable, clearable user selector shared by the create and
 * edit event modals.
 *
 * - When nothing is selected the control shows a search input; typing filters
 *   the dropdown (case-insensitive over name + email).
 * - When a user is selected the control shows that user's name and email with a
 *   "×" clear button that resets the selection to null.
 */
export const UserPicker = ({
  users,
  value,
  onChange,
  label = 'Assigner à un utilisateur',
  placeholder = 'Rechercher un utilisateur...',
}: UserPickerProps) => {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedUser = useMemo(
    () => (value === null ? null : users.find((u) => u.id === value) ?? null),
    [users, value]
  );

  const filtered = useMemo(() => filterUsers(users, query), [users, query]);

  const handleSelect = (userId: string) => {
    onChange(userId);
    setQuery('');
    setOpen(false);
  };

  const handleClear = () => {
    onChange(null);
    setQuery('');
    setOpen(false);
  };

  return (
    <div ref={containerRef}>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>

      {selectedUser ? (
        <div className="flex items-center justify-between gap-2 w-full px-3 py-2 border border-gray-300 rounded text-sm">
          <span className="truncate text-gray-800">
            {selectedUser.first_name} {selectedUser.last_name}
            <span className="text-gray-500"> — {selectedUser.email}</span>
          </span>
          <button
            type="button"
            aria-label="Effacer la sélection"
            onClick={handleClear}
            className="flex-shrink-0 text-gray-400 hover:text-[#000E9C] focus:outline-none focus:ring-2 focus:ring-[#4949FF] rounded"
          >
            ×
          </button>
        </div>
      ) : (
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
              {filtered.length === 0 ? (
                <li className="px-3 py-2 text-sm text-gray-500">Aucun utilisateur trouvé</li>
              ) : (
                filtered.map((u) => (
                  <li key={u.id} role="option" aria-selected={false}>
                    <button
                      type="button"
                      onMouseDown={(e) => {
                        // onMouseDown fires before input blur, keeping the click.
                        e.preventDefault();
                        handleSelect(u.id);
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
      )}
    </div>
  );
};

export default UserPicker;
