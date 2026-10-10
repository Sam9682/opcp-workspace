import { useMemo, useRef, useState } from 'react';
import type { User } from '../services/adminService';
import { filterUsers } from './UserPicker';

interface MultiUserPickerProps {
  /** Candidate users, typically from adminService.listUsers(). */
  users: User[];
  /** Currently selected user ids (empty array => public event). */
  value: string[];
  /** Called with the next full list of selected ids. */
  onChange: (userIds: string[]) => void;
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
 * Controlled, searchable, multi-select user picker used by the create and edit
 * event modals. Selected users appear as removable chips; the search input
 * filters remaining users (case-insensitive over name + email) and adds them on
 * click. An empty selection means the event is public (visible to everyone).
 */
export const MultiUserPicker = ({
  users,
  value,
  onChange,
  label = 'Assign to users',
  placeholder = 'Search for a user...',
  emptyText = 'None (public event)',
}: MultiUserPickerProps) => {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedUsers = useMemo(
    () =>
      value
        .map((id) => users.find((u) => u.id === id))
        .filter((u): u is User => Boolean(u)),
    [users, value]
  );

  // Candidates = filtered users that are not already selected.
  const candidates = useMemo(() => {
    const selected = new Set(value);
    return filterUsers(users, query).filter((u) => !selected.has(u.id));
  }, [users, query, value]);

  const add = (userId: string) => {
    if (!value.includes(userId)) {
      onChange([...value, userId]);
    }
    setQuery('');
    setOpen(false);
  };

  const remove = (userId: string) => {
    onChange(value.filter((id) => id !== userId));
  };

  return (
    <div ref={containerRef}>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>

      {selectedUsers.length > 0 ? (
        <div className="flex flex-wrap gap-2 mb-2">
          {selectedUsers.map((u) => (
            <span
              key={u.id}
              className="inline-flex items-center gap-1 rounded-full bg-[#EEF0FF] text-[#000E9C] text-xs px-2 py-1"
            >
              <span className="truncate max-w-[220px]">
                {u.first_name} {u.last_name}
              </span>
              <button
                type="button"
                aria-label={`Retirer ${u.first_name} ${u.last_name}`}
                onClick={() => remove(u.id)}
                className="flex-shrink-0 text-[#4949FF] hover:text-[#000E9C] focus:outline-none focus:ring-2 focus:ring-[#4949FF] rounded"
              >
                ×
              </button>
            </span>
          ))}
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
                      add(u.id);
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

export default MultiUserPicker;
